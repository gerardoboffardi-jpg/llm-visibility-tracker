"""Prompts — lista, aggiungi, modifica, lancia run."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from dashboard.auth import require_password
from dashboard.style import apply_style, page_header, render_sidebar
from dashboard.utils import fun_loader, prompts_overview_df
from src import prompt_service as ps
from src.runner import run_single

st.set_page_config(page_title="Prompts", page_icon="📝", layout="wide")
apply_style()
if not require_password():
    st.stop()

render_sidebar()

page_header(
    icon="📝",
    title="Prompts",
    sub="Gestisci la lista dei prompt monitorati su tutti gli LLM.",
)

# ----------------- Toolbar azioni (ben visibile) -----------------
st.markdown(
    """
    <div style="background:white;border:1px solid #F1F5F9;border-radius:14px;
                padding:18px 22px;margin-bottom:18px">
        <div style="font-size:0.74rem;color:#E94E1B;font-weight:700;
                    text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">
            Aggiungi prompt
        </div>
        <div style="font-size:1.05rem;font-weight:600;color:#0F172A;margin-bottom:14px">
            Tre modi per popolare la lista di prompt da monitorare
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

ta1, ta2, ta3 = st.columns(3)
with ta1:
    st.markdown(
        """
        <div style="background:#FFF1EC;border:1px solid #FFE0D4;border-radius:12px;
                    padding:16px;margin-bottom:8px">
            <div style="font-size:1.6rem;margin-bottom:6px">🪄</div>
            <div style="font-weight:600;color:#0F172A">Genera da URL o Brochure</div>
            <div style="color:#64748B;font-size:0.86rem;margin:4px 0 0 0">
                Incolla un link del sito o carica un PDF: l'LLM suggerisce 20-30 prompt rilevanti.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(
        "🪄 Genera da URL/Brochure",
        use_container_width=True,
        type="primary",
        key="btn_generate",
    ):
        st.session_state["show_generate_form"] = True

with ta2:
    st.markdown(
        """
        <div style="background:white;border:1px solid #F1F5F9;border-radius:12px;
                    padding:16px;margin-bottom:8px">
            <div style="font-size:1.6rem;margin-bottom:6px">➕</div>
            <div style="font-weight:600;color:#0F172A">Aggiungi prompt singolo</div>
            <div style="color:#64748B;font-size:0.86rem;margin:4px 0 0 0">
                Inserisci manualmente un singolo prompt con categoria, geo e intent.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(
        "➕ Aggiungi prompt",
        use_container_width=True,
        key="btn_add",
    ):
        st.session_state["show_add_form"] = True

with ta3:
    st.markdown(
        """
        <div style="background:white;border:1px solid #F1F5F9;border-radius:12px;
                    padding:16px;margin-bottom:8px">
            <div style="font-size:1.6rem;margin-bottom:6px">📤</div>
            <div style="font-weight:600;color:#0F172A">Import YAML/CSV</div>
            <div style="color:#64748B;font-size:0.86rem;margin:4px 0 0 0">
                Carica una lista in bulk da file YAML o CSV con colonne text, category, geo, intent.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(
        "📤 Import YAML/CSV",
        use_container_width=True,
        key="btn_import",
    ):
        st.session_state["show_import_form"] = True

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

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
                    st.cache_data.clear()
                    st.session_state["show_add_form"] = False
                    if run_now:
                        with st.spinner(fun_loader(f"Eseguo prompt #{p.id} su tutti i modelli…")):
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
            st.cache_data.clear()
            st.session_state["show_import_form"] = False
            st.rerun()

# ----------------- Prompt generator from URL / PDF -----------------
if st.session_state.get("show_generate_form"):
    from src import prompt_generator as pg

    st.markdown("### 🪄 Genera prompt da URL o brochure")
    st.caption(
        "Incolla un URL del tuo sito (es. landing prodotto, pagina servizio) "
        "oppure carica una brochure PDF. Un LLM analizzerà il contenuto e proporrà "
        "20-30 prompt realistici che gli utenti potrebbero fare a ChatGPT/Claude/Perplexity. "
        "Tu scegli quali importare."
    )

    src_tabs = st.tabs(["🌐 Da URL", "📄 Da PDF (brochure)"])

    # ---------- URL tab ----------
    with src_tabs[0]:
        with st.form("gen_url"):
            url = st.text_input(
                "URL del sito o pagina",
                placeholder="https://talentgarden.com/it/coworking-milano",
            )
            provider = st.selectbox(
                "Modello generatore",
                ["auto (Claude → fallback OpenAI)", "Claude", "OpenAI"],
                help="auto è la scelta consigliata: usa Claude e ripiega su OpenAI se la key Anthropic manca.",
            )
            submit_url = st.form_submit_button("Genera prompt", type="primary")
            cancel_url = st.form_submit_button("✗ Annulla")

            if submit_url and url.strip():
                with st.spinner(fun_loader("Scarico la pagina e chiamo il modello…")):
                    try:
                        prov = (
                            "auto" if "auto" in provider
                            else ("claude" if "Claude" in provider else "openai")
                        )
                        result = pg.generate_from_url(url.strip(), provider=prov)
                        st.session_state["generated_result"] = result
                        st.success(
                            f"✅ Generati {len(result.prompts)} prompt da "
                            f"{result.source_text_chars} char estratti, modello: {result.model_used}"
                        )
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Errore: {e}")

            if cancel_url:
                st.session_state["show_generate_form"] = False
                st.session_state.pop("generated_result", None)
                st.rerun()

    # ---------- PDF tab ----------
    with src_tabs[1]:
        with st.form("gen_pdf"):
            uploaded = st.file_uploader("Brochure PDF", type=["pdf"])
            provider_pdf = st.selectbox(
                "Modello generatore",
                ["auto (Claude → fallback OpenAI)", "Claude", "OpenAI"],
                key="prov_pdf",
            )
            submit_pdf = st.form_submit_button("Genera prompt", type="primary")
            cancel_pdf = st.form_submit_button("✗ Annulla", key="cancel_pdf")

            if submit_pdf and uploaded is not None:
                with st.spinner(fun_loader("Estraggo testo dal PDF e chiamo il modello…")):
                    try:
                        prov = (
                            "auto" if "auto" in provider_pdf
                            else ("claude" if "Claude" in provider_pdf else "openai")
                        )
                        result = pg.generate_from_pdf(
                            uploaded.read(), uploaded.name, provider=prov,
                        )
                        st.session_state["generated_result"] = result
                        st.success(
                            f"✅ Generati {len(result.prompts)} prompt da "
                            f"{result.source_text_chars} char estratti, modello: {result.model_used}"
                        )
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Errore: {e}")

            if cancel_pdf:
                st.session_state["show_generate_form"] = False
                st.session_state.pop("generated_result", None)
                st.rerun()

    # ---------- Preview + import ----------
    gen_result = st.session_state.get("generated_result")
    if gen_result is not None:
        st.markdown("---")
        st.markdown(f"#### 📋 Anteprima prompt generati ({len(gen_result.prompts)})")
        st.caption(
            f"Sorgente: `{gen_result.source_label}` · modello: `{gen_result.model_used}` · "
            "Spunta i prompt che vuoi importare."
        )

        # Build dataframe modificabile
        import pandas as pd
        df_gen = pd.DataFrame(
            [
                {
                    "import": True,  # tutti selezionati di default
                    "text": p.text,
                    "category": p.category or "",
                    "geo": p.geo or "",
                    "intent": p.intent or "",
                }
                for p in gen_result.prompts
            ]
        )
        edited = st.data_editor(
            df_gen,
            column_config={
                "import": st.column_config.CheckboxColumn("✓", width="small"),
                "text": st.column_config.TextColumn("Prompt", width="large"),
                "category": st.column_config.TextColumn("Categoria", width="small"),
                "geo": st.column_config.TextColumn("Geo", width="small"),
                "intent": st.column_config.TextColumn("Intent", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=420,
            key="gen_editor",
        )

        n_selected = int(edited["import"].sum()) if not edited.empty else 0

        cb1, cb2, cb3 = st.columns([1, 1, 2])
        do_import = cb1.button(
            f"✅ Importa {n_selected} prompt selezionati",
            type="primary",
            disabled=n_selected == 0,
            use_container_width=True,
        )
        do_run_after = cb2.checkbox("Esegui subito i prompt importati", value=False)
        cb3.caption("Force-import bypassa il check duplicati. Lasciato disattivato per default.")
        force_dup = cb3.checkbox("Forza (bypassa duplicati)", value=False)

        if do_import:
            added: list[int] = []
            duplicates: list[str] = []
            errors: list[str] = []
            with st.spinner(fun_loader("Importo prompt selezionati…")):
                for _, row in edited.iterrows():
                    if not row["import"]:
                        continue
                    try:
                        p = ps.create_prompt(
                            text=row["text"],
                            category=row["category"] or None,
                            geo=row["geo"] or None,
                            intent=row["intent"] or None,
                            notes=f"Generato da {gen_result.source_label}",
                            force=force_dup,
                        )
                        added.append(p.id)
                    except ps.DuplicatePromptError as e:
                        duplicates.append(e.warning.existing_text)
                    except Exception as e:  # noqa: BLE001
                        errors.append(str(e))
            st.success(
                f"✅ {len(added)} importati · {len(duplicates)} duplicati saltati · "
                f"{len(errors)} errori"
            )
            if duplicates:
                with st.expander("Duplicati saltati"):
                    for d in duplicates:
                        st.write(f"- {d}")
            if do_run_after and added:
                with st.spinner(fun_loader(f"Eseguo {len(added)} prompt su tutti i modelli…")):
                    for pid in added:
                        try:
                            run_single(pid, repeat=1)
                        except Exception as e:  # noqa: BLE001
                            st.warning(f"Run #{pid} fallita: {e}")
                st.success("Esecuzione completata.")
            st.cache_data.clear()
            st.session_state.pop("generated_result", None)
            st.session_state["show_generate_form"] = False
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

# Tabella in sola lettura (consultazione)
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

# ----------------- Rilancia prompt (pannello dedicato) -----------------
with st.expander("▶️ Rilancia prompt", expanded=False):
    st.caption(
        "Seleziona i prompt e le ripetizioni, poi avvia l'esecuzione su tutti i "
        "modelli abilitati. Il costo è proporzionale a ripetizioni × modelli × prompt."
    )

    _r_id_to_label = {int(r.id): f"#{int(r.id)} · {str(r.prompt)[:70]}" for r in df.itertuples()}
    _r_all = list(_r_id_to_label.values())
    _r_lab2id = {v: k for k, v in _r_id_to_label.items()}

    rsa1, rsa2, _ = st.columns([1, 1, 3])
    if rsa1.button("Seleziona tutti", key="run_sel_all_btn", use_container_width=True):
        st.session_state["run_selection"] = _r_all
        st.rerun()
    if rsa2.button("Deseleziona", key="run_desel_btn", use_container_width=True):
        st.session_state["run_selection"] = []
        st.rerun()

    run_labels = st.multiselect(
        "Prompt da rilanciare",
        options=_r_all,
        key="run_selection",
        placeholder="Scegli i prompt…",
    )
    run_ids = [_r_lab2id[l] for l in run_labels if l in _r_lab2id]

    repeat = st.number_input(
        "Ripetizioni per prompt",
        min_value=1, max_value=10, value=1, step=1,
        help="Più ripetizioni = più dati sulla consistenza del modello.",
    )

    if st.button(
        f"▶️ Esegui {len(run_ids)} prompt × {repeat}",
        type="primary",
        disabled=len(run_ids) == 0,
        use_container_width=True,
    ):
        prog = st.progress(0.0, text="Avvio…")
        ok_total = att_total = 0
        for i, pid in enumerate(run_ids):
            with st.spinner(fun_loader(f"Eseguo prompt #{pid} ({i + 1}/{len(run_ids)}) su tutti i modelli…")):
                try:
                    s = run_single(pid, repeat=int(repeat))
                    ok_total += s.n_success
                    att_total += s.n_attempted
                except Exception as e:  # noqa: BLE001
                    st.warning(f"Prompt #{pid} fallito: {e}")
            prog.progress((i + 1) / len(run_ids), text=f"{i + 1}/{len(run_ids)} prompt")
        st.success(f"✅ Completato: {ok_total}/{att_total} risposte OK su {len(run_ids)} prompt.")
        st.cache_data.clear()  # dati cambiati → invalida la cache
        st.rerun()

# ----------------- Eliminazione prompt (pannello dedicato) -----------------
with st.expander("🗑 Elimina prompt", expanded=False):
    st.caption("Seleziona uno o più prompt dall'elenco, poi clicca **Elimina selezionati**. Nessuna eliminazione avviene in automatico.")

    id_to_label = {int(r.id): f"#{int(r.id)} · {str(r.prompt)[:70]}" for r in df.itertuples()}
    all_labels = list(id_to_label.values())
    label_to_id = {v: k for k, v in id_to_label.items()}

    bsa1, bsa2, _ = st.columns([1, 1, 3])
    if bsa1.button("Seleziona tutti", use_container_width=True):
        st.session_state["del_selection"] = all_labels
        st.rerun()
    if bsa2.button("Deseleziona", use_container_width=True):
        st.session_state["del_selection"] = []
        st.rerun()

    selected_labels = st.multiselect(
        "Prompt da eliminare",
        options=all_labels,
        key="del_selection",
        placeholder="Scegli i prompt…",
    )
    selected_ids = [label_to_id[l] for l in selected_labels if l in label_to_id]

    if st.button(
        f"🗑 Elimina selezionati ({len(selected_ids)})",
        type="primary",
        disabled=len(selected_ids) == 0,
        use_container_width=True,
    ):
        st.session_state["confirm_delete_ids"] = selected_ids

    # Conferma esplicita (azione irreversibile)
    pending = st.session_state.get("confirm_delete_ids")
    if pending:
        st.warning(
            f"⚠️ Stai per eliminare **{len(pending)} prompt** e TUTTE le risposte, "
            "citazioni e menzioni collegate. L'azione è **irreversibile**."
        )
        cc1, cc2, _ = st.columns([1, 1, 3])
        if cc1.button("Sì, elimina definitivamente", type="primary", use_container_width=True):
            n = ps.delete_prompts(pending)
            st.session_state.pop("confirm_delete_ids", None)
            st.session_state["del_selection"] = []
            st.success(f"✅ {n} prompt eliminati.")
            st.cache_data.clear()  # dati cambiati → invalida la cache
            st.rerun()
        if cc2.button("Annulla", use_container_width=True):
            st.session_state.pop("confirm_delete_ids", None)
            st.rerun()

st.markdown("**Apri un prompt** → vai alla pagina **Prompt Detail** e inserisci l'ID del prompt.")
st.markdown("Per esecuzione manuale di un prompt usa la pagina **Prompt Detail** o il CLI:")
st.code("python -m scripts.run_single_prompt --prompt-id <ID> --repeat 3", language="bash")
