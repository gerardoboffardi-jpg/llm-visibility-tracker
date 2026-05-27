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

# Bridge: in produzione (Streamlit Cloud) i secrets vengono passati via
# st.secrets, non env. Li copiamo in os.environ così tutto il codice provider
# continua a leggere via os.getenv senza modifiche.
import os as _os  # noqa: E402
try:
    import streamlit as _st  # noqa: E402
    for _k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
               "PERPLEXITY_API_KEY", "DATABASE_URL", "SLACK_WEBHOOK_URL"):
        _v = _st.secrets.get(_k) if hasattr(_st, "secrets") else None
        if _v and not _os.environ.get(_k):
            _os.environ[_k] = str(_v)
except Exception:
    pass

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
    init_db,
)

# Inizializza schema (idempotente — safe da chiamare a ogni reload)
try:
    init_db()
except Exception as _e:  # noqa: BLE001
    # Se il DB non è raggiungibile mostriamo l'errore in chiaro al primo widget
    import streamlit as _st
    _st.error(f"⚠️ Impossibile inizializzare il database: {_e}")
    _st.stop()


_ANIMALS = [
    "🦘", "🐢", "🦊", "🦉", "🐝", "🦒", "🐙", "🦋", "🐬", "🦜",
    "🐧", "🦩", "🦔", "🐹", "🦦", "🐨", "🐼", "🐎", "🦓", "🦌",
    "🐆", "🦄", "🦥", "🦡", "🦃", "🦢", "🐡", "🦞", "🐳", "🐊",
]
_FLAGS = [
    "🇮🇹", "🇪🇺", "🇪🇸", "🇫🇷", "🇩🇪", "🇬🇧", "🇮🇪", "🇳🇱",
    "🇵🇹", "🇸🇪", "🇩🇰", "🇨🇭", "🇦🇹", "🇧🇪", "🇫🇮", "🇳🇴",
]


def fun_loader(text: str) -> str:
    """Restituisce una stringa con 2 emoji random (1 animale + 1 bandiera) per
    rendere meno noioso il caricamento. Esempio: '🦘 🇮🇹 — Genero prompt…'

    Uso: `with st.spinner(fun_loader("Genero prompt…")): ...`
    """
    import random
    animal = random.choice(_ANIMALS)
    flag = random.choice(_FLAGS)
    return f"{animal} {flag} — {text}"


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


def recent_responses_feed(
    limit: int = 50,
    model_id: str | None = None,
    prompt_id: int | None = None,
    only_citation: bool = False,
    only_mention: bool = False,
    only_gap: bool = False,
) -> list[dict]:
    """Feed cronologico delle risposte con prompt text + citazioni + mention.

    Ottimizzato per la pagina "Risposte" — fa una query principale poi carica
    citazioni/mention solo per le risposte mostrate.
    """
    with get_session() as s:
        stmt = (
            select(Response, Prompt.text.label("prompt_text"),
                   Prompt.category.label("prompt_category"),
                   Prompt.geo.label("prompt_geo"))
            .join(Prompt, Prompt.id == Response.prompt_id)
            .order_by(Response.created_at.desc())
        )
        if model_id:
            stmt = stmt.where(Response.model_id == model_id)
        if prompt_id:
            stmt = stmt.where(Response.prompt_id == prompt_id)
        if only_citation:
            stmt = stmt.where(Response.has_target_citation.is_(True))
        if only_mention:
            stmt = stmt.where(Response.has_target_mention.is_(True))
        if only_gap:
            stmt = stmt.where(
                Response.has_target_mention.is_(True),
                Response.has_target_citation.is_(False),
            )
        stmt = stmt.limit(limit)
        rows = list(s.execute(stmt).all())

        out = []
        for row in rows:
            r = row[0]
            cits = list(s.scalars(
                select(Citation).where(Citation.response_id == r.id).order_by(Citation.position)
            ).all())
            mens = list(s.scalars(
                select(Mention).where(Mention.response_id == r.id)
            ).all())
            out.append({
                "id": r.id,
                "prompt_id": r.prompt_id,
                "prompt_text": row.prompt_text,
                "prompt_category": row.prompt_category,
                "prompt_geo": row.prompt_geo,
                "model_id": r.model_id,
                "created_at": r.created_at,
                "text": r.text,
                "latency_ms": r.latency_ms,
                "has_target_mention": r.has_target_mention,
                "has_target_citation": r.has_target_citation,
                "total_citations": r.total_citations,
                "citations": [
                    {
                        "position": c.position, "url": c.url, "domain": c.domain,
                        "is_target": c.is_target_domain, "is_competitor": c.is_competitor_domain,
                        "title": c.page_title,
                    }
                    for c in cits
                ],
                "n_mentions": len(mens),
                "n_target_mentions": sum(1 for m in mens if m.is_target),
                "n_competitor_mentions": sum(1 for m in mens if not m.is_target),
            })
    return out


