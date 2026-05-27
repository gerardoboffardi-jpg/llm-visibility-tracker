"""Models — confronto performance dei modelli LLM."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from dashboard.auth import require_password
from dashboard.style import apply_style, model_avatar, model_meta, page_header, render_sidebar
from dashboard.utils import model_aggregates

st.set_page_config(page_title="Models", page_icon="🤖", layout="wide")
apply_style()
if not require_password():
    st.stop()

render_sidebar()

page_header(
    icon="🤖",
    title="Models",
    sub="Confronto delle performance dei modelli LLM monitorati.",
)

df = model_aggregates()
if df.empty:
    st.info("Nessuna risposta raccolta ancora. Esegui un batch.")
    st.stop()

st.dataframe(
    df[["model_id", "n_responses", "citation_rate", "mention_rate",
        "avg_total_citations", "avg_latency_ms"]],
    column_config={
        "model_id": "Modello",
        "n_responses": st.column_config.NumberColumn("# risposte"),
        "citation_rate": st.column_config.ProgressColumn(
            "Citation rate ⭐", format="%.1f%%", min_value=0, max_value=1,
        ),
        "mention_rate": st.column_config.ProgressColumn(
            "Mention rate", format="%.1f%%", min_value=0, max_value=1,
        ),
        "avg_total_citations": st.column_config.NumberColumn("Avg # cit/risp", format="%.1f"),
        "avg_latency_ms": st.column_config.NumberColumn("Latency media (ms)", format="%.0f"),
    },
    hide_index=True, use_container_width=True,
)

st.divider()
st.markdown("### Configurazione modelli")
st.markdown("Edita `config/models.yaml` per attivare/disattivare modelli o aggiungerne di nuovi.")
st.code("""
# Esempio
- id: perplexity-sonar
  provider: perplexity
  model: sonar
  web_search: true
  enabled: true
""", language="yaml")
