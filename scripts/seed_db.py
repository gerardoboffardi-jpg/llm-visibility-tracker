"""Script idempotente per inizializzare DB e popolare prompt + competitor_domains.

Uso:
    python -m scripts.seed_db
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.storage import CompetitorDomain, Prompt, init_db, get_session  # noqa: E402

CONFIG_DIR = ROOT / "config"


def load_yaml(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def seed_competitor_domains(session, brands_cfg: dict) -> tuple[int, int]:
    added = 0
    skipped = 0
    for comp in brands_cfg.get("competitors", []):
        for domain in comp.get("domains", []):
            domain_norm = domain.lower().strip()
            existing = session.query(CompetitorDomain).filter_by(domain=domain_norm).first()
            if existing:
                skipped += 1
                continue
            session.add(CompetitorDomain(brand_name=comp["name"], domain=domain_norm))
            added += 1
    session.commit()
    return added, skipped


def seed_prompts(session, prompts_cfg: list[dict]) -> tuple[int, int]:
    added = 0
    skipped = 0
    for p in prompts_cfg:
        text = p["text"].strip()
        existing = session.query(Prompt).filter_by(text=text).first()
        if existing:
            skipped += 1
            continue
        session.add(
            Prompt(
                text=text,
                category=p.get("category"),
                geo=p.get("geo"),
                intent=p.get("intent"),
                is_active=True,
                created_by="seed",
            )
        )
        added += 1
    session.commit()
    return added, skipped


def main() -> None:
    print("→ Inizializzazione schema DB...")
    init_db()

    brands_cfg = load_yaml(CONFIG_DIR / "brands.yaml")
    prompts_cfg = load_yaml(CONFIG_DIR / "seed_prompts.yaml")

    with get_session() as session:
        c_added, c_skipped = seed_competitor_domains(session, brands_cfg)
        print(f"→ Competitor domains: {c_added} aggiunti, {c_skipped} già presenti")

        p_added, p_skipped = seed_prompts(session, prompts_cfg)
        print(f"→ Prompt: {p_added} aggiunti, {p_skipped} già presenti")

    print("✓ Seed completato.")


if __name__ == "__main__":
    main()