def get_available_models() -> list[str]:
    """Lista degli model_id presenti nelle risposte (per filtri)."""
    with get_session() as s:
        rows = s.execute(
            select(Response.model_id, func.count(Response.id).label("n"))
            .group_by(Response.model_id)
            .order_by(func.count(Response.id).desc())
        ).all()
        return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# COST & RUN HISTORY
# ---------------------------------------------------------------------------


def cost_aggregates() -> dict:
    """Statistiche di costo aggregato a livello di tutto il sistema.

    Returns dict con:
      - cost_total_usd
      - cost_by_model: list[dict(model_id, n_resp, tokens, cost_usd)]
      - cost_last_7d_usd
      - n_responses_with_tokens
    """
    from datetime import datetime, timedelta
    from src.cost import estimate_cost, load_model_pricing

    pricing = load_model_pricing()
    with get_session() as s:
        responses = list(s.scalars(select(Response)).all())

    total = 0.0
    last_7d = 0.0
    n_with_tokens = 0
    cutoff = datetime.utcnow() - timedelta(days=7)
    by_model: dict[str, dict] = {}
    for r in responses:
        c = estimate_cost(r.model_id, r.tokens or 0, has_web_search=True, pricing=pricing)
        total += c
        if r.tokens and r.tokens > 0:
            n_with_tokens += 1
        if r.created_at and r.created_at >= cutoff:
            last_7d += c
        m = by_model.setdefault(r.model_id, {"model_id": r.model_id, "n_resp": 0, "tokens": 0, "cost_usd": 0.0})
        m["n_resp"] += 1
        m["tokens"] += r.tokens or 0
        m["cost_usd"] += c

    by_model_list = sorted(by_model.values(), key=lambda x: x["cost_usd"], reverse=True)
    return {
        "cost_total_usd": round(total, 4),
        "cost_last_7d_usd": round(last_7d, 4),
        "n_responses_with_tokens": n_with_tokens,
        "cost_by_model": by_model_list,
    }


def run_history(limit: int = 100) -> pd.DataFrame:
    """Storico delle run con metriche aggregate per ognuna.

    Colonne: run_id, started_at, finished_at, durata_s, trigger_type, n_responses,
    n_success, cost_usd_stimato.
    "n_success" qui = n risposte non-vuote (proxy: tokens > 0 OR text non vuoto).
    """
    from src.cost import estimate_cost, load_model_pricing

    pricing = load_model_pricing()
    with get_session() as s:
        runs = list(
            s.scalars(select(Run).order_by(Run.started_at.desc()).limit(limit)).all()
        )
        rows = []
        for run in runs:
            resps = list(s.scalars(select(Response).where(Response.run_id == run.id)).all())
            n_resp = len(resps)
            n_success = sum(1 for r in resps if (r.text or "").strip() and (r.tokens or 0) > 0)
            cost = sum(
                estimate_cost(r.model_id, r.tokens or 0, has_web_search=True, pricing=pricing)
                for r in resps
            )
            duration = None
            if run.finished_at and run.started_at:
                duration = (run.finished_at - run.started_at).total_seconds()
            rows.append({
                "run_id": run.id,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "durata_s": duration,
                "trigger_type": run.trigger_type,
                "n_responses": n_resp,
                "n_success": n_success,
                "cost_usd": round(cost, 4),
            })
    return pd.DataFrame(rows)


