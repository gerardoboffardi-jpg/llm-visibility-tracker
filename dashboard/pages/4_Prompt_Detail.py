"""Prompt Detail — risposte, citazioni evidenziate, citation gap, azioni."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from collections import defaultdict

import streamlit as st

from dashboard.auth import require_password
from dashboard.style import (
    apply_style,
    badge,
    model_avatar,
    model_meta,
    page_header,
    render_chat_response,
    render_sidebar,
)
from dashboard.utils import (
    fmt_dt,
    fmt_pct,
    get_responses_for_prompt,
    highlight_brands_html,
)
from src import prompt_service as ps
from src.runner import run_single

st.set_page_config(page_title="Prompt Detail", page_icon="🔬", layout="wide")
apply_style()
if not require_password():
    st.stop()

render_sidebar()

page_header(
    icon="🔬",
    title="Prompt Detail",
    sub="Approfondisci un singolo prompt: risposte LLM, citazioni, gap.",
)

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
meta_parts = []
if prompt.category:
    meta_parts.append(f"📂 {prompt.category}")
if prompt.geo:
    meta_parts.append(f"📍 {prompt.geo}")
if prompt.intent:
    meta_parts.append(f"🎯 {prompt.intent}")
meta_parts.append("✅ attivo" if prompt.is_active else "⏸ inattivo")

st.markdown(
    f"""
    <div class="tag-card" style="background:linear-gradient(135deg,white,#F8FAFC);
                                  padding:24px 26px;margin-top:8px">
        <div style="color:#64748B;font-size:0.78rem;text-transform:uppercase;
                    letter-spacing:0.06em;font-weight:600;margin-bottom:6px">
            Prompt #{prompt.id}
        </div>
        <div style="font-size:1.3rem;font-weight:600;color:#0F172A;line-height:1.4">
            {prompt.text}
        </div>
        <div style="color:#64748B;font-size:0.88rem;margin-top:10px">
            {" · ".join(meta_parts)}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------- KPI ----------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Citation rate ⭐", fmt_pct(stats.citation_rate))
c2.metric("Mention rate", fmt_pct(stats.mention_rate))
c3.metric("# risposte", stats.n_responses)
c4.metric("Ultima run", fmt_dt(stats.last_run_at))

# ---------------- Azioni ----------------
b1, b2, b3, b4 = st.columns(4)
with b1:
    with st.popover("▶ Rilancia", use_container_width=True):
        st.markdown("**Esegui questo prompt** su tutti i modelli abilitati.")
        repeat = st.number_input(
            "Numero di ripetizioni",
            min_value=1, max_value=10, value=3, step=1,
            help="Più ripetizioni = più dati per vedere consistenza del modello. "
                 "Costo proporzionale al numero di ripetizioni × modelli.",
        )
        if st.button(f"Esegui {repeat}× ora", type="primary", use_container_width=True):
            from dashboard.utils import fun_loader
            with st.spinner(fun_loader(f"Eseguo {repeat} ripetizioni su tutti i modelli abilitati…")):
                s = run_single(selected_id, repeat=int(repeat))
            st.success(
                f"Run #{s.run_id}: {s.n_success}/{s.n_attempted} OK in {s.elapsed_s:.1f}s"
            )
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

st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

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
st.markdown("### 📊 Confronto modelli")
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

st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

# ---------------- Engine summary cards ----------------
st.markdown("### 💬 Risposte degli LLM")
st.caption(
    "Risposte in formato chat: il prompt come l'utente lo ha posto + la risposta del modello "
    "con i brand evidenziati. Brand TAG in **verde**, competitor in **arancione**."
)

from dashboard.style import engine_summary_card

cols = st.columns(min(len(by_model), 4))
for i, mid in enumerate(list(by_model.keys())[:4]):
    lst = by_model[mid]
    n_men = sum(1 for r in lst if r["has_target_mention"])
    n_cit = sum(1 for r in lst if r["has_target_citation"])
    if n_cit > 0:
        stat = f"Citato {n_cit} su {len(lst)} risposte"
    elif n_men > 0:
        stat = f"Menzionato {n_men} su {len(lst)} risposte"
    else:
        stat = f"Mai menzionato · {len(lst)} risposte"
    cols[i % len(cols)].markdown(
        engine_summary_card(mid, "", stat), unsafe_allow_html=True,
    )

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

