"""Recommendations engine per chiudere il citation gap (AEO/SEO).

Genera suggerimenti rule-based dai dati di visibility:
- prompt con citation gap → contenuti canonici mancanti
- competitor che vincono → comparativi da scrivere
- domini neutri ricorrenti (Wikipedia, magazine) → guest post / link building
- prompt mai eseguiti → primi run per misurare
- categorie con basso citation rate → priorità di intervento

Ogni recommendation ha severity (high/medium/low), titolo, motivazione
data-driven, action items concreti.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import Integer, func, select

from src.storage import Citation, Prompt, Response, get_session


Severity = Literal["high", "medium", "low"]


@dataclass
class Recommendation:
    severity: Severity
    icon: str  # emoji
    category: str  # "Citation gap" / "Competitor" / "Link building" / ...
    title: str
    why: str  # motivazione data-driven (numeri concreti)
    actions: list[str]  # action items
    related_ids: list[int] = field(default_factory=list)  # prompt_id correlati
    related_domains: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rule-based recommenders
# ---------------------------------------------------------------------------


def _gap_recommendations() -> list[Recommendation]:
    """Prompt dove TAG è menzionato nel testo ma il dominio NON viene citato."""
    out: list[Recommendation] = []
    with get_session() as s:
        # Aggrega per prompt
        rows = s.execute(
            select(
                Prompt.id,
                Prompt.text,
                Prompt.category,
                Prompt.geo,
                func.count(Response.id).label("n_resp"),
                func.sum(
                    func.coalesce(Response.has_target_mention.cast(Integer), 0)
                ).label("n_men"),
                func.sum(
                    func.coalesce(Response.has_target_citation.cast(Integer), 0)
                ).label("n_cit"),
            )
            .join(Response, Response.prompt_id == Prompt.id)
            .group_by(Prompt.id, Prompt.text, Prompt.category, Prompt.geo)
            .having(func.count(Response.id) > 0)
        ).all()

    # Filtra gap (menzionato senza citazione) ordinato per severità
    gap_rows = []
    for r in rows:
        n_resp = r.n_resp or 0
        n_men = r.n_men or 0
        n_cit = r.n_cit or 0
        if n_resp == 0:
            continue
        men_rate = n_men / n_resp
        cit_rate = n_cit / n_resp
        gap = max(0.0, men_rate - cit_rate)
        if gap >= 0.5:
            gap_rows.append((r, gap, men_rate, cit_rate))

    gap_rows.sort(key=lambda x: x[1], reverse=True)
    top = gap_rows[:5]

    if not top:
        return out

    # Una recommendation per ogni prompt con gap alto
    for r, gap, men_rate, cit_rate in top:
        sev: Severity = "high" if gap >= 0.8 else "medium"
        out.append(
            Recommendation(
                severity=sev,
                icon="⚠️",
                category="Citation gap",
                title=f'Crea contenuto canonico per "{r.text[:60]}…"' if len(r.text) > 60 else f'Crea contenuto canonico per "{r.text}"',
                why=(
                    f"Su {int(r.n_resp)} risposte LLM, Talent Garden è menzionato nel testo "
                    f"il {men_rate*100:.0f}% delle volte ma il dominio talentgarden.com è citato "
                    f"solo il {cit_rate*100:.0f}%. Gap = {gap*100:.0f} punti percentuali."
                ),
                actions=[
                    f"Identifica la query intent (categoria: {r.category or '—'}, geo: {r.geo or '—'})",
                    "Crea una pagina dedicata sul sito talentgarden.com che risponda esattamente a questa domanda",
                    "Ottimizza meta description e H1 con keyword esplicita (helpful content)",
                    "Aggiungi structured data (FAQ / HowTo) per essere parsato meglio dagli LLM",
                    "Pubblica e attendi 2-3 settimane per re-test, poi rilancia il prompt",
                ],
                related_ids=[r.id],
            )
        )
    return out


def _competitor_recommendations() -> list[Recommendation]:
    """Competitor con più citazioni: opportunità di scrivere contenuti comparativi."""
    out: list[Recommendation] = []
    with get_session() as s:
        rows = s.execute(
            select(
                Citation.domain,
                func.count(Citation.id).label("n_cit"),
                func.count(func.distinct(Response.prompt_id)).label("n_prompts"),
            )
            .join(Response, Response.id == Citation.response_id)
            .where(Citation.is_competitor_domain.is_(True))
            .group_by(Citation.domain)
            .order_by(func.count(Citation.id).desc())
            .limit(5)
        ).all()

    if not rows:
        return out

    # Recommendation aggregata per i top 3 competitor
    top3 = rows[:3]
    domains_str = ", ".join(f"{r.domain} ({int(r.n_cit)} cit.)" for r in top3)

    out.append(
        Recommendation(
            severity="high",
            icon="🏁",
            category="Competitor",
            title="Pubblica pagine comparative vs i competitor che vincono",
            why=(
                f"I top competitor citati dagli LLM nei prompt monitorati sono: {domains_str}. "
                f"Gli LLM li scelgono come fonte di riferimento — significa che hanno contenuti "
                f"più strutturati o canonici sui nostri stessi argomenti."
            ),
            actions=[
                "Crea pagine \"Talent Garden vs [Competitor]\" sui prodotti/servizi sovrapposti",
                "Inquadra differenze oggettive (prezzo, location, format) — gli LLM preferiscono comparativi neutri",
                "Linka internamente da pagine già autorevoli (es. blog post di link building, magazine TAG)",
                "Aggiungi tabelle comparative (markdown-friendly, gli LLM le parsano meglio)",
                f"Considera priorità per: {top3[0].domain}",
            ],
            related_domains=[r.domain for r in top3],
        )
    )
    return out


def _link_building_recommendations() -> list[Recommendation]:
    """Domini neutri (Wikipedia, magazine, directory) ricorrenti → guest post / link building."""
    out: list[Recommendation] = []
    with get_session() as s:
        rows = s.execute(
            select(
                Citation.domain,
                func.count(Citation.id).label("n_cit"),
                func.count(func.distinct(Response.prompt_id)).label("n_prompts"),
            )
            .join(Response, Response.id == Citation.response_id)
            .where(
                Citation.is_target_domain.is_(False),
                Citation.is_competitor_domain.is_(False),
            )
            .group_by(Citation.domain)
            .order_by(func.count(Citation.id).desc())
            .limit(8)
        ).all()

    # Filtra quelli con frequenza significativa
    significant = [r for r in rows if r.n_cit >= 3]
    if not significant:
        return out

    top5 = significant[:5]
    domains_str = ", ".join(f"{r.domain} ({int(r.n_cit)})" for r in top5)

    out.append(
        Recommendation(
            severity="medium",
            icon="🔗",
            category="Link building",
            title="Sfrutta i domini neutri citati dagli LLM",
            why=(
                f"Gli LLM citano ricorrentemente fonti terze neutre: {domains_str}. "
                f"Se appari in queste pagine (guest post, intervista, citation building), "
                f"aumenti le probabilità di essere a tua volta menzionato dagli LLM."
            ),
            actions=[
                "Identifica autori/editor delle pagine ricorrenti e proponi guest post",
                "Wikipedia: verifica se TAG ha una voce in italiano (e ne migliora qualità)",
                "Magazine/blog di settore: proponi case study o intervista founder",
                "Directory verticali (coworking, education): verifica presenza e aggiorna scheda",
                f"Priorità per: {top5[0].domain}",
            ],
            related_domains=[r.domain for r in top5],
        )
    )
    return out


def _never_executed_recommendations() -> list[Recommendation]:
    """Prompt mai eseguiti → priorità di misurazione."""
    with get_session() as s:
        sub = (
            select(Response.prompt_id, func.count(Response.id).label("n"))
            .group_by(Response.prompt_id)
            .subquery()
        )
        rows = s.execute(
            select(Prompt.id, Prompt.text)
            .outerjoin(sub, sub.c.prompt_id == Prompt.id)
            .where(Prompt.is_active.is_(True))
            .where((sub.c.n.is_(None)) | (sub.c.n == 0))
            .limit(10)
        ).all()

    if not rows:
        return []

    return [
        Recommendation(
            severity="low",
            icon="📝",
            category="Misurazione",
            title=f"Esegui i {len(rows)} prompt attivi che non hanno ancora risposte",
            why=(
                f"Ci sono {len(rows)} prompt nella lista che non hanno mai generato "
                f"risposte: non sai ancora come performano. Senza dati non puoi prioritizzare."
            ),
            actions=[
                "Vai su 🔬 Prompt Detail per ognuno e clicca \"▶ Rilancia\" con repeat=3",
                "Oppure usa CLI: `python -m scripts.run_batch --repeat 3`",
                "Tempo stimato: ~30 sec/prompt × N modelli × 3 ripetizioni",
            ],
            related_ids=[r.id for r in rows],
        )
    ]


def _category_recommendations() -> list[Recommendation]:
    """Categorie con citation rate basso → focus content strategy."""
    with get_session() as s:
        rows = s.execute(
            select(
                Prompt.category,
                func.count(Response.id).label("n_resp"),
                func.sum(
                    func.coalesce(Response.has_target_citation.cast(Integer), 0)
                ).label("n_cit"),
            )
            .join(Response, Response.prompt_id == Prompt.id)
            .where(Prompt.category.isnot(None))
            .group_by(Prompt.category)
            .having(func.count(Response.id) >= 5)
        ).all()

    if not rows:
        return []

    cat_data = []
    for r in rows:
        cit_rate = (r.n_cit or 0) / (r.n_resp or 1)
        cat_data.append((r.category, cit_rate, int(r.n_resp)))

    weak = sorted([c for c in cat_data if c[1] < 0.20], key=lambda x: x[1])[:3]
    if not weak:
        return []

    out: list[Recommendation] = []
    for cat, cit_rate, n_resp in weak:
        out.append(
            Recommendation(
                severity="medium" if cit_rate < 0.10 else "low",
                icon="🎯",
                category="Content strategy",
                title=f"Categoria \"{cat}\": citation rate basso ({cit_rate*100:.0f}%)",
                why=(
                    f"Sulla categoria \"{cat}\" abbiamo {n_resp} risposte LLM ma "
                    f"talentgarden.com è citato solo nel {cit_rate*100:.0f}% dei casi. "
                    f"Significa che il sito non ha contenuti sufficientemente canonici/autorevoli "
                    f"per questo tema."
                ),
                actions=[
                    f"Mappa i prompt della categoria \"{cat}\" e identifica i temi senza pagina dedicata",
                    "Definisci una content roadmap di 4-6 articoli mirati",
                    "Includi nella roadmap pillar page + cluster pages collegate (topic cluster SEO)",
                    "Usa keyword tool per validare il volume di ricerca prima di scrivere",
                ],
            )
        )
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_all() -> list[Recommendation]:
    """Genera tutti i suggerimenti, ordinati per severity desc."""
    recs: list[Recommendation] = []
    recs.extend(_gap_recommendations())
    recs.extend(_competitor_recommendations())
    recs.extend(_link_building_recommendations())
    recs.extend(_category_recommendations())
    recs.extend(_never_executed_recommendations())
    # Ordina: high → medium → low
    order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: order.get(r.severity, 9))
    return recs
