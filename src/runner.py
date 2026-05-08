"""Runner: orchestra l'esecuzione di prompt × model × repeat e persiste su DB.

API:
- `run_single(prompt_id, model_ids=None, repeat=1, trigger_type="manual")` → per UI / on-demand
- `run_batch(prompt_ids=None, model_ids=None, repeat=3, trigger_type="scheduled")` → batch periodici

Per ogni risposta:
1. crea record `Response` con i campi denormalizzati (citation rate fields)
2. crea record `Citation` per ogni URL citato (classificato target/competitor/other)
3. la mention detection (Fase 6) si aggancia qui, hook pronto

Parallelizzazione: ThreadPool per modello (i singoli provider sono I/O bound).
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.analyzer import (
    BrandIndex,
    MentionAnalysis,
    analyze_text,
    load_brand_index,
)
from src.citation_analyzer import (
    BrandConfig,
    CitationAnalysis,
    analyze_citations,
    load_brand_config,
)
from src.providers import LLMProvider, build_all_enabled, build_provider
from src.providers.base import LLMResponse
from src.providers.factory import _load_models_config
from src.storage import Citation as DBCitation
from src.storage import Mention as DBMention
from src.storage import Prompt, Response, Run, get_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class RunStats:
    run_id: int
    n_attempted: int
    n_success: int
    n_errors: int
    elapsed_s: float


def _resolve_providers(model_ids: list[str] | None) -> list[LLMProvider]:
    """Costruisce i provider richiesti. Se `model_ids=None` usa tutti gli enabled."""
    if model_ids is None:
        return build_all_enabled()
    cfg_by_id = {c["id"]: c for c in _load_models_config()}
    out: list[LLMProvider] = []
    for mid in model_ids:
        cfg = cfg_by_id.get(mid)
        if cfg is None:
            logger.warning("Model id sconosciuto: %s", mid)
            continue
        try:
            out.append(build_provider(cfg))
        except Exception as e:  # noqa: BLE001
            logger.warning("Skip %s: %s", mid, e)
    return out


def _persist_response(
    session: Session,
    *,
    run_id: int,
    prompt_id: int,
    provider: LLMProvider,
    llm_response: LLMResponse,
    analysis: CitationAnalysis,
    mention_analysis: MentionAnalysis,
) -> Response:
    """Salva una `Response` con campi denormalizzati e tutte le `Citation`."""
    raw_json: str | None = None
    try:
        raw_json = json.dumps(llm_response.raw_response, default=str)[:200_000]
    except Exception:  # noqa: BLE001
        raw_json = None

    response = Response(
        run_id=run_id,
        prompt_id=prompt_id,
        model_id=provider.model_id,
        text=llm_response.text or "",
        latency_ms=llm_response.latency_ms,
        tokens=llm_response.tokens_used,
        raw_json=raw_json,
        created_at=datetime.utcnow(),
        # Citation-derived denormalized fields
        has_target_citation=analysis.has_target_citation,
        target_citation_position=analysis.target_citation_position,
        total_citations=analysis.total,
        has_target_mention=mention_analysis.has_target_mention,
        target_position_in_list=mention_analysis.target_position_in_list,
    )
    session.add(response)
    session.flush()  # per avere response.id

    for ac in analysis.citations:
        session.add(
            DBCitation(
                response_id=response.id,
                position=ac.position,
                url=ac.url,
                domain=ac.domain,
                is_target_domain=ac.is_target_domain,
                is_competitor_domain=ac.is_competitor_domain,
                page_title=ac.page_title,
                snippet=ac.snippet,
            )
        )
    for dm in mention_analysis.mentions:
        session.add(
            DBMention(
                response_id=response.id,
                brand_name=dm.brand_name,
                is_target=dm.is_target,
                position_in_text=dm.position_in_text,
                context_snippet=dm.context_snippet,
                sentiment=dm.sentiment,
                context_label=dm.context_label,
            )
        )
    return response


# ---------------------------------------------------------------------------
# Core: una singola query
# ---------------------------------------------------------------------------


def _execute_one(
    provider: LLMProvider,
    prompt_text: str,
    brand_cfg: BrandConfig,
    brand_index: BrandIndex,
    do_sentiment: bool,
) -> tuple[LLMResponse, CitationAnalysis, MentionAnalysis]:
    """Esegue la query, analizza citazioni e menzioni nel testo."""
    llm_response = provider.query(prompt_text)
    analysis = analyze_citations(llm_response.citations, brand_cfg)
    mention_analysis = analyze_text(
        llm_response.text, brand_index=brand_index, do_sentiment=do_sentiment,
    )
    return llm_response, analysis, mention_analysis


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_single(
    prompt_id: int,
    *,
    model_ids: list[str] | None = None,
    repeat: int = 1,
    trigger_type: str = "manual",
    max_workers: int = 4,
    do_sentiment: bool = False,
) -> RunStats:
    """Esegue tutti i provider richiesti su un singolo prompt, `repeat` volte ciascuno."""
    return _run_internal(
        prompt_ids=[prompt_id],
        model_ids=model_ids,
        repeat=repeat,
        trigger_type=trigger_type,
        max_workers=max_workers,
        do_sentiment=do_sentiment,
    )


def run_batch(
    prompt_ids: list[int] | None = None,
    *,
    model_ids: list[str] | None = None,
    repeat: int = 3,
    trigger_type: str = "scheduled",
    max_workers: int = 4,
    only_active: bool = True,
    do_sentiment: bool = False,
) -> RunStats:
    """Esegue il batch su tutti i prompt richiesti (default: tutti gli `is_active`)."""
    if prompt_ids is None:
        with get_session() as s:
            stmt = select(Prompt.id)
            if only_active:
                stmt = stmt.where(Prompt.is_active.is_(True))
            prompt_ids = [row[0] for row in s.execute(stmt).all()]
    if not prompt_ids:
        logger.warning("Nessun prompt da eseguire")
        return RunStats(run_id=-1, n_attempted=0, n_success=0, n_errors=0, elapsed_s=0)

    return _run_internal(
        prompt_ids=prompt_ids,
        model_ids=model_ids,
        repeat=repeat,
        trigger_type=trigger_type,
        max_workers=max_workers,
        do_sentiment=do_sentiment,
    )


def _run_internal(
    *,
    prompt_ids: list[int],
    model_ids: list[str] | None,
    repeat: int,
    trigger_type: str,
    max_workers: int,
    do_sentiment: bool = False,
) -> RunStats:
    providers = _resolve_providers(model_ids)
    if not providers:
        raise RuntimeError(
            "Nessun provider disponibile. Controlla API key in .env e models.yaml"
        )

    brand_cfg = load_brand_config()
    brand_index = load_brand_index()
    started = datetime.utcnow()

    # Crea Run
    with get_session() as s:
        run = Run(started_at=started, trigger_type=trigger_type)
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id

        # Carica i testi dei prompt una volta sola
        prompts = {p.id: p for p in s.scalars(select(Prompt).where(Prompt.id.in_(prompt_ids))).all()}

    # Costruisci la lista dei task: (prompt_id, prompt_text, provider, repeat_idx)
    tasks: list[tuple[int, str, LLMProvider, int]] = []
    for pid in prompt_ids:
        if pid not in prompts:
            logger.warning("Prompt id=%s non trovato, skip", pid)
            continue
        text = prompts[pid].text
        for prov in providers:
            for r in range(repeat):
                tasks.append((pid, text, prov, r))

    n_success = 0
    n_errors = 0

    logger.info("Run %s: %d task (%d prompt × %d provider × %d repeat)",
                run_id, len(tasks), len(prompt_ids), len(providers), repeat)

    # Esegui in parallelo
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_task = {
            pool.submit(_execute_one, prov, text, brand_cfg, brand_index, do_sentiment):
                (pid, text, prov, ri)
            for (pid, text, prov, ri) in tasks
        }
        # Persistiamo i risultati man mano in una sessione dedicata (single-thread DB)
        with get_session() as s:
            for fut in as_completed(future_to_task):
                pid, text, prov, ri = future_to_task[fut]
                try:
                    llm_resp, analysis, mention_analysis = fut.result()
                except Exception as e:  # noqa: BLE001
                    logger.error("Task fallito (prompt=%s model=%s): %s", pid, prov.model_id, e)
                    llm_resp = LLMResponse(
                        model_id=prov.model_id, text="", citations=[], error=str(e),
                    )
                    analysis = CitationAnalysis(citations=[])
                    mention_analysis = MentionAnalysis(mentions=[])

                if llm_resp.error:
                    n_errors += 1
                else:
                    n_success += 1

                _persist_response(
                    s,
                    run_id=run_id,
                    prompt_id=pid,
                    provider=prov,
                    llm_response=llm_resp,
                    analysis=analysis,
                    mention_analysis=mention_analysis,
                )
                # Commit per ogni risposta → progress visibile, robusto a crash
                s.commit()

            # Chiudi run
            run = s.get(Run, run_id)
            run.finished_at = datetime.utcnow()
            s.commit()
            elapsed = (run.finished_at - run.started_at).total_seconds()

    logger.info("Run %s done: %d success, %d errors in %.1fs",
                run_id, n_success, n_errors, elapsed)

    return RunStats(
        run_id=run_id,
        n_attempted=len(tasks),
        n_success=n_success,
        n_errors=n_errors,
        elapsed_s=elapsed,
    )