# ---------------- Filtro modelli (pills cliccabili) ----------------
# Permette di mostrare solo i modelli selezionati. Default: tutti.
all_model_ids = list(by_model.keys())
model_labels: dict[str, str] = {
    mid: f"{model_meta(mid)[0]} · {mid}" for mid in all_model_ids
}
# st.pills disponibile da Streamlit 1.40. Fallback su multiselect.
try:
    selected_models = st.pills(
        "Filtra per modello (click per attivare/disattivare)",
        options=all_model_ids,
        format_func=lambda mid: model_meta(mid)[0],
        selection_mode="multi",
        default=all_model_ids,  # tutti selezionati di default
        key=f"model_filter_{selected_id}",
    )
except (AttributeError, TypeError):
    selected_models = st.multiselect(
        "Filtra per modello",
        options=all_model_ids,
        default=all_model_ids,
        format_func=lambda mid: model_meta(mid)[0],
        key=f"model_filter_{selected_id}",
    )

if not selected_models:
    st.info("Nessun modello selezionato — clicca su uno o più pulsanti sopra per vederli.")
    st.stop()

# Filtra il dict di modelli
by_model = {mid: lst for mid, lst in by_model.items() if mid in selected_models}

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

# ---------------- Risposte per modello: card grande + frecce navigazione ----------------
# Pattern HubSpot: per ogni modello mostro UNA risposta alla volta in una card grande
# leggibile (Markdown renderizzato), con frecce ‹ › per scorrere le altre ripetizioni.

def _render_citations_block(r: dict) -> None:
    if r["citations"]:
        with st.expander(f"🔗 {len(r['citations'])} citazioni", expanded=False):
            for c in r["citations"]:
                kind = "target" if c["is_target"] else ("competitor" if c["is_competitor"] else "")
                kind_label = (
                    "🟢 TARGET" if c["is_target"]
                    else ("🟠 competitor" if c["is_competitor"] else "⚪ other")
                )
                title = c["title"] or c["url"]
                st.markdown(
                    f'<div class="tag-cit {kind}">'
                    f'<div class="tag-cit-pos">#{c["position"]}</div>'
                    f'<div class="tag-cit-body">'
                    f'<div class="tag-cit-domain">{kind_label} · {c["domain"]}</div>'
                    f'<div class="tag-cit-title">'
                    f'<a href="{c["url"]}" target="_blank">{title}</a>'
                    f'</div></div></div>',
                    unsafe_allow_html=True,
                )
    if r["mentions"]:
        with st.expander(f"💬 {len(r['mentions'])} menzioni"):
            for m in r["mentions"][:6]:
                tag = "🟢" if m["is_target"] else "🟠"
                sent = f" · _{m['sentiment']}_" if m.get("sentiment") else ""
                st.markdown(f"{tag} **{m['brand_name']}**{sent}")
                if m.get("snippet"):
                    st.caption(f"…{m['snippet']}…")
            if len(r["mentions"]) > 6:
                st.caption(f"+ altre {len(r['mentions']) - 6} menzioni")


def _render_single_run(r: dict, mid: str, run_idx: int, n: int) -> None:
    """Renderizza una singola card chat + citazioni/mentions sotto."""
    extra = badge(f"Run {run_idx}/{n}", "neutral") + " "
    if r["latency_ms"]:
        extra += badge(f"{r['latency_ms']}ms", "neutral") + " "
    extra += badge(f"{r['total_citations']} citazioni", "neutral")

    body_html = highlight_brands_html(r["text"])

    st.markdown(
        render_chat_response(
            model_id=mid,
            prompt_text=prompt.text,
            response_text_html=body_html,
            created_at_str=fmt_dt(r["created_at"]),
            has_target_mention=r["has_target_mention"],
            has_target_citation=r["has_target_citation"],
            extra_badges_html=extra,
            show_prompt=True,
        ),
        unsafe_allow_html=True,
    )
    _render_citations_block(r)


