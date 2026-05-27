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
from dashboard.style import (
    CORAL,
    GREEN,
    ORANGE,
    apply_style,
    badge,
    render_chat_response,
    render_sidebar,
    section_header,
)
from dashboard.utils import (
    cost_aggregates,
    fmt_dt,
    fmt_pct,
    fmt_usd,
    global_kpis,
    highlight_brands_html,
    recent_responses_feed,
    truncate,
)

st.set_page_config(
    page_title="LLM Visibility — Talent Garden",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_style()

if not require_password():
    st.stop()

# ---------------- Hero stile HubSpot AEO ----------------
kpis = global_kpis()
cost_agg = cost_aggregates()

# Sidebar con KPI corrente (citation rate + cost & run)
render_sidebar(
    current_kpi_label=f"{kpis['n_responses']} risposte · {kpis['n_prompts']} prompt",
    current_kpi_value=fmt_pct(kpis['citation_rate']),
    cost_usd=cost_agg["cost_total_usd"],
    n_runs=kpis["n_runs"],
)
cit_rate = kpis["citation_rate"]
men_rate = kpis["mention_rate"]
share = kpis["share_of_citations"]
gap = kpis["citation_gap"]

# Color per il numero principale
if cit_rate >= 0.30:
    primary_color_class = "green"
elif cit_rate >= 0.15:
    primary_color_class = "orange"
else:
    primary_color_class = "coral"

st.markdown(
    f"""
    <div class="tag-hero">
        <span class="tag-eyebrow">LLM Visibility · Talent Garden</span>
        <h1 class="tag-h1">
            Quanto è visibile Talent Garden<br/>nelle risposte degli <span class="accent">LLM</span>?
        </h1>
        <p class="tag-sub">
            Monitora come ChatGPT, Perplexity, Claude e Gemini citano
            <strong>talentgarden.com</strong> quando rispondono a domande reali su
            coworking, formazione e innovation. Scopri dove sei già citato,
            dove sei menzionato ma non linkato (citation gap), e dove i competitor ti battono.
        </p>
        <div class="tag-kpi-row">
            <div class="tag-kpi">
                <div class="tag-kpi-label">Citation rate</div>
                <div class="tag-kpi-value {primary_color_class}">{fmt_pct(cit_rate)}</div>
                <div class="tag-kpi-hint">{kpis['n_responses']} risposte · {kpis['n_prompts']} prompt</div>
            </div>
            <div class="tag-kpi">
                <div class="tag-kpi-label">Mention rate</div>
                <div class="tag-kpi-value">{fmt_pct(men_rate)}</div>
                <div class="tag-kpi-hint">Brand citato nel testo</div>
            </div>
            <div class="tag-kpi">
                <div class="tag-kpi-label">Share of citations</div>
                <div class="tag-kpi-value">{fmt_pct(share)}</div>
                <div class="tag-kpi-hint">Su {kpis['n_total_citations']} citazioni totali</div>
            </div>
            <div class="tag-kpi">
                <div class="tag-kpi-label">Citation gap</div>
                <div class="tag-kpi-value orange">{fmt_pct(gap)}</div>
                <div class="tag-kpi-hint">Opportunità SEO</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------- Onboarding empty state ----------------
if kpis["n_responses"] == 0:
    st.info(
        "**Benvenuto!** Non ci sono ancora risposte raccolte.\n\n"
        "1. Vai su **📝 Prompts** e verifica la lista (30 prompt già caricati)\n"
        "2. Lancia un batch dal terminale: `python -m scripts.run_batch --repeat 1`\n"
        "3. Torna qui per vedere i risultati",
        icon="👋",
    )
    st.stop()

# ---------------- Volume snapshot ----------------
section_header(
    eyebrow="Volume monitorato",
    title="Cosa stiamo tracciando",
    sub="Il perimetro dei prompt, modelli e run su cui calcoliamo le metriche di visibility.",
)
v1, v2, v3, v4 = st.columns(4)
v1.metric("📝 Prompt totali", kpis["n_prompts"])
v2.metric("✅ Prompt attivi", kpis["n_active"])
v3.metric("💬 Risposte", kpis["n_responses"])
v4.metric("🔄 Run", kpis["n_runs"])

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

# ---------------- Cost & Run snapshot ----------------
section_header(
    eyebrow="Costi & Run",
    title="Quanto ci stiamo spendendo",
    sub="Stima USD basata sui token consumati × pricing modello. "
        "Per dettaglio vai su 💰 Costi & Run.",
)
avg_cost_per_run = (cost_agg["cost_total_usd"] / kpis["n_runs"]) if kpis["n_runs"] else 0.0
k1, k2, k3, k4 = st.columns(4)
k1.metric("💰 Costo totale", fmt_usd(cost_agg["cost_total_usd"]))
k2.metric("📅 Ultimi 7 gg", fmt_usd(cost_agg["cost_last_7d_usd"]))
k3.metric("💸 Costo / run", fmt_usd(avg_cost_per_run))
k4.metric(
    "🏃 Run totali", kpis["n_runs"],
    help="Numero di batch eseguiti (manuali + scheduled + API).",
)

# Mini breakdown per modello (top 3)
if cost_agg["cost_by_model"]:
    st.markdown(
        "<div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:8px'>",
        unsafe_allow_html=True,
    )
    for m in cost_agg["cost_by_model"][:4]:
        from dashboard.style import model_avatar, model_meta
        name = model_meta(m["model_id"])[0]
        st.markdown(
            f"""
            <div class="tag-engine-card" style="flex:1;min-width:200px">
                {model_avatar(m["model_id"])}
                <div>
                    <div class="tag-engine-name">{name}</div>
                    <div class="tag-engine-stat">
                        <strong style="color:{CORAL}">{fmt_usd(m["cost_usd"])}</strong>
                        · {m["n_resp"]} risposte
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

# ---------------- Ultime risposte LLM (preview) ----------------
section_header(
    eyebrow="Cosa dicono gli LLM",
    title="Ultime risposte raccolte",
    sub="Le risposte più recenti degli LLM, con brand evidenziati. "
        "Vai su 💬 Risposte per il feed completo con filtri.",
)

recent = recent_responses_feed(limit=3)
if not recent:
    st.info("Nessuna risposta ancora.")
else:
    for r in recent:
        # Preview limita il testo per non saturare l'home
        text_preview = r["text"][:600].rstrip()
        if len(r["text"]) > 600:
            text_preview += " …"
        body_html = highlight_brands_html(text_preview)

        st.markdown(
            f'<div style="margin-top:8px;font-size:0.88rem">'
            f'<a href="/Prompt_Detail?prompt_id={r["prompt_id"]}" '
            f'style="color:#0F172A;font-weight:600">'
            f'🔬 Prompt #{r["prompt_id"]} — {truncate(r["prompt_text"], 90)}</a>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            render_chat_response(
                model_id=r["model_id"],
                prompt_text=r["prompt_text"],
                response_text_html=body_html,
                created_at_str=fmt_dt(r["created_at"]),
                has_target_mention=r["has_target_mention"],
                has_target_citation=r["has_target_citation"],
            ),
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<div style='text-align:center;margin-top:8px'>"
        f"<a href='/Risposte' style='color:{CORAL};font-weight:600'>"
        f"Vedi tutte le risposte →</a></div>",
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)

# ---------------- Quick nav (card cliccabili) ----------------
section_header(
    eyebrow="Esplora",
    title="Dove andare",
    sub="Le viste principali della dashboard — clicca per aprirla.",
)


def _nav_card(href: str, icon: str, title: str, desc: str) -> str:
    """HTML di una card di navigazione cliccabile."""
    return (
        f'<a href="{href}" target="_self" class="tag-nav-card">'
        f'<div class="tag-nav-card-icon">{icon}</div>'
        f'<div class="tag-nav-card-title">{title}</div>'
        f'<div class="tag-nav-card-desc">{desc}</div>'
        f'</a>'
    )


nav_cards = [
    ("/Overview",      "📊", "Overview",
     "KPI complessivi, top prompt, citation gap, trend."),
    ("/Risposte",      "💬", "Risposte",
     "Feed di tutte le risposte LLM con filtri e brand evidenziati."),
    ("/Prompt_Detail", "🔬", "Prompt Detail",
     "Approfondisci un singolo prompt: tutte le risposte e citazioni."),
    ("/Prompts",       "📝", "Prompts",
     "Gestisci la lista dei prompt monitorati."),
    ("/Citations",     "🔗", "Citations",
     "URL citate dagli LLM: target, competitor, fonti neutre."),
    ("/Models",        "🤖", "Models",
     "Confronta performance dei modelli LLM."),
    ("/Costi_e_Run",   "💰", "Costi & Run",
     "Controllo spesa LLM + storico esecuzioni."),
    ("/Recommendations", "🎯", "Recommendations",
     "Suggerimenti AEO/SEO per chiudere il citation gap."),
]

# Layout a griglia 4 colonne (8 card su 2 righe). Tutto in un solo
# st.markdown per evitare che ogni iteration prenda padding diverso.
cards_html = '<div class="tag-nav-grid">'
for href, icon, title, desc in nav_cards:
    cards_html += _nav_card(href, icon, title, desc)
cards_html += "</div>"
st.markdown(cards_html, unsafe_allow_html=True)

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
st.caption(
    "💡 Batch settimanale automatico: vedi `.github/workflows/weekly_batch.yml` · "
    "manuale: `python -m scripts.run_batch --repeat 1`"
)
