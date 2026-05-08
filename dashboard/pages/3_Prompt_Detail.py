"""Prompt Detail — risposte, citazioni evidenziate, citation gap, azioni."""
from __future__ import annotations

from collections import defaultdict

import streamlit as st

from dashboard.utils import (
    fmt_dt,
    fmt_pct,
    get_responses_for_prompt,
    highlight_brands_html,
)
from src import prompt_service as ps
from src.runner import run_single

st.set_page_config(page_title="Prompt Detail", page_icon="🔬", layout="wide")
st.title("🔬 Prompt Detail")

# Selettore prompt
prompts = ps.list_prompts()
if not prompts:
    st.warning("Nessun prompt nel database.")
    st.stop()

# id da query param se presente
qp = st.query_params
default_id = int(qp.get("prompt_id", prompts[0].id)) if qp.get("prompt_id") else prompts[0].id
ids = [p.id for p in prompts]
labels = {p.id: f"#{p.id} — {p.text[:80]}" for p in prompts}
selected_id = st.selectbox(
    "Prompt",
    options=ids,
    index=ids.index(default_id) if default_id in ids else 0,
    format_func=lambda i: labels[i],
)
st.query_params["prompt_id"] = str(selected_id)

prompt = ps.get_prompt(selected_id)
stats = ps.get_prompt_stats(selected_id)
responses = get_responses_for_prompt(selected_id)

# ---------------- Header ----------------
st.markdown(f"### {prompt.text}")
meta_parts = []
if prompt.category:
    meta_parts.append(f"📂 {prompt.category}")
if prompt.geo:
    meta_parts.append(f"📍 {prompt.geo}")
if prompt.intent:
    meta_parts.append(f"🎯 {prompt.intent}")
meta_parts.append("✅ attivo" if prompt.is_active else "⏸ inattivo")
st.caption(" · ".join(meta_parts))

# ---------------- KPI ----------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Citation rate ⭐", fmt_pct(stats.citation_rate))
c2.metric("Mention rate", fmt_pct(stats.mention_rate))
c3.metric("# risposte", stats.n_responses)
c4.metric("Ultima run", fmt_dt(stats.last_run_at))

# ---------------- Azioni ----------------
b1, b2, b3, b4 = st.columns(4)
if b1.button("▶ Rilancia (1 repeat)", use_container_width=True):
    with st.spinner("Eseguo su tutti i modelli abilitati…"):
        s = run_single(selected_id, repeat=1)
    st.success(f"Run #{s.run_id}: {s.n_success}/{s.n_attempted} OK in {s.elapsed_s:.1f}s")
    st.rerun()
if b2.button("⏸ Disattiva" if prompt.is_active else "▶ Attiva", use_container_width=True):
    ps.set_prompt_active(selected_id, not prompt.is_active)
    st.rerun()
with b3:
    with st.popover("✏️ Modifica", use_container_width=True):
        with st.form(f"edit_{selected_id}"):
            new_text = st.text_area("Testo", value=prompt.text)
            new_cat = st.text_input("Categoria", value=prompt.category or "")
            new_geo = st.text_input("Geo", value=prompt.geo or "")
            new_int = st.text_input("Intent", value=prompt.intent or "")
            new_notes = st.text_area("Note", value=prompt.notes or "")
            if st.form_submit_button("Salva", type="primary"):
                ps.update_prompt(
                    selected_id, text=new_text, category=new_cat, geo=new_geo,
                    intent=new_int, notes=new_notes,
                )
                st.rerun()
with b4:
    with st.popover("📋 Duplica", use_container_width=True):
        with st.form(f"dup_{selected_id}"):
            dup_text = st.text_area("Nuovo testo", value=prompt.text + " (copia)")
            if st.form_submit_button("Crea copia", type="primary"):
                try:
                    new_p = ps.create_prompt(
                        text=dup_text, category=prompt.category, geo=prompt.geo,
                        intent=prompt.intent, force=True,
                    )
                    st.success(f"Creato prompt #{new_p.id}")
                    st.query_params["prompt_id"] = str(new_p.id)
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(str(e))

st.divider()

if not responses:
    st.info("Nessuna risposta ancora. Clicca **▶ Rilancia** per eseguire il prompt.")
    st.stop()

