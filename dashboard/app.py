"""LLM Visibility Tracker — Streamlit entry point.

Avvio:
    streamlit run dashboard/app.py
"""
from __future__ import annotations

import streamlit as st

from dashboard.utils import global_kpis, fmt_pct

st.set_page_config(
    page_title="LLM Visibility Tracker",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 LLM Visibility Tracker")
st.caption("Monitora la presenza di **talentgarden.com** nelle risposte degli LLM con web search attivo.")

kpis = global_kpis()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Citation rate", fmt_pct(kpis["citation_rate"]),
          help="% di risposte in cui talentgarden.com è citato come fonte")
c2.metric("Mention rate", fmt_pct(kpis["mention_rate"]),
          help="% di risposte in cui Talent Garden è menzionato nel testo")
c3.metric("Share of citations", fmt_pct(kpis["share_of_citations"]),
          help="Quota delle citazioni totali che vanno verso talentgarden.com")
c4.metric("Citation gap", fmt_pct(kpis["citation_gap"]),
          help="% di risposte in cui il brand è menzionato ma il sito non è citato")

st.divider()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Prompt totali", kpis["n_prompts"])
c2.metric("Prompt attivi", kpis["n_active"])
c3.metric("Risposte raccolte", kpis["n_responses"])
c4.metric("Run eseguite", kpis["n_runs"])

st.divider()

st.markdown("""
### Naviga
- **Overview** — KPI globali e trend
- **Prompts** — lista, aggiungi, modifica i prompt monitorati
- **Prompt Detail** — risposte per modello, citazioni evidenziate
- **Citations** — esplora tutte le URL citate (target / competitor / altro)
- **Models** — confronto performance dei modelli LLM
""")

st.markdown("---")
st.caption("Per lanciare un batch da terminale: `python -m scripts.run_batch --repeat 3`")
