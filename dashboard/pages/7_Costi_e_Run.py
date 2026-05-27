"""💰 Costi & Run — monitor spese LLM + storico esecuzioni."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

from dashboard.auth import require_password
from dashboard.style import (
    CORAL,
    apply_style,
    model_avatar,
    model_meta,
    page_header,
    render_sidebar,
    section_header,
)
from dashboard.utils import (
    cost_aggregates,
    fmt_dt,
    fmt_usd,
    run_history,
    top_prompts_by_cost,
)

st.set_page_config(page_title="Costi & Run", page_icon="💰", layout="wide")
apply_style()
if not require_password():
    st.stop()

render_sidebar()

page_header(
    icon="💰",
    title="Costi & Run",
    sub="Monitor della spesa LLM e dello storico esecuzioni. "
        "Stima USD basata sui token consumati × pricing in config/models.yaml.",
)

# ---------------- KPI hero ----------------
agg = cost_aggregates()
runs_df = run_history(limit=200)

n_runs = len(runs_df)
total_resp = int(runs_df["n_responses"].sum()) if not runs_df.empty else 0
avg_cost_per_run = (agg["cost_total_usd"] / n_runs) if n_runs else 0.0
cost_per_response = (agg["cost_total_usd"] / total_resp) if total_resp else 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 Costo totale", fmt_usd(agg["cost_total_usd"]))
c2.metric("📅 Ultimi 7 giorni", fmt_usd(agg["cost_last_7d_usd"]))
c3.metric("🏃 Run totali", n_runs)
c4.metric("💸 Costo / run", fmt_usd(avg_cost_per_run))

c1, c2, c3, c4 = st.columns(4)
c1.metric("💬 Risposte totali", total_resp)
c2.metric("Risposte con token", agg["n_responses_with_tokens"])
c3.metric("Costo / risposta", fmt_usd(cost_per_response))
c4.metric(
    "Token tracking",
    f"{agg['n_responses_with_tokens']}/{total_resp}" if total_resp else "—",
    help="Solo le risposte con count token valorizzato finiscono nella stima.",
)

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ---------------- Costo per modello ----------------
section_header(
    eyebrow="Cost breakdown",
    title="Costo per modello",
    sub="Quale engine sta consumando il budget? Stima basata su token × prezzo provider.",
)

if not agg["cost_by_model"]:
    st.info("Nessuna risposta con token valorizzati ancora.")
else:
    df_models = pd.DataFrame(agg["cost_by_model"])
    df_models["display_name"] = df_models["model_id"].apply(lambda m: model_meta(m)[0])

    # Card per modello + barra
    cols = st.columns(min(len(df_models), 4))
    max_cost = float(df_models["cost_usd"].max()) or 1.0
    for i, row in enumerate(df_models.itertuples()):
        col = cols[i % len(cols)]
        with col:
            pct = (row.cost_usd / max_cost) * 100 if max_cost else 0
            st.markdown(
                f"""
                <div class="tag-engine-card" style="flex-direction:column;align-items:flex-start;gap:8px">
                    <div style="display:flex;align-items:center;gap:10px;width:100%">
                        {model_avatar(row.model_id)}
                        <div>
                            <div class="tag-engine-name">{row.display_name}</div>
                            <div class="tag-engine-stat">{row.n_resp} risposte · {row.tokens:,} token</div>
                        </div>
                    </div>
                    <div style="font-size:1.4rem;font-weight:700;color:{CORAL};line-height:1">
                        {fmt_usd(row.cost_usd)}
                    </div>
                    <div style="background:#F1F5F9;border-radius:999px;height:6px;width:100%;overflow:hidden">
                        <div style="background:{CORAL};height:100%;width:{pct:.1f}%"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

# ---------------- Storico Run ----------------
section_header(
    eyebrow="Cronologia",
    title="Ultime 200 run",
    sub="Ogni run = un batch di esecuzione (manuale, scheduled o triggerata via API).",
)

if runs_df.empty:
    st.info("Nessuna run ancora.")
else:
    # Calcola tasso successo (proxy)
    runs_df["success_rate"] = (
        runs_df["n_success"] / runs_df["n_responses"].replace(0, 1)
    ).where(runs_df["n_responses"] > 0, 0)

    st.dataframe(
        runs_df,
        column_config={
            "run_id": st.column_config.NumberColumn("ID", width="small"),
            "started_at": st.column_config.DatetimeColumn(
                "Inizio", format="YYYY-MM-DD HH:mm", width="medium",
            ),
            "finished_at": st.column_config.DatetimeColumn(
                "Fine", format="YYYY-MM-DD HH:mm", width="medium",
            ),
            "durata_s": st.column_config.NumberColumn(
                "Durata (s)", format="%.0f", width="small",
            ),
            "trigger_type": st.column_config.TextColumn("Trigger", width="small"),
            "n_responses": st.column_config.NumberColumn("# risp.", width="small"),
            "n_success": st.column_config.NumberColumn("# ok", width="small"),
            "success_rate": st.column_config.ProgressColumn(
                "Successo", format="%.0f%%", min_value=0, max_value=1, width="small",
            ),
            "cost_usd": st.column_config.NumberColumn(
                "Costo (USD)", format="$%.4f", width="small",
            ),
        },
        hide_index=True,
        use_container_width=True,
        height=520,
    )

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

# ---------------- Top prompt più costosi ----------------
section_header(
    eyebrow="Drill-down",
    title="Top 10 prompt più costosi",
    sub="I prompt che hanno generato più spesa cumulata (più run × più modelli × più token).",
)

top_costly = top_prompts_by_cost(limit=10)
if top_costly.empty:
    st.info("Nessun dato.")
else:
    st.dataframe(
        top_costly,
        column_config={
            "prompt_id": st.column_config.NumberColumn("ID", width="small"),
            "prompt": st.column_config.TextColumn("Prompt", width="large"),
            "n_resp": st.column_config.NumberColumn("# risp.", width="small"),
            "cost_usd": st.column_config.NumberColumn(
                "Costo (USD)", format="$%.4f", width="small",
            ),
        },
        hide_index=True,
        use_container_width=True,
    )

# ---------------- Note pricing ----------------
with st.expander("ℹ️ Come funziona la stima costi"):
    st.markdown(
        """
        - **Pricing** è definito in `config/models.yaml` (campi `input_price_per_1m`,
          `output_price_per_1m`, `web_search_price`). Modifica quel file per aggiornare
          i prezzi dei provider.
        - **Token split**: usiamo un'euristica 70% input / 30% output sul totale
          `Response.tokens` salvato in DB. Se in futuro salveremo input/output split,
          la stima diventa esatta.
        - **Web search**: aggiunto come costo fisso per chiamata se il modello ha
          `web_search: true`. Per Anthropic = $0.010, OpenAI = $0.030, Gemini = $0.000,
          Perplexity = $0.005 (incluso nei modelli sonar).
        - **Sottostima possibile** se molte risposte hanno `tokens = NULL` (alcuni
          provider non li ritornano in modo affidabile, es. Perplexity).
        """
    )