# ---------------- Citation gap callout ----------------
gap_responses = [r for r in responses if r["has_target_mention"] and not r["has_target_citation"]]
if gap_responses:
    st.warning(
        f"⚠️ **Citation gap**: {len(gap_responses)} risposte menzionano Talent Garden ma "
        f"NON citano il dominio. Opportunità SEO: ottimizzare contenuti per essere citati come fonte."
    )

# ---------------- Confronto modelli ----------------
st.subheader("📊 Confronto modelli")
by_model: dict[str, list] = defaultdict(list)
for r in responses:
    by_model[r["model_id"]].append(r)

import pandas as pd
rows = []
for mid, lst in by_model.items():
    n = len(lst)
    n_cit = sum(1 for r in lst if r["has_target_citation"])
    n_men = sum(1 for r in lst if r["has_target_mention"])
    cit_positions = [r["target_citation_position"] for r in lst if r["target_citation_position"]]
    avg_pos = sum(cit_positions) / len(cit_positions) if cit_positions else None
    rows.append({
        "model": mid,
        "n_risposte": n,
        "citation_rate": n_cit / n if n else 0,
        "mention_rate": n_men / n if n else 0,
        "avg_target_position": avg_pos,
    })
df_models = pd.DataFrame(rows)
st.dataframe(
    df_models,
    column_config={
        "model": "Modello",
        "n_risposte": st.column_config.NumberColumn("# risp.", width="small"),
        "citation_rate": st.column_config.ProgressColumn(
            "Citation rate", format="%.1f%%", min_value=0, max_value=1,
        ),
        "mention_rate": st.column_config.ProgressColumn(
            "Mention rate", format="%.1f%%", min_value=0, max_value=1,
        ),
        "avg_target_position": st.column_config.NumberColumn(
            "Posizione media citazione", format="%.1f",
        ),
    },
    hide_index=True,
    use_container_width=True,
)

st.divider()

# ---------------- Risposte per modello (tabs) ----------------
st.subheader("💬 Risposte per modello")
tabs = st.tabs(list(by_model.keys()))
for tab, mid in zip(tabs, by_model.keys()):
    with tab:
        for r in by_model[mid]:
            cit_emoji = "✅" if r["has_target_citation"] else "❌"
            men_emoji = "✅" if r["has_target_mention"] else "❌"
            with st.expander(
                f"{fmt_dt(r['created_at'])} — citation {cit_emoji} · mention {men_emoji} · "
                f"{r['total_citations']} cit · {r['latency_ms']}ms",
                expanded=False,
            ):
                # Citation gap warning sul singolo
                if r["has_target_mention"] and not r["has_target_citation"]:
                    st.warning("⚠️ Menzionato ma non citato — citation gap")

                # Testo evidenziato
                st.markdown("**Risposta**")
                html = highlight_brands_html(r["text"])
                st.markdown(
                    f"<div style='background:#f8fafc;padding:12px;border-radius:6px;"
                    f"line-height:1.6;font-size:0.92em'>{html}</div>",
                    unsafe_allow_html=True,
                )

                # Citazioni
                if r["citations"]:
                    st.markdown("**🔗 Citazioni**")
                    for c in r["citations"]:
                        if c["is_target"]:
                            tag = "🟢 **TARGET**"
                            color = "#16a34a"
                        elif c["is_competitor"]:
                            tag = "🟠 competitor"
                            color = "#f97316"
                        else:
                            tag = "⚪ other"
                            color = "#64748b"
                        st.markdown(
                            f"<div style='border-left:3px solid {color};padding-left:8px;margin:4px 0'>"
                            f"<small>[{c['position']}] {tag} — <code>{c['domain']}</code></small><br>"
                            f"<a href='{c['url']}' target='_blank'>{c['title'] or c['url']}</a>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.caption("_Nessuna citazione._")

                # Mention dettaglio (collapsible)
                if r["mentions"]:
                    with st.popover(f"Vedi {len(r['mentions'])} menzioni"):
                        for m in r["mentions"]:
                            tag = "🟢" if m["is_target"] else "🟠"
                            sent = f" · _{m['sentiment']}_" if m.get("sentiment") else ""
                            st.markdown(f"{tag} **{m['brand_name']}**{sent}")
                            st.caption(f"…{m['snippet']}…")