def top_prompts_by_cost(limit: int = 10) -> pd.DataFrame:
    """Prompt con costo cumulativo più alto."""
    from src.cost import estimate_cost, load_model_pricing

    pricing = load_model_pricing()
    with get_session() as s:
        prompts = list(s.scalars(select(Prompt)).all())
        rows = []
        for p in prompts:
            resps = list(s.scalars(select(Response).where(Response.prompt_id == p.id)).all())
            if not resps:
                continue
            cost = sum(
                estimate_cost(r.model_id, r.tokens or 0, has_web_search=True, pricing=pricing)
                for r in resps
            )
            rows.append({
                "prompt_id": p.id,
                "prompt": p.text,
                "n_resp": len(resps),
                "cost_usd": round(cost, 4),
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("cost_usd", ascending=False).head(limit)


def fmt_usd(x: float | None) -> str:
    if x is None:
        return "—"
    if abs(x) < 0.01:
        return f"${x*100:.2f}¢"
    return f"${x:.2f}"


def truncate(text: str, n: int = 90) -> str:
    if not text:
        return ""
    text = text.strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def highlight_brands_html(text: str) -> str:
    """Restituisce HTML formattato (Markdown renderizzato) con brand evidenziati.

    Pipeline:
    1. Markdown → HTML (lib `markdown`) con tabelle, liste, link, code, headings
    2. BeautifulSoup parsing dell'HTML
    3. Applica brand highlight SOLO sui text nodes (non rompe href, code, ecc.)
    4. Forza target="_blank" + collassa newline interni che confonderebbero Streamlit

    Target = verde, competitor = arancione.
    """
    if not text:
        return ""

    import html as _html
    import markdown as _md
    from bs4 import BeautifulSoup, NavigableString

    # 1) Markdown → HTML
    html_text = _md.markdown(
        text,
        extensions=["extra", "nl2br", "sane_lists"],
        output_format="html5",
    )

    # 2) Brand aliases (desc per lunghezza)
    idx = load_brand_index()
    aliases: list[tuple[str, bool]] = []
    for b in idx.brands:
        for a in b.aliases:
            aliases.append((a, b.is_target))
    aliases.sort(key=lambda x: len(x[0]), reverse=True)

    target_color = "#16a34a"
    comp_color = "#f97316"

    soup = BeautifulSoup(html_text, "html.parser")

    def _highlight_node(node: NavigableString) -> None:
        # Salta dentro a tag che NON vogliamo toccare
        parent = node.parent.name if node.parent else None
        if parent in ("a", "code", "pre", "script", "style"):
            return
        original = str(node)
        replaced = _html.escape(original)
        changed = False
        for alias, is_target in aliases:
            color = target_color if is_target else comp_color
            weight = "700" if is_target else "600"
            esc_alias = _html.escape(alias)
            pattern = re.compile(rf"(?<!\w){re.escape(esc_alias)}(?!\w)")
            new_rep, n = pattern.subn(
                f'<span style="background:{color}22;color:{color};'
                f'padding:1px 4px;border-radius:3px;font-weight:{weight}">'
                f'{esc_alias}</span>',
                replaced,
            )
            if n:
                changed = True
                replaced = new_rep
        if changed:
            node.replace_with(BeautifulSoup(replaced, "html.parser"))

    for node in list(soup.find_all(string=True)):
        if isinstance(node, NavigableString):
            _highlight_node(node)

    # Forza target="_blank" sui link
    for a in soup.find_all("a"):
        a["target"] = "_blank"
        a["rel"] = "noopener noreferrer"

    # Stringify e collassa newline (Streamlit interpreta \n\n come fine paragrafo
    # markdown — spezzerebbe la card che contiene l'HTML)
    out = str(soup)
    out = out.replace("\n", "")  # safe perché Markdown ha già messo i <br> dove serve
    return out
