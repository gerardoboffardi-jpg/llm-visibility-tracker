"""💬 Risposte — feed cronologico di tutte le risposte LLM con filtri."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import yaml
import streamlit as st

from dashboard.auth import require_password
from dashboard.style import (
    CORAL,
    apply_style,
    badge,
    page_header,
    render_chat_response,
    render_sidebar,
)
from dashboard.utils import (
    fmt_dt,
    get_available_models,
    highlight_brands_html,
    recent_responses_feed,
    truncate,
)
from src import prompt_service as ps

st.set_page_config(page_title="Risposte", page_icon="💬", layout="wide")
apply_style()
if not require_password():
    st.stop()

render_sidebar()

page_header(
    icon="💬",
    title="Risposte LLM",
    sub="Feed cronologico di tutte le risposte raccolte. Brand evidenziati e citazioni in chiaro.",
)

# --- Carica config modelli per distinguere search vs chat ---
_cfg_path = Path(__file__).resolve().parent.parent.parent / "config" / "models.yaml"
try:
    with open(_cfg_path) as _f:
        _models_cfg = yaml.safe_load(_f) or []
except Exception:
    _models_cfg = []

_search_model_ids: set[str] = {
    m["id"] for m in _models_cfg if "id" in m and m.get("web_search", True)
}
_chat_model_ids: set[str] = {
    m["id"] for m in _models_cfg if "id" in m and not m.get("web_search", True)
}

# ----------------- Filtri (top bar) -----------------
prompts = ps.list_prompts()
prompt_options = {0: "Tutti i prompt"}
for p in prompts:
    prompt_options[p.id] = f"#{p.id} — {truncate(p.text, 70)}"

models = get_available_models()
model_options = ["Tutti i modelli"] + models

with st.container():
    f1, f2, f3, f4, f5 = st.columns([2, 2, 2, 1, 1])
    sel_prompt = f1.selectbox(
        "Prompt", options=list(prompt_options.keys()),
        format_func=lambda i: prompt_options[i],
    )
    sel_model = f2.selectbox("Modello", options=model_options)
    sel_status = f3.selectbox(
        "Filtra per visibility",
        options=["Tutte", "✅ Solo con citazione", "💬 Solo con menzione",
                 "⚠️ Solo citation gap", "❌ Né citato né menzionato"],
    )
    sel_model_type = f4.selectbox(
        "Tipo modello",
        options=["Tutti", "🔍 Search", "💬 Chat"],
    )
    limit = f5.number_input("Limite", min_value=10, max_value=500, value=50, step=10)

# ----------------- Query feed -----------------
filters = {
    "limit": int(limit),
    "model_id": sel_model if sel_model != "Tutti i modelli" else None,
    "prompt_id": sel_prompt if sel_prompt else None,
}
if sel_status == "✅ Solo con citazione":
    filters["only_citation"] = True
elif sel_status == "💬 Solo con menzione":
    filters["only_mention"] = True
elif sel_status == "⚠️ Solo citation gap":
    filters["only_gap"] = True

feed = recent_responses_feed(**filters)

# Filtro client-side per "Né citato né menzionato"
if sel_status == "❌ Né citato né menzionato":
    feed = [r for r in feed if not r["has_target_citation"] and not r["has_target_mention"]]

# Filtro client-side per tipo modello (search vs chat)
if sel_model_type == "🔍 Search":
    # Se il modello non è in config, lo trattiamo come search per retrocompatibilità
    feed = [r for r in feed if r["model_id"] in _search_model_ids or r["model_id"] not in _chat_model_ids]
elif sel_model_type == "💬 Chat":
    feed = [r for r in feed if r["model_id"] in _chat_model_ids]

# ----------------- Summary chip -----------------
n_total = len(feed)
n_cit = sum(1 for r in feed if r["has_target_citation"])
n_men = sum(1 for r in feed if r["has_target_mention"])
n_gap = sum(1 for r in feed if r["has_target_mention"] and not r["has_target_citation"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Risposte mostrate", n_total)
c2.metric("Con citazione ✓", n_cit)
c3.metric("Con menzione 💬", n_men)
c4.metric("Citation gap ⚠️", n_gap)

st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

# ----------------- Engine summary cards (stile HubSpot) -----------------
from dashboard.style import engine_summary_card

# Aggrega menzioni per engine
by_engine: dict[str, dict] = {}
for r in feed:
    e = r["model_id"]
    by_engine.setdefault(e, {"n": 0, "n_men": 0, "n_cit": 0})
    by_engine[e]["n"] += 1
    if r["has_target_mention"]:
        by_engine[e]["n_men"] += 1
    if r["has_target_citation"]:
        by_engine[e]["n_cit"] += 1

if by_engine:
    cols = st.columns(min(len(by_engine), 4))
    for i, (mid, stats) in enumerate(list(by_engine.items())[:4]):
        col = cols[i % len(cols)]
        if stats["n_men"] > 0:
            stat = f"Menzionato {stats['n_men']} su {stats['n']} risposte"
        else:
            stat = f"Mai menzionato · {stats['n']} risposte"
        col.markdown(engine_summary_card(mid, "", stat), unsafe_allow_html=True)

st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

if not feed:
    st.info("Nessuna risposta con questi filtri.")
    st.stop()

# ----------------- Feed in chat-style -----------------
for r in feed:
    # Badge extra: posizione citazione se presente
    extra_badges = ""
    if r["has_target_citation"]:
        tgt_pos = None
        for c in r["citations"]:
            if c["is_target"]:
                tgt_pos = c["position"]
                break
        if tgt_pos:
            extra_badges += badge(f"Pos. #{tgt_pos}", "coral")

    # Link al Prompt Detail (in alto, fuori dalla chat card)
    st.markdown(
        f"""
        <div style="margin-top:10px;display:flex;justify-content:space-between;
                    align-items:baseline;gap:10px;flex-wrap:wrap">
            <a href="/Prompt_Detail?prompt_id={r['prompt_id']}"
               style="color:#0F172A;font-weight:600;font-size:0.92rem">
                🔬 Prompt #{r['prompt_id']} — {truncate(r['prompt_text'], 100)}
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Chat card
    body_html = highlight_brands_html(r["text"])
    st.markdown(
        render_chat_response(
            model_id=r["model_id"],
            prompt_text=r["prompt_text"],
            response_text_html=body_html,
            created_at_str=fmt_dt(r["created_at"]),
            has_target_mention=r["has_target_mention"],
            has_target_citation=r["has_target_citation"],
            extra_badges_html=extra_badges,
        ),
        unsafe_allow_html=True,
    )

    # Citazioni (sotto, in expander per non saturare)
    if r["citations"]:
        with st.expander(f"🔗 {len(r['citations'])} citazioni"):
            for c in r["citations"]:
                kind = "target" if c["is_target"] else ("competitor" if c["is_competitor"] else "")
                kind_label = (
                    "🟢 TARGET" if c["is_target"]
                    else ("🟠 competitor" if c["is_competitor"] else "⚪ other")
                )
                title = c["title"] or c["url"]
                st.markdown(
                    f"""
                    <div class="tag-cit {kind}">
                        <div class="tag-cit-pos">#{c['position']}</div>
                        <div class="tag-cit-body">
                            <div class="tag-cit-domain">{kind_label} · {c['domain']}</div>
                            <div class="tag-cit-title">
                                <a href="{c['url']}" target="_blank">{title}</a>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
