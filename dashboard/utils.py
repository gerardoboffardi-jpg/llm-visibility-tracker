"""Helper condivisi per le pagine Streamlit."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=True)

import pandas as pd  # noqa: E402
from sqlalchemy import Integer, func, select  # noqa: E402

from src.analyzer import load_brand_index  # noqa: E402
from src.citation_analyzer import load_brand_config  # noqa: E402
from src.storage import (  # noqa: E402
    Citation,
    Mention,
    Prompt,
    Response,
    Run,
    get_session,
)


def fmt_pct(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x * 100:.1f}%"


def fmt_dt(dt) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M")


def prompts_overview_df() -> pd.DataFrame:
    """Tabella con tutti i prompt + metriche aggregate (citation rate, mention rate, ecc)."""
    with get_session() as s:
        prompts = list(s.scalars(select(Prompt)).all())

        rows = []
        for p in prompts:
            n_resp = s.scalar(
                select(func.count(Response.id)).where(Response.prompt_id == p.id)
            ) or 0
            n_models = s.scalar(
                select(func.count(func.distinct(Response.model_id))).where(
                    Response.prompt_id == p.id
                )
            ) or 0
            last_run = s.scalar(
                select(func.max(Response.created_at)).where(Response.prompt_id == p.id)
            )
            if n_resp:
                n_cit = s.scalar(
                    select(func.count(Response.id)).where(
                        Response.prompt_id == p.id,
                        Response.has_target_citation.is_(True),
                    )
                ) or 0
                n_men = s.scalar(
                    select(func.count(Response.id)).where(
                        Response.prompt_id == p.id,
                        Response.has_target_mention.is_(True),
                    )
                ) or 0
                cit_rate = n_cit / n_resp
                men_rate = n_men / n_resp
            else:
                cit_rate = None
                men_rate = None

            rows.append({
                "id": p.id,
                "prompt": p.text,
                "categoria": p.category or "",
                "geo": p.geo or "",
                "intent": p.intent or "",
                "attivo": p.is_active,
                "n_risposte": n_resp,
                "n_modelli": n_models,
                "citation_rate": cit_rate,
                "mention_rate": men_rate,
                "ultima_run": last_run,
            })
    df = pd.DataFrame(rows)
    return df


def global_kpis() -> dict:
    """KPI aggregati a livello globale."""
    with get_session() as s:
        n_prompts = s.scalar(select(func.count(Prompt.id))) or 0
        n_active = s.scalar(select(func.count(Prompt.id)).where(Prompt.is_active.is_(True))) or 0
        n_responses = s.scalar(select(func.count(Response.id))) or 0
        n_runs = s.scalar(select(func.count(Run.id))) or 0
        n_target_cit = s.scalar(
            select(func.count(Response.id)).where(Response.has_target_citation.is_(True))
        ) or 0
        n_target_men = s.scalar(
            select(func.count(Response.id)).where(Response.has_target_mention.is_(True))
        ) or 0
        n_total_cits = s.scalar(select(func.count(Citation.id))) or 0
        n_target_cit_total = s.scalar(
            select(func.count(Citation.id)).where(Citation.is_target_domain.is_(True))
        ) or 0
        n_competitor_cit_total = s.scalar(
            select(func.count(Citation.id)).where(Citation.is_competitor_domain.is_(True))
        ) or 0

        cit_rate = (n_target_cit / n_responses) if n_responses else 0.0
        men_rate = (n_target_men / n_responses) if n_responses else 0.0
        share_of_cit = (n_target_cit_total / n_total_cits) if n_total_cits else 0.0
        gap = max(0.0, men_rate - cit_rate)  # menzionato ma non citato

    return {
        "n_prompts": n_prompts,
        "n_active": n_active,
        "n_responses": n_responses,
        "n_runs": n_runs,
        "citation_rate": cit_rate,
        "mention_rate": men_rate,
        "share_of_citations": share_of_cit,
        "citation_gap": gap,
        "n_total_citations": n_total_cits,
        "n_target_citations": n_target_cit_total,
        "n_competitor_citations": n_competitor_cit_total,
    }


def domain_aggregates() -> pd.DataFrame:
    """Tabella aggregata di tutti i domini citati con conteggi."""
    with get_session() as s:
        stmt = (
            select(
                Citation.domain,
                Citation.is_target_domain,
                Citation.is_competitor_domain,
                func.count(Citation.id).label("n_citations"),
                func.count(func.distinct(Response.prompt_id)).label("n_prompts"),
                func.count(func.distinct(Response.model_id)).label("n_models"),
            )
            .join(Response, Response.id == Citation.response_id)
            .group_by(Citation.domain, Citation.is_target_domain, Citation.is_competitor_domain)
            .order_by(func.count(Citation.id).desc())
        )
        rows = [dict(r._mapping) for r in s.execute(stmt).all()]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["category"] = df.apply(
        lambda r: "target" if r["is_target_domain"] else
        ("competitor" if r["is_competitor_domain"] else "other"),
        axis=1,
    )
    return df[["domain", "category", "n_citations", "n_prompts", "n_models"]]


def model_aggregates() -> pd.DataFrame:
    """Per ogni model_id: n risposte, citation rate, mention rate, latency media."""
    with get_session() as s:
        stmt = (
            select(
                Response.model_id,
                func.count(Response.id).label("n_responses"),
                func.sum(
                    func.coalesce(Response.has_target_citation.cast(Integer), 0)
                ).label("n_target_cit"),
                func.sum(
                    func.coalesce(Response.has_target_mention.cast(Integer), 0)
                ).label("n_target_men"),
                func.avg(Response.latency_ms).label("avg_latency_ms"),
                func.avg(Response.total_citations).label("avg_total_citations"),
            )
            .group_by(Response.model_id)
            .order_by(func.count(Response.id).desc())
        )
        rows = [dict(r._mapping) for r in s.execute(stmt).all()]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["citation_rate"] = df["n_target_cit"] / df["n_responses"]
    df["mention_rate"] = df["n_target_men"] / df["n_responses"]
    return df


def get_responses_for_prompt(prompt_id: int) -> list[dict]:
    """Risposte di un prompt con citazioni e menzioni associate, ordinate per data desc."""
    out = []
    with get_session() as s:
        responses = list(s.scalars(
            select(Response).where(Response.prompt_id == prompt_id).order_by(Response.created_at.desc())
        ).all())
        for r in responses:
            cits = list(s.scalars(
                select(Citation).where(Citation.response_id == r.id).order_by(Citation.position)
            ).all())
            mens = list(s.scalars(
                select(Mention).where(Mention.response_id == r.id).order_by(Mention.position_in_text)
            ).all())
            out.append({
                "id": r.id,
                "model_id": r.model_id,
                "created_at": r.created_at,
                "text": r.text,
                "latency_ms": r.latency_ms,
                "tokens": r.tokens,
                "has_target_mention": r.has_target_mention,
                "has_target_citation": r.has_target_citation,
                "target_citation_position": r.target_citation_position,
                "target_position_in_list": r.target_position_in_list,
                "total_citations": r.total_citations,
                "citations": [
                    {
                        "position": c.position, "url": c.url, "domain": c.domain,
                        "is_target": c.is_target_domain, "is_competitor": c.is_competitor_domain,
                        "title": c.page_title, "snippet": c.snippet,
                    }
                    for c in cits
                ],
                "mentions": [
                    {
                        "brand_name": m.brand_name, "is_target": m.is_target,
                        "position_in_text": m.position_in_text,
                        "snippet": m.context_snippet,
                        "sentiment": m.sentiment, "context_label": m.context_label,
                    }
                    for m in mens
                ],
            })
    return out


def highlight_brands_html(text: str) -> str:
    """Restituisce HTML con i brand evidenziati: target verde, competitor arancione."""
    import html
    if not text:
        return ""
    idx = load_brand_index()
    cfg = load_brand_config()
    target_color = "#16a34a"  # verde
    comp_color = "#f97316"    # arancione

    # Costruisci pattern combinato: ordine per lunghezza desc così i nomi lunghi vincono
    aliases = []
    for b in idx.brands:
        for a in b.aliases:
            aliases.append((a, b.is_target))
    aliases.sort(key=lambda x: len(x[0]), reverse=True)

    safe = html.escape(text)
    for alias, is_target in aliases:
        color = target_color if is_target else comp_color
        weight = "700" if is_target else "600"
        # Evita doppio wrap: usa lookbehind/ahead negativo per <span>
        pattern = re.compile(rf"(?<!\w){re.escape(html.escape(alias))}(?!\w)")
        safe = pattern.sub(
            f'<span style="background:{color}22;color:{color};padding:1px 4px;border-radius:3px;font-weight:{weight}">{html.escape(alias)}</span>',
            safe,
        )
    # Preserva newline
    return safe.replace("\n", "<br>")
