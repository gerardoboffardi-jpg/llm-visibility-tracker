"""📊 Overview — KPI, top prompt, gap, trend, domain mix."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st
from sqlalchemy import Integer, func, select

from dashboard.auth import require_password
from dashboard.utils import (
    domain_aggregates,
    fmt_pct,
    global_kpis,
    prompts_overview_df,
)
from src.storage import Response, get_session

st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")
if not require_password():
    st.stop()

st.title("📊 Overview")
st.caption("Vista aggregata su tutti i prompt monitorati.")

kpis = global_kpis()

if kpis["n_responses"] == 0:
    st.info("Nessuna risposta raccolta ancora. Esegui `python -m scripts.run_batch --repeat 1` per iniziare.", icon="ℹ️")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("⭐ Citation rate", fmt_pct(kpis["citation_rate"]))
c2.metric("💬 Mention rate", fmt_pct(kpis["mention_rate"]))
c3.metric("📊 Share of citations", fmt_pct(kpis["share_of_citations"]))
c4.metric("⚠️ Citation gap", fmt_pct(kpis["citation_gap"]))

st.divider()

# ---------------- Top + Gap ----------------
df = prompts_overview_df()
df_with_data = df[df["n_risposte"] > 0].copy()

col1, col2 = st.columns(2)

with col1:
    st.subheader("🏆 Top 10 prompt per citation rate")
    st.caption("I prompt dove talentgarden.com viene citato più spesso.")
    top = df_with_data.sort_values("citation_rate", ascending=False).head(10)
    if top.empty:
        st.info("Nessuna run ancora disponibile.")
    else:
        st.dataframe(
            top[["prompt", "citation_rate", "mention_rate", "n_risposte"]],
            column_config={
                "prompt": st.column_config.TextColumn("Prompt", width="large"),
                "citation_rate": st.column_config.ProgressColumn(
                    "Citation", format="%.0f%%", min_value=0, max_value=1,
                ),
                "mention_rate": st.column_config.ProgressColumn(
                    "Mention", format="%.0f%%", min_value=0, max_value=1,
                ),
                "n_risposte": st.column_config.NumberColumn("# risp.", width="small"),
            },
            hide_index=True, use_container_width=True, height=420,
        )

with col2:
    st.subheader("⚠️ Top citation gap")
    st.caption("Prompt dove il brand è menzionato ma il sito **non** è citato → opportunità SEO.")
    gap = df_with_data.copy()
    gap["gap"] = (gap["mention_rate"].fillna(0) - gap["citation_rate"].fillna(0)).clip(lower=0)
    gap = gap[gap["gap"] > 0].sort_values("gap", ascending=False).head(10)
    if gap.empty:
        st.success("Nessun citation gap rilevato 🎉")
    else:
        st.dataframe(
            gap[["prompt", "mention_rate", "citation_rate", "gap"]],
            column_config={
                "prompt": st.column_config.TextColumn("Prompt", width="large"),
                "mention_rate": st.column_config.ProgressColumn(
                    "Mention", format="%.0f%%", min_value=0, max_value=1,
                ),
                "citation_rate": st.column_config.ProgressColumn(
                    "Citation", format="%.0f%%", min_value=0, max_value=1,
                ),
                "gap": st.column_config.ProgressColumn(
                    "Gap", format="%.0f%%", min_value=0, max_value=1,
                ),
            },
            hide_index=True, use_container_width=True, height=420,
        )

st.divider()

# ---------------- Domain mix ----------------
st.subheader("🌐 Domain mix delle citazioni")
dom = domain_aggregates()
if dom.empty:
    st.info("Nessuna citazione raccolta.")
else:
    summary = dom.groupby("category")["n_citations"].sum().reset_index()
    # Ordine fisso e colori semaforici
    order = ["target", "competitor", "other"]
    summary["category"] = pd.Categorical(summary["category"], categories=order, ordered=True)
    summary = summary.sort_values("category")

    c1, c2 = st.columns([1, 2])
    with c1:
        st.dataframe(
            summary.rename(columns={"category": "Categoria", "n_citations": "Citazioni"}),
            hide_index=True, use_container_width=True,
        )
        total = summary["n_citations"].sum()
        for _, row in summary.iterrows():
            pct = (row["n_citations"] / total) if total else 0
            label = {"target": "🟢 TARGET", "competitor": "🟠 Competitor", "other": "⚪ Altri"}[row["category"]]
            st.markdown(f"{label}: **{fmt_pct(pct)}**")
    with c2:
        st.bar_chart(
            summary.set_index("category")["n_citations"],
            color="#E94E1B",
            height=300,
        )

st.divider()

# ---------------- Trend ----------------
st.subheader("📈 Trend citation rate nel tempo")
with get_session() as s:
    stmt = (
        select(
            func.date(Response.created_at).label("day"),
            func.count(Response.id).label("n_resp"),
            func.sum(
                func.coalesce(Response.has_target_citation.cast(Integer), 0)
            ).label("n_cit"),
        )
        .group_by(func.date(Response.created_at))
        .order_by(func.date(Response.created_at))
    )
    rows = [dict(r._mapping) for r in s.execute(stmt).all()]
trend = pd.DataFrame(rows)
if trend.empty or len(trend) < 2:
    st.info("Servono almeno 2 giorni di dati per vedere il trend.")
else:
    trend["citation_rate"] = trend["n_cit"] / trend["n_resp"]
    st.line_chart(trend.set_index("day")["citation_rate"], color="#E94E1B", height=280)
