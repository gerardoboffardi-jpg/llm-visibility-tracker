"""Models — confronto performance dei modelli LLM."""
from __future__ import annotations

import streamlit as st

from dashboard.utils import model_aggregates

st.set_page_config(page_title="Models", page_icon="🤖", layout="wide")
st.title("🤖 Models")
st.caption("Confronto delle performance dei modelli LLM monitorati.")

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