for mid in by_model.keys():
    lst = by_model[mid]
    n = len(lst)
    display_name, _ = model_meta(mid)
    n_cit = sum(1 for r in lst if r["has_target_citation"])
    n_men = sum(1 for r in lst if r["has_target_mention"])

    if n_cit > 0:
        stat_text = f"Citato {n_cit} su {n} risposte"
        stat_class = "mentioned"
    elif n_men > 0:
        stat_text = f"Menzionato {n_men} su {n} risposte"
        stat_class = "gap"
    else:
        stat_text = f"Mai menzionato · {n} risposte"
        stat_class = "not-mentioned"

    # Header del modello (avatar + nome + stat aggregata)
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:14px;'
        f'padding:16px 0 8px 0;border-top:1px solid #F1F5F9;margin-top:22px">'
        f'{model_avatar(mid)}'
        f'<div style="flex:1">'
        f'<div style="font-weight:700;font-size:1.2rem;color:#0F172A">{display_name}</div>'
        f'<div style="color:#64748B;font-size:0.82rem;font-family:ui-monospace,Menlo,monospace">{mid}</div>'
        f'</div>'
        f'<span class="tag-run-status {stat_class}">{stat_text}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Toggle "vedi tutte" / "naviga una alla volta" — disponibile solo se ci sono ≥ 2 run
    expand_key = f"expand_{selected_id}_{mid}"
    if n >= 2:
        expand_all = st.toggle(
            f"📑 Vedi tutte le {n} risposte di {display_name}",
            key=expand_key,
            value=False,
            help="OFF: una alla volta con frecce di navigazione. "
                 "ON: tutte le risposte affiancate in lista verticale.",
        )
    else:
        expand_all = False  # 1 sola risposta: niente toggle, niente frecce

    if expand_all:
        # ----- Modalità: tutte AFFIANCATE in colonne (max 3 per riga) -----
        st.caption(
            f"Mostro tutte le {n} risposte di {display_name} affiancate "
            f"per confronto rapido."
        )
        MAX_PER_ROW = 3
        for chunk_start in range(0, n, MAX_PER_ROW):
            chunk = lst[chunk_start : chunk_start + MAX_PER_ROW]
            cols = st.columns(len(chunk), gap="medium")
            for col, (rel_idx, r) in zip(cols, enumerate(chunk, start=chunk_start + 1)):
                with col:
                    extra = badge(f"Run {rel_idx}/{n}", "neutral") + " "
                    if r["latency_ms"]:
                        extra += badge(f"{r['latency_ms']}ms", "neutral") + " "
                    extra += badge(f"{r['total_citations']} cit.", "neutral")
                    body_html = highlight_brands_html(r["text"])
                    st.markdown(
                        render_chat_response(
                            model_id=mid,
                            prompt_text=prompt.text,
                            response_text_html=body_html,
                            created_at_str=fmt_dt(r["created_at"]),
                            has_target_mention=r["has_target_mention"],
                            has_target_citation=r["has_target_citation"],
                            extra_badges_html=extra,
                            show_prompt=False,  # prompt è in header pagina
                            compact=True,
                        ),
                        unsafe_allow_html=True,
                    )
                    _render_citations_block(r)
    else:
        # ----- Modalità: navigazione una alla volta -----
        state_key = f"run_idx_{selected_id}_{mid}"
        if state_key not in st.session_state:
            st.session_state[state_key] = 0
        cur_idx = max(0, min(st.session_state[state_key], n - 1))

        if n >= 2:
            nav_l, nav_c, nav_r = st.columns([1, 6, 1])
            with nav_l:
                if st.button("‹ Prec.", key=f"prev_{mid}",
                             disabled=(cur_idx == 0),
                             use_container_width=True):
                    st.session_state[state_key] = cur_idx - 1
                    st.rerun()
            with nav_c:
                st.markdown(
                    f'<div style="text-align:center;color:#64748B;font-size:0.92rem;'
                    f'padding-top:6px;font-weight:500">'
                    f'Risposta {cur_idx + 1} di {n}</div>',
                    unsafe_allow_html=True,
                )
            with nav_r:
                if st.button("Succ. ›", key=f"next_{mid}",
                             disabled=(cur_idx >= n - 1),
                             use_container_width=True):
                    st.session_state[state_key] = cur_idx + 1
                    st.rerun()

        _render_single_run(lst[cur_idx], mid, cur_idx + 1, n)
