"""Citations — esplora tutte le URL citate aggregate."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st
from sqlalchemy import func, select

from dashboard.auth import require_password
from dashboard.utils import domain_aggregates
from src.storage import Citation, Response, get_session

st.set_page_config(page_title="Citations", page_icon="🔗", layout="wide")
if not require_password():
    st.stop()

st.title("🔗 Citations Explorer")

st.caption("Esplora tutte le URL citate dagli LLM. Le citazioni sono cittadini di prima classe in questa dashboard.")

dom = domain_aggregates()
if dom.empty:
    st.info("Nessuna citazione raccolta ancora.")
    st.stop()

tab_top, tab_target, tab_comp, tab_other = st.tabs([
    "🌐 Top domini", "🟢 Citazioni TARGET", "🟠 Competitor", "⚪ Altri"
])

# --- TOP DOMAINS -------------------------------------------------------------
with tab_top:
    st.subheader("Top domini citati")
    st.dataframe(
        dom,
        column_config={
            "domain": st.column_config.TextColumn("Dominio", width="medium"),
            "category": st.column_config.TextColumn("Categoria", width="small"),
            "n_citations": st.column_config.NumberColumn("# citazioni"),
            "n_prompts": st.column_config.NumberColumn("# prompt unici"),
            "n_models": st.column_config.NumberColumn("# modelli"),
        },
        hide_index=True, use_container_width=True, height=500,
    )

# Helper per estrarre URL specifiche di una categoria
def _urls_for(category: str) -> pd.DataFrame:
    with get_session() as s:
        cond = []
        if category == "target":
            cond.append(Citation.is_target_domain.is_(True))
        elif category == "competitor":
            cond.append(Citation.is_competitor_domain.is_(True))
        else:  # other
            cond.append(Citation.is_target_domain.is_(False))
            cond.append(Citation.is_competitor_domain.is_(False))

        stmt = (
            select(
                Citation.url,
                Citation.domain,
                Citation.page_title,
                func.count(Citation.id).label("n_citations"),
                func.count(func.distinct(Response.prompt_id)).label("n_prompts"),
                func.count(func.distinct(Response.model_id)).label("n_models"),
                func.avg(Citation.position).label("avg_position"),
            )
            .join(Response, Response.id == Citation.response_id)
            .where(*cond)
            .group_by(Citation.url, Citation.domain, Citation.page_title)
            .order_by(func.count(Citation.id).desc())
        )
        rows = [dict(r._mapping) for r in s.execute(stmt).all()]
    return pd.DataFrame(rows)


# --- TARGET ------------------------------------------------------------------
with tab_target:
    st.subheader("URL specifiche di talentgarden.com")
    st.caption("Le pagine che gli LLM citano più spesso → contenuti 'magneti per LLM'.")
    df = _urls_for("target")
    if df.empty:
        st.info("Nessuna citazione target ancora.")
    else:
        st.dataframe(
            df,
            column_config={
                "url": st.column_config.LinkColumn("URL", width="large"),
                "domain": "Dominio",
                "page_title": "Titolo pagina",
                "n_citations": st.column_config.NumberColumn("# cit.", width="small"),
                "n_prompts": st.column_config.NumberColumn("# prompt", width="small"),
                "n_models": st.column_config.NumberColumn("# modelli", width="small"),
                "avg_position": st.column_config.NumberColumn(
                    "Pos. media", format="%.1f", width="small",
                ),
            },
            hide_index=True, use_container_width=True, height=500,
        )

# --- COMPETITOR --------------------------------------------------------------
with tab_comp:
    st.subheader("URL dei competitor citate dagli LLM")
    st.caption("Quali pagine dei competitor performano bene? Spunti per benchmarking.")
    df = _urls_for("competitor")
    if df.empty:
        st.info("Nessuna citazione competitor.")
    else:
        st.dataframe(
            df,
            column_config={
                "url": st.column_config.LinkColumn("URL", width="large"),
                "domain": "Dominio",
                "page_title": "Titolo",
                "n_citations": st.column_config.NumberColumn("# cit."),
                "n_prompts": st.column_config.NumberColumn("# prompt"),
                "n_models": st.column_config.NumberColumn("# modelli"),
                "avg_position": st.column_config.NumberColumn("Pos. media", format="%.1f"),
            },
            hide_index=True, use_container_width=True, height=500,
        )

# --- OTHER -------------------------------------------------------------------
with tab_other:
    st.subheader("Domini neutri ricorrenti")
    st.caption(
        "Wikipedia, magazine, directory che vengono citate spesso → opportunità di "
        "guest post, link building, citation building."
    )
    df = _urls_for("other")
    if df.empty:
        st.info("Nessun dominio 'other'.")
    else:
        # Aggrega per dominio (non per URL specifico)
        agg = df.groupby("domain").agg(
            n_citations=("n_citations", "sum"),
            n_prompts=("n_prompts", "sum"),
            n_models=("n_models", "max"),
        ).reset_index().sort_values("n_citations", ascending=False)
        st.dataframe(
            agg,
            column_config={
                "domain": st.column_config.TextColumn("Dominio", width="medium"),
                "n_citations": st.column_config.NumberColumn("# citazioni"),
                "n_prompts": st.column_config.NumberColumn("# prompt unici"),
                "n_models": st.column_config.NumberColumn("# modelli"),
            },
            hide_index=True, use_container_width=True, height=500,
        )
