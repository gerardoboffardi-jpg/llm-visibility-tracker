"""CRUD service per i prompt + statistiche aggregate.

Usato da CLI/script e dal dispatcher GitHub Actions (scripts/gh_action.py).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import yaml
from rapidfuzz import fuzz
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.storage import Prompt, Response, get_session


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PromptStats:
    """Statistiche aggregate per un singolo prompt."""

    prompt_id: int
    n_responses: int
    n_models: int
    citation_rate: float  # 0..1
    mention_rate: float  # 0..1
    last_run_at: datetime | None


@dataclass
class DuplicateWarning:
    existing_id: int
    existing_text: str
    similarity: float


class DuplicatePromptError(Exception):
    def __init__(self, warning: DuplicateWarning):
        self.warning = warning
        super().__init__(
            f"Prompt simile già esistente (id={warning.existing_id}, "
            f"similarity={warning.similarity:.2f}): {warning.existing_text!r}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


DEFAULT_DEDUP_THRESHOLD = 0.90


def _find_similar_prompt(
    session: Session, text: str, threshold: float = DEFAULT_DEDUP_THRESHOLD
) -> DuplicateWarning | None:
    """Cerca prompt simili sopra la soglia. Ritorna il primo match (più simile)."""
    text_norm = text.strip().lower()
    best: DuplicateWarning | None = None
    for p in session.scalars(select(Prompt)).all():
        sim = fuzz.ratio(text_norm, p.text.strip().lower()) / 100.0
        if sim >= threshold and (best is None or sim > best.similarity):
            best = DuplicateWarning(existing_id=p.id, existing_text=p.text, similarity=sim)
    return best


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def list_prompts(
    session: Session | None = None,
    *,
    only_active: bool | None = None,
    category: str | None = None,
    geo: str | None = None,
    search: str | None = None,
) -> list[Prompt]:
    own_session = session is None
    s = session or get_session()
    try:
        stmt = select(Prompt)
        if only_active is True:
            stmt = stmt.where(Prompt.is_active.is_(True))
        elif only_active is False:
            stmt = stmt.where(Prompt.is_active.is_(False))
        if category:
            stmt = stmt.where(Prompt.category == category)
        if geo:
            stmt = stmt.where(Prompt.geo == geo)
        if search:
            stmt = stmt.where(Prompt.text.ilike(f"%{search}%"))
        stmt = stmt.order_by(Prompt.created_at.desc())
        return list(s.scalars(stmt).all())
    finally:
        if own_session:
            s.close()


def get_prompt(prompt_id: int, session: Session | None = None) -> Prompt | None:
    own_session = session is None
    s = session or get_session()
    try:
        return s.get(Prompt, prompt_id)
    finally:
        if own_session:
            s.close()


def get_prompt_stats(prompt_id: int, session: Session | None = None) -> PromptStats:
    own_session = session is None
    s = session or get_session()
    try:
        n_responses = s.scalar(
            select(func.count(Response.id)).where(Response.prompt_id == prompt_id)
        ) or 0
        n_models = s.scalar(
            select(func.count(func.distinct(Response.model_id))).where(
                Response.prompt_id == prompt_id
            )
        ) or 0
        last_run_at = s.scalar(
            select(func.max(Response.created_at)).where(Response.prompt_id == prompt_id)
        )
        if n_responses > 0:
            n_citations = s.scalar(
                select(func.count(Response.id)).where(
                    Response.prompt_id == prompt_id,
                    Response.has_target_citation.is_(True),
                )
            ) or 0
            n_mentions = s.scalar(
                select(func.count(Response.id)).where(
                    Response.prompt_id == prompt_id,
                    Response.has_target_mention.is_(True),
                )
            ) or 0
            citation_rate = n_citations / n_responses
            mention_rate = n_mentions / n_responses
        else:
            citation_rate = 0.0
            mention_rate = 0.0
        return PromptStats(
            prompt_id=prompt_id,
            n_responses=n_responses,
            n_models=n_models,
            citation_rate=citation_rate,
            mention_rate=mention_rate,
            last_run_at=last_run_at,
        )
    finally:
        if own_session:
            s.close()


def create_prompt(
    text: str,
    *,
    category: str | None = None,
    geo: str | None = None,
    intent: str | None = None,
    notes: str | None = None,
    created_by: str | None = None,
    force: bool = False,
    dedup_threshold: float = DEFAULT_DEDUP_THRESHOLD,
    session: Session | None = None,
) -> Prompt:
    """Crea un nuovo prompt. Se trova un prompt simile sopra la soglia e
    `force=False`, solleva `DuplicatePromptError`."""
    text = text.strip()
    if not text:
        raise ValueError("Il testo del prompt non può essere vuoto.")

    own_session = session is None
    s = session or get_session()
    try:
        if not force:
            warning = _find_similar_prompt(s, text, dedup_threshold)
            if warning is not None:
                # Se è esattamente identico, ritorna l'esistente direttamente
                if warning.similarity >= 0.999:
                    existing = s.get(Prompt, warning.existing_id)
                    if existing:
                        return existing
                raise DuplicatePromptError(warning)
        else:
            # Anche con force=True evita di violare il vincolo UNIQUE: se esiste
            # già un prompt con lo stesso testo, restituiscilo (idempotente)
            existing = s.scalar(select(Prompt).where(Prompt.text == text))
            if existing is not None:
                return existing

        prompt = Prompt(
            text=text,
            category=category,
            geo=geo,
            intent=intent,
            notes=notes,
            created_by=created_by or "ui",
            is_active=True,
        )
        s.add(prompt)
        s.commit()
        s.refresh(prompt)
        return prompt
    finally:
        if own_session:
            s.close()


def update_prompt(
    prompt_id: int,
    *,
    text: str | None = None,
    category: str | None = None,
    geo: str | None = None,
    intent: str | None = None,
    notes: str | None = None,
    session: Session | None = None,
) -> Prompt:
    own_session = session is None
    s = session or get_session()
    try:
        prompt = s.get(Prompt, prompt_id)
        if prompt is None:
            raise ValueError(f"Prompt id={prompt_id} non trovato.")
        if text is not None:
            prompt.text = text.strip()
        if category is not None:
            prompt.category = category
        if geo is not None:
            prompt.geo = geo
        if intent is not None:
            prompt.intent = intent
        if notes is not None:
            prompt.notes = notes
        prompt.updated_at = datetime.utcnow()
        s.commit()
        s.refresh(prompt)
        return prompt
    finally:
        if own_session:
            s.close()


def set_prompt_active(prompt_id: int, active: bool, session: Session | None = None) -> Prompt:
    own_session = session is None
    s = session or get_session()
    try:
        prompt = s.get(Prompt, prompt_id)
        if prompt is None:
            raise ValueError(f"Prompt id={prompt_id} non trovato.")
        prompt.is_active = active
        prompt.updated_at = datetime.utcnow()
        s.commit()
        s.refresh(prompt)
        return prompt
    finally:
        if own_session:
            s.close()


def deactivate_prompt(prompt_id: int, session: Session | None = None) -> Prompt:
    return set_prompt_active(prompt_id, False, session=session)


def activate_prompt(prompt_id: int, session: Session | None = None) -> Prompt:
    return set_prompt_active(prompt_id, True, session=session)


# ---------------------------------------------------------------------------
# Eliminazione
# ---------------------------------------------------------------------------


def delete_prompt(prompt_id: int, session: Session | None = None) -> bool:
    """Elimina un prompt e TUTTE le risposte collegate (con citazioni/menzioni
    via cascade ORM). Ritorna True se il prompt esisteva ed è stato eliminato.

    Azione IRREVERSIBILE.
    """
    own_session = session is None
    s = session or get_session()
    try:
        prompt = s.get(Prompt, prompt_id)
        if prompt is None:
            return False
        # Elimina prima le risposte (la cascade su Response → citations/mentions
        # rimuove anche quelle), altrimenti il vincolo FK blocca la delete.
        responses = list(s.scalars(select(Response).where(Response.prompt_id == prompt_id)))
        for r in responses:
            s.delete(r)
        s.delete(prompt)
        s.commit()
        return True
    finally:
        if own_session:
            s.close()


def delete_prompts(prompt_ids: Iterable[int], session: Session | None = None) -> int:
    """Elimina più prompt in un'unica transazione. Ritorna il numero di prompt
    effettivamente eliminati. Azione IRREVERSIBILE."""
    own_session = session is None
    s = session or get_session()
    deleted = 0
    try:
        for pid in prompt_ids:
            prompt = s.get(Prompt, pid)
            if prompt is None:
                continue
            for r in list(s.scalars(select(Response).where(Response.prompt_id == pid))):
                s.delete(r)
            s.delete(prompt)
            deleted += 1
        s.commit()
        return deleted
    finally:
        if own_session:
            s.close()


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------


@dataclass
class BulkImportResult:
    added: int
    skipped_duplicates: int
    skipped_invalid: int
    duplicates: list[DuplicateWarning]


def _iter_records_from_yaml(content: str) -> Iterable[dict]:
    data = yaml.safe_load(content)
    if not isinstance(data, list):
        raise ValueError("Il file YAML deve contenere una lista di prompt.")
    return data


def _iter_records_from_csv(content: str) -> Iterable[dict]:
    reader = csv.DictReader(io.StringIO(content))
    yield from reader


def bulk_import(
    content: str,
    *,
    fmt: str = "yaml",
    dedup_threshold: float = DEFAULT_DEDUP_THRESHOLD,
    session: Session | None = None,
) -> BulkImportResult:
    """Importa prompt in massa da YAML o CSV (colonne: text, category, geo, intent, notes)."""
    if fmt not in {"yaml", "csv"}:
        raise ValueError("fmt deve essere 'yaml' o 'csv'")

    records = list(
        _iter_records_from_yaml(content) if fmt == "yaml" else _iter_records_from_csv(content)
    )

    own_session = session is None
    s = session or get_session()
    added = 0
    skipped_dup = 0
    skipped_invalid = 0
    duplicates: list[DuplicateWarning] = []
    try:
        for rec in records:
            text = (rec.get("text") or "").strip()
            if not text:
                skipped_invalid += 1
                continue
            warning = _find_similar_prompt(s, text, dedup_threshold)
            if warning is not None:
                duplicates.append(warning)
                skipped_dup += 1
                continue
            s.add(
                Prompt(
                    text=text,
                    category=rec.get("category"),
                    geo=rec.get("geo"),
                    intent=rec.get("intent"),
                    notes=rec.get("notes"),
                    created_by=rec.get("created_by", "import"),
                    is_active=True,
                )
            )
            added += 1
        s.commit()
    finally:
        if own_session:
            s.close()

    return BulkImportResult(
        added=added,
        skipped_duplicates=skipped_dup,
        skipped_invalid=skipped_invalid,
        duplicates=duplicates,
    )


def bulk_import_file(path: str | Path, **kwargs) -> BulkImportResult:
    p = Path(path)
    fmt = "yaml" if p.suffix.lower() in {".yaml", ".yml"} else "csv"
    return bulk_import(p.read_text(encoding="utf-8"), fmt=fmt, **kwargs)
