"""Models — confronto performance dei modelli LLM, separati in search e chat."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import yaml
import streamlit as st

from dashboard.auth import require_password
from dashboard.style import apply_style, page_header, render_sidebar
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

# --- Carica configurazione modelli da models.yaml ---
_cfg_path = Path(__file__).resolve().parent.parent.parent / "config" / "models.yaml"
try:
    with open(_cfg_path) as _f:
        _models_cfg = yaml.safe_load(_f) or []
except Exception:
    _models_cfg = []

# Costruisci set di model_id per categoria
search_model_ids: set[str] = set()
chat_model_ids: set[str] = set()
for _m in _models_cfg:
    if "id" not in _m:
        continue
    if _m.get("web_search", True):
        search_model_ids.add(_m["id"])
    else:
        chat_model_ids.add(_m["id"])

# --- Dati aggregati dal DB ---
df = model_aggregates()
if df.empty:
    st.info("Nessuna risposta raccolta ancora. Esegui un batch.")
    st.stop()

df_search = df[df["model_id"].isin(search_model_ids)].copy()
df_chat = df[df["model_id"].isin(chat_model_ids)].copy()
# Modelli non presenti in config: li trattiamo come search per retrocompatibilità
df_unknown = df[~df["model_id"].isin(search_model_ids | chat_model_ids)].copy()
if not df_unknown.empty:
    df_search = st.data_editor if False else df_search  # noop
    df_search = df_search._append(df_unknown, ignore_index=True)

# ============================================================
# SEZIONE 1: Modelli Search (con web search)
# ============================================================
st.markdown("### 🔍 Modelli Search (con web search)")
st.caption("Questi modelli hanno accesso al web in tempo reale. La metrica principale è la **citation rate**: quanto spesso talentgarden.com appare citato.")

if df_search.empty:
    st.info("Nessun dato per i modelli search.")
else:
    st.dataframe(
        df_search[["model_id", "n_responses", "citation_rate", "mention_rate",
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

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

# ============================================================
# SEZIONE 2: Modelli Chat (senza web search)
# ============================================================
st.markdown("### 💬 Modelli Chat (senza web search)")
st.caption(
    "Per i modelli chat la **citation_rate è sempre 0** (non hanno accesso al web). "
    "La metrica rilevante è la **mention_rate**, che misura quanto il brand è presente "
    "nel training data del modello."
)

if df_chat.empty:
    st.info("Nessun dato per i modelli chat ancora raccolta.")
else:
    st.dataframe(
        df_chat[["model_id", "n_responses", "mention_rate", "citation_rate", "avg_latency_ms"]],
        column_config={
            "model_id": "Modello",
            "n_responses": st.column_config.NumberColumn("# risposte"),
            "mention_rate": st.column_config.ProgressColumn(
                "Mention rate 💬", format="%.1f%%", min_value=0, max_value=1,
            ),
            "citation_rate": st.column_config.ProgressColumn(
                "Citation rate (n/a)", format="%.1f%%", min_value=0, max_value=1,
            ),
            "avg_latency_ms": st.column_config.NumberColumn("Latency media (ms)", format="%.0f"),
        },
        hide_index=True, use_container_width=True,
    )

st.divider()
st.markdown("### Configurazione modelli")
st.markdown("Edita `config/models.yaml` per attivare/disattivare modelli o aggiungerne di nuovi.")
st.code("""
# Esempio modello search
- id: perplexity-sonar
  provider: perplexity
  model: sonar
  web_search: true
  enabled: true

# Esempio modello chat (senza web search)
- id: gpt-4o-chat
  provider: openai
  model: gpt-4o
  web_search: false
  enabled: true
""", language="yaml")
