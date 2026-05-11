"""LLM Visibility Tracker — Streamlit entry point.

Avvio locale:
    streamlit run dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from dashboard.auth import require_password
from dashboard.utils import fmt_pct, global_kpis

st.set_page_config(
    page_title="LLM Visibility — Talent Garden",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not require_password():
    st.stop()

# ---------------- Sidebar ----------------
with st.sidebar:
    st.markdown("### 🔍 LLM Visibility")
    st.caption("Talent Garden")
    st.markdown("---")
    st.caption(
        "Monitora la visibilità di **talentgarden.com** "
        "nelle risposte degli LLM con web search attivo "
        "(ChatGPT, Perplexity, Claude, Gemini)."
    )

# ---------------- Hero ----------------
kpis = global_kpis()
cit_rate = kpis["citation_rate"]
trend_color = "#16a34a" if cit_rate >= 0.30 else ("#f59e0b" if cit_rate >= 0.15 else "#dc2626")

st.markdown(
    f"""
    <div style="text-align:center;padding:24px 12px 12px">
        <div style="font-size:0.85rem;color:#64748b;letter-spacing:0.05em;
                    text-transform:uppercase;font-weight:600">
            Citation rate complessiva
        </div>
        <div style="font-size:4rem;font-weight:700;color:{trend_color};
                    line-height:1;margin:8px 0">
            {fmt_pct(cit_rate)}
        </div>
        <div style="color:#64748b;max-width:560px;margin:0 auto">
            <strong>talentgarden.com</strong> è citato come fonte
            nel {fmt_pct(cit_rate)} delle risposte degli LLM monitorati
            ({kpis['n_responses']} risposte su {kpis['n_prompts']} prompt).
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("")

# ---------------- KPI secondari ----------------
c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Mention rate", fmt_pct(kpis["mention_rate"]),
    help="% di risposte in cui Talent Garden è menzionato nel testo",
)
c2.metric(
    "Share of citations", fmt_pct(kpis["share_of_citations"]),
    help="Quota delle citazioni totali che vanno verso talentgarden.com",
)
c3.metric(
    "Citation gap", fmt_pct(kpis["citation_gap"]),
    help="Menzionato ma non citato → opportunità SEO",
    delta="opportunità SEO" if kpis["citation_gap"] > 0 else None,
    delta_color="off",
)
c4.metric(
    "Citazioni TG", kpis["n_target_citations"],
    help="Numero totale di URL talentgarden.com citate",
)

st.divider()

# ---------------- Volume ----------------
v1, v2, v3, v4 = st.columns(4)
v1.metric("📝 Prompt totali", kpis["n_prompts"])
v2.metric("✅ Prompt attivi", kpis["n_active"])
v3.metric("💬 Risposte", kpis["n_responses"])
v4.metric("🔄 Run", kpis["n_runs"])

st.markdown("")

# ---------------- Onboarding empty state ----------------
if kpis["n_responses"] == 0:
    st.info(
        "**Benvenuto!** Non ci sono ancora risposte raccolte.\n\n"
        "1. Vai su **📝 Prompts** e verifica la lista (30 prompt già caricati)\n"
        "2. Lancia un batch dal terminale: `python -m scripts.run_batch --repeat 1`\n"
        "3. Torna qui per vedere i risultati",
        icon="👋",
    )
else:
    st.markdown(
        """
        ### Esplora i dati
        - **📊 Overview** — top prompt, citation gap, trend nel tempo
        - **📝 Prompt** — gestisci la lista, aggiungi nuovi prompt
        - **🔬 Prompt Detail** — leggi le risposte degli LLM con i brand evidenziati
        - **🔗 Citations** — esplora le URL citate (target, competitor, fonti neutre)
        - **🤖 Models** — confronta le performance dei modelli LLM
        """
    )

st.markdown("---")
st.caption(
    "💡 Per lanciare un batch settimanale: vedi `.github/workflows/weekly_batch.yml`"
)
