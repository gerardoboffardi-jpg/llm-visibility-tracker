"""Test del prompt_service usando un DB SQLite in-memory."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.storage import Base, Response, Run
from src import prompt_service as ps


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_create_and_list(session):
    p = ps.create_prompt("Coworking a Milano centro", category="coworking", session=session)
    assert p.id is not None
    assert p.is_active is True

    prompts = ps.list_prompts(session=session)
    assert len(prompts) == 1
    assert prompts[0].text == "Coworking a Milano centro"


def test_create_duplicate_raises(session):
    ps.create_prompt("Coworking a Milano centro", session=session)
    with pytest.raises(ps.DuplicatePromptError) as excinfo:
        # variazione minima: dovrebbe matchare con high similarity
        ps.create_prompt("Coworking a Milano centro!", session=session)
    assert excinfo.value.warning.similarity >= 0.90


def test_create_duplicate_force(session):
    ps.create_prompt("Coworking a Milano centro", session=session)
    p2 = ps.create_prompt("Coworking a Milano centro!", force=True, session=session)
    assert p2.id is not None
    assert len(ps.list_prompts(session=session)) == 2


def test_create_exact_duplicate_returns_existing(session):
    p1 = ps.create_prompt("Coworking a Milano", session=session)
    p2 = ps.create_prompt("Coworking a Milano", session=session)
    assert p1.id == p2.id


def test_update_prompt(session):
    p = ps.create_prompt("Coworking a Roma", session=session)
    ps.update_prompt(p.id, category="coworking", geo="Roma", session=session)
    refreshed = ps.get_prompt(p.id, session=session)
    assert refreshed.category == "coworking"
    assert refreshed.geo == "Roma"


def test_deactivate_activate(session):
    p = ps.create_prompt("Coworking a Torino", session=session)
    ps.deactivate_prompt(p.id, session=session)
    assert ps.get_prompt(p.id, session=session).is_active is False
    ps.activate_prompt(p.id, session=session)
    assert ps.get_prompt(p.id, session=session).is_active is True


def test_filters(session):
    ps.create_prompt("Q1", category="coworking", geo="Milano", session=session)
    ps.create_prompt("Q2", category="formazione", geo="Roma", session=session)
    ps.create_prompt("Q3 milano", category="coworking", geo="Milano", session=session)

    assert len(ps.list_prompts(session=session, category="coworking")) == 2
    assert len(ps.list_prompts(session=session, geo="Roma")) == 1
    assert len(ps.list_prompts(session=session, search="milano")) == 1  # solo "Q3 milano" matcha sul testo


def test_stats_no_responses(session):
    p = ps.create_prompt("Prompt senza risposte", session=session)
    stats = ps.get_prompt_stats(p.id, session=session)
    assert stats.n_responses == 0
    assert stats.citation_rate == 0.0
    assert stats.last_run_at is None


def test_stats_with_responses(session):
    p = ps.create_prompt("Prompt con risposte", session=session)
    run = Run(trigger_type="test")
    session.add(run)
    session.flush()

    # 3 responses: 2 con citation, 1 senza; tutte con mention
    for i, has_cit in enumerate([True, True, False]):
        session.add(
            Response(
                run_id=run.id,
                prompt_id=p.id,
                model_id=f"model-{i % 2}",
                text="dummy",
                has_target_mention=True,
                has_target_citation=has_cit,
            )
        )
    session.commit()

    stats = ps.get_prompt_stats(p.id, session=session)
    assert stats.n_responses == 3
    assert stats.n_models == 2
    assert stats.citation_rate == pytest.approx(2 / 3)
    assert stats.mention_rate == 1.0
    assert stats.last_run_at is not None


def test_bulk_import_yaml(session):
    yaml_content = """
- text: Prompt A
  category: coworking
- text: Prompt B
  category: formazione
- text: ""
"""
    result = ps.bulk_import(yaml_content, fmt="yaml", session=session)
    assert result.added == 2
    assert result.skipped_invalid == 1
    assert result.skipped_duplicates == 0


def test_bulk_import_dedup(session):
    ps.create_prompt("Coworking a Milano", session=session)
    yaml_content = """
- text: Coworking a Milano
- text: Nuovo prompt
"""
    result = ps.bulk_import(yaml_content, fmt="yaml", session=session)
    assert result.added == 1
    assert result.skipped_duplicates == 1
    assert len(result.duplicates) == 1


def test_bulk_import_csv(session):
    csv_content = "text,category,geo\nPrompt CSV 1,coworking,Milano\nPrompt CSV 2,formazione,Roma\n"
    result = ps.bulk_import(csv_content, fmt="csv", session=session)
    assert result.added == 2
