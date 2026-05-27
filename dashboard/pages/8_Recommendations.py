"""🎯 Recommendations — suggerimenti AEO/SEO per chiudere il citation gap."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from dashboard.auth import require_password
from dashboard.style import (
    CORAL,
    apply_style,
    page_header,
    render_sidebar,
    section_header,
)
from src import prompt_service as ps
from src.recommender import Recommendation, generate_all

st.set_page_config(page_title="Recommendations", page_icon="🎯", layout="wide")
apply_style()
if not require_password():
    st.stop()

render_sidebar()

page_header(
    icon="🎯",
    title="Recommendations",
    sub="Suggerimenti AEO/SEO per chiudere il citation gap — derivati dai dati raccolti.",
)

recs: list[Recommendation] = generate_all()

if not recs:
    st.info(
        "Nessun suggerimento ancora. Esegui qualche batch (su 📝 Prompts o via CLI) "
        "per raccogliere dati su cui basare le raccomandazioni."
    )
    st.stop()

# ---------------- Summary chips ----------------
sev_counts = {"high": 0, "medium": 0, "low": 0}
for r in recs:
    sev_counts[r.severity] = sev_counts.get(r.severity, 0) + 1

c1, c2, c3, c4 = st.columns(4)
c1.metric("Totale", len(recs))
c2.metric("🔴 Alta priorità", sev_counts["high"])
c3.metric("🟡 Media priorità", sev_counts["medium"])
c4.metric("🔵 Bassa priorità", sev_counts["low"])

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ---------------- Filtri ----------------
f1, f2, f3 = st.columns([1, 2, 2])
with f1:
    sev_filter = st.selectbox(
        "Filtra per priorità",
        ["Tutte", "🔴 Alta", "🟡 Media", "🔵 Bassa"],
    )
with f2:
    cats = sorted({r.category for r in recs})
    cat_filter = st.multiselect(
        "Filtra per categoria",
        options=cats,
        placeholder="Tutte le categorie",
    )
with f3:
    # Lista prompt correlati alle recommendations
    all_related_ids = sorted({pid for r in recs for pid in r.related_ids})
    if all_related_ids:
        prompts_by_id = {p.id: p for p in ps.list_prompts()}
        prompt_filter = st.multiselect(
            "Filtra per prompt",
            options=all_related_ids,
            format_func=lambda pid: (
                f"#{pid} · {prompts_by_id[pid].text[:60]}…"
                if pid in prompts_by_id and len(prompts_by_id[pid].text) > 60
                else (f"#{pid} · {prompts_by_id[pid].text}" if pid in prompts_by_id else f"#{pid}")
            ),
            placeholder="Tutti i prompt correlati",
        )
    else:
        prompt_filter = []
        st.caption("Nessun prompt correlato a queste recommendations.")

# Applica filtri
filtered = recs
if sev_filter == "🔴 Alta":
    filtered = [r for r in filtered if r.severity == "high"]
elif sev_filter == "🟡 Media":
    filtered = [r for r in filtered if r.severity == "medium"]
elif sev_filter == "🔵 Bassa":
    filtered = [r for r in filtered if r.severity == "low"]
if cat_filter:
    filtered = [r for r in filtered if r.category in cat_filter]
if prompt_filter:
    # Mostra solo recommendations che hanno almeno un prompt_id in prompt_filter
    filtered = [r for r in filtered if any(pid in prompt_filter for pid in r.related_ids)]

st.caption(f"{len(filtered)} suggerimenti mostrati su {len(recs)} totali")

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ---------------- Card per ogni recommendation ----------------
SEV_COLORS = {
    "high":   ("#DC2626", "#FEF2F2", "🔴 Alta"),
    "medium": ("#F59E0B", "#FFFBEB", "🟡 Media"),
    "low":    ("#3B82F6", "#EFF6FF", "🔵 Bassa"),
}

for r in filtered:
    color, bg, sev_label = SEV_COLORS.get(r.severity, ("#64748B", "#F1F5F9", r.severity))

    # Header card
    st.markdown(
        f"""
        <div class="tag-rec-card">
            <div class="tag-rec-head">
                <div class="tag-rec-icon" style="background:{bg};color:{color}">
                    {r.icon}
                </div>
                <div style="flex:1">
                    <div class="tag-rec-meta">
                        <span class="tag-rec-sev" style="background:{bg};color:{color}">
                            {sev_label}
                        </span>
                        <span class="tag-rec-cat">{r.category}</span>
                    </div>
                    <div class="tag-rec-title">{r.title}</div>
                </div>
            </div>
            <div class="tag-rec-why">
                <strong>Perché:</strong> {r.why}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Action items
    with st.expander(f"📋 {len(r.actions)} azioni consigliate", expanded=(r.severity == "high")):
        for i, action in enumerate(r.actions, start=1):
            st.markdown(f"**{i}.** {action}")

        if r.related_ids:
            st.markdown("---")
            st.markdown("**Prompt correlati:**")
            for pid in r.related_ids[:5]:
                st.markdown(
                    f"- 🔬 [Apri Prompt #{pid}](/Prompt_Detail?prompt_id={pid})"
                )
            if len(r.related_ids) > 5:
                st.caption(f"+ altri {len(r.related_ids) - 5} prompt")

        if r.related_domains:
            st.markdown("---")
            st.markdown("**Domini correlati:** " + ", ".join(
                f"`{d}`" for d in r.related_domains[:8]
            ))

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)


# ---------------- AI summary (opzionale, on-demand) ----------------
st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
section_header(
    eyebrow="Bonus AI",
    title="Genera un piano d'azione narrativo",
    sub="Usa Claude per trasformare i suggerimenti sopra in un piano d'azione "
        "discorsivo da condividere col team.",
)

if st.button("🤖 Genera piano d'azione AI", type="primary"):
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.error("ANTHROPIC_API_KEY non configurato.")
    else:
        from dashboard.utils import fun_loader
        with st.spinner(fun_loader("Claude sta analizzando i dati e scrivendo il piano…")):
            try:
                import anthropic
                client = anthropic.Anthropic()
                bullet = []
                for r in recs[:10]:
                    bullet.append(
                        f"- [{r.severity.upper()}] {r.category}: {r.title}\n"
                        f"  Motivazione: {r.why}\n"
                        f"  Azioni: {' | '.join(r.actions[:3])}"
                    )
                user_msg = (
                    "Sei un SEO/AEO strategist. Dato il seguente elenco di suggerimenti "
                    "data-driven generati per il brand Talent Garden (talentgarden.com), "
                    "scrivimi un **piano d'azione di 4-6 settimane** in italiano:\n\n"
                    + "\n".join(bullet)
                    + "\n\nFormato: paragrafi brevi, suddiviso per settimana, con priorità chiare. "
                    "Includi una nota finale su KPI da monitorare."
                )
                resp = client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=2000,
                    messages=[{"role": "user", "content": user_msg}],
                )
                text = "".join(b.text for b in resp.content if hasattr(b, "text"))
                st.markdown("### 📋 Piano d'azione")
                st.markdown(text)
            except Exception as e:  # noqa: BLE001
                st.error(f"Errore: {e}")
