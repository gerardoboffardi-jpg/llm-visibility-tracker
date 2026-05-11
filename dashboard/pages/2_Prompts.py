"""Prompts — lista, aggiungi, modifica, lancia run."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from dashboard.auth import require_password
from dashboard.utils import prompts_overview_df
from src import prompt_service as ps
from src.runner import run_single

st.set_page_config(page_title="Prompts", page_icon="📝", layout="wide")
if not require_password():
    st.stop()

st.title("📝 Prompts")
st.caption("Gestisci i prompt che vengono monitorati su tutti gli LLM.")

# ----------------- Top bar: actions -----------------
top_l, top_r = st.columns([3, 1])
with top_r:
    if st.button("➕ Aggiungi prompt", use_container_width=True, type="primary"):
        st.session_state["show_add_form"] = True
    if st.button("📤 Import YAML/CSV", use_container_width=True):
        st.session_state["show_import_form"] = True

# ----------------- Add prompt form -----------------
if st.session_state.get("show_add_form"):
    with st.form("add_prompt", clear_on_submit=True):
        st.markdown("### ➕ Nuovo prompt")
        text = st.text_area("Testo del prompt *", height=80, placeholder="Es: Migliori coworking a Milano")
        c1, c2, c3 = st.columns(3)
        category = c1.text_input("Categoria", placeholder="coworking / formazione / innovation / brand")
        geo = c2.text_input("Geo", placeholder="Milano / Italia / ...")
        intent = c3.text_input("Intent", placeholder="discovery / pricing / comparison / brand")
        notes = st.text_input("Note (opzionale)")
        force = st.checkbox("Forza (bypassa check duplicati)")
        run_now = st.checkbox("Esegui subito su tutti i modelli abilitati")

        c1, c2 = st.columns(2)
        submit = c1.form_submit_button("✅ Salva", use_container_width=True, type="primary")
        cancel = c2.form_submit_button("✗ Annulla", use_container_width=True)

        if submit:
            if not text.strip():
                st.error("Il testo è obbligatorio.")
            else:
                try:
                    p = ps.create_prompt(
                        text=text, category=category or None, geo=geo or None,
                        intent=intent or None, notes=notes or None, force=force,
                    )
                    st.success(f"Prompt #{p.id} creato.")
                    st.session_state["show_add_form"] = False
                    if run_now:
                        with st.spinner(f"Eseguo prompt #{p.id} su tutti i modelli…"):
                            stats = run_single(p.id, repeat=1)
                        st.success(f"Run #{stats.run_id}: {stats.n_success}/{stats.n_attempted} OK in {stats.elapsed_s:.1f}s")
                    st.rerun()
                except ps.DuplicatePromptError as e:
                    w = e.warning
                    st.warning(
                        f"⚠️ Prompt simile già esistente (id={w.existing_id}, similarity={w.similarity:.2f}):\n\n"
                        f"> {w.existing_text}\n\nAttiva 'Forza' per inserire comunque."
                    )
        if cancel:
            st.session_state["show_add_form"] = False
            st.rerun()

# ----------------- Import form -----------------
if st.session_state.get("show_import_form"):
    with st.form("import_prompts", clear_on_submit=True):
        st.markdown("### 📤 Import YAML / CSV")
        f = st.file_uploader("File", type=["yaml", "yml", "csv"])
        st.caption("YAML: lista di {text, category, geo, intent, notes}. CSV: stesse colonne come header.")
        submit = st.form_submit_button("Importa")
        if submit and f is not None:
            content = f.read().decode("utf-8")
            fmt = "yaml" if f.name.endswith((".yaml", ".yml")) else "csv"
            result = ps.bulk_import(content, fmt=fmt)
            st.success(
                f"✅ {result.added} aggiunti · {result.skipped_duplicates} duplicati saltati · "
                f"{result.skipped_invalid} non validi"
            )
            st.session_state["show_import_form"] = False
            st.rerun()

# ----------------- Filtri -----------------
with st.expander("🔎 Filtri", expanded=False):
    c1, c2, c3, c4 = st.columns(4)
    search = c1.text_input("Cerca testo")
    cat_filter = c2.text_input("Categoria")
    geo_filter = c3.text_input("Geo")
    status_filter = c4.selectbox("Stato", ["Tutti", "Attivi", "Inattivi"])
    c1, c2, c3 = st.columns(3)
    only_no_runs = c1.checkbox("Solo prompt mai eseguiti")
    only_no_target_cit = c2.checkbox("Solo dove il dominio NON è citato")
    only_gap = c3.checkbox("Solo citation gap (menzionato ma non citato)")

# ----------------- Tabella -----------------
df = prompts_overview_df()
if df.empty:
    st.info("Nessun prompt nel database. Clicca '➕ Aggiungi prompt' o esegui `python -m scripts.seed_db`.")
    st.stop()

# Applica filtri
if search:
    df = df[df["prompt"].str.contains(search, case=False, na=False)]
if cat_filter:
    df = df[df["categoria"].str.contains(cat_filter, case=False, na=False)]
if geo_filter:
    df = df[df["geo"].str.contains(geo_filter, case=False, na=False)]
if status_filter == "Attivi":
    df = df[df["attivo"]]
elif status_filter == "Inattivi":
    df = df[~df["attivo"]]
if only_no_runs:
    df = df[df["n_risposte"] == 0]
if only_no_target_cit:
    df = df[(df["n_risposte"] > 0) & (df["citation_rate"].fillna(0) == 0)]
if only_gap:
    df = df[(df["mention_rate"].fillna(0) - df["citation_rate"].fillna(0)) > 0]

st.caption(f"{len(df)} prompt mostrati")

st.dataframe(
    df,
    column_config={
        "id": st.column_config.NumberColumn("ID", width="small"),
        "prompt": st.column_config.TextColumn("Prompt", width="large"),
        "categoria": "Categoria",
        "geo": "Geo",
        "intent": "Intent",
        "attivo": st.column_config.CheckboxColumn("Attivo"),
        "n_risposte": st.column_config.NumberColumn("# risp.", width="small"),
        "n_modelli": st.column_config.NumberColumn("# mod.", width="small"),
        "citation_rate": st.column_config.ProgressColumn(
            "Citation rate ⭐", format="%.1f%%", min_value=0, max_value=1,
            help="Metrica chiave: % di risposte in cui talentgarden.com è citato",
        ),
        "mention_rate": st.column_config.ProgressColumn(
            "Mention rate", format="%.1f%%", min_value=0, max_value=1,
        ),
        "ultima_run": st.column_config.DatetimeColumn("Ultima run", format="YYYY-MM-DD HH:mm"),
    },
    hide_index=True,
    use_container_width=True,
    height=500,
)

st.markdown("**Apri un prompt** → vai alla pagina **Prompt Detail** e inserisci l'ID del prompt.")
st.markdown("Per esecuzione manuale di un prompt usa la pagina **Prompt Detail** o il CLI:")
st.code("python -m scripts.run_single_prompt --prompt-id <ID> --repeat 3", language="bash")
