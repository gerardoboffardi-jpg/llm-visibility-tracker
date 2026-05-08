"""Test per analyzer (mention detection, list position)."""
from __future__ import annotations

import pytest

from src.analyzer import (
    BrandEntry,
    BrandIndex,
    analyze_text,
    detect_mentions,
)


@pytest.fixture
def idx():
    return BrandIndex(brands=(
        BrandEntry(name="Talent Garden", aliases=("Talent Garden", "TAG", "talentgarden"), is_target=True),
        BrandEntry(name="WeWork", aliases=("WeWork",), is_target=False),
        BrandEntry(name="Copernico", aliases=("Copernico",), is_target=False),
    ))


def test_detect_simple(idx):
    text = "Talent Garden offre coworking. Anche WeWork è un'opzione."
    ms = detect_mentions(text, idx)
    assert len(ms) == 2
    assert ms[0].brand_name == "Talent Garden" and ms[0].is_target
    assert ms[1].brand_name == "WeWork" and not ms[1].is_target


def test_detect_no_partial_match(idx):
    """WeWorker non deve matchare WeWork."""
    text = "Sono un WeWorker felice."
    ms = detect_mentions(text, idx)
    assert ms == []


def test_detect_multiple_occurrences(idx):
    text = "Talent Garden a Milano. Talent Garden a Roma."
    ms = detect_mentions(text, idx)
    assert len(ms) == 2
    assert ms[0].position_in_text < ms[1].position_in_text


def test_detect_alias_dedup_same_position(idx):
    """Talent Garden + alias 'talentgarden' non devono produrre 2 mention sullo stesso punto."""
    text = "Talent Garden è qui."
    ms = detect_mentions(text, idx)
    # Solo 1 mention (anche se "Talent Garden" matcha entrambi gli alias)
    target_count = sum(1 for m in ms if m.is_target)
    assert target_count == 1


def test_list_position(idx):
    text = """Ecco i migliori coworking:
1. WeWork
2. Talent Garden
3. Copernico

Altre note."""
    ms = detect_mentions(text, idx)
    tg = next(m for m in ms if m.brand_name == "Talent Garden")
    assert tg.list_position == 2
    ww = next(m for m in ms if m.brand_name == "WeWork")
    assert ww.list_position == 1


def test_list_position_bullets(idx):
    text = """Spazi:
- WeWork
- Talent Garden
"""
    ms = detect_mentions(text, idx)
    tg = next(m for m in ms if m.brand_name == "Talent Garden")
    assert tg.list_position == 2


def test_no_list_position_for_inline(idx):
    text = "Talent Garden è una buona opzione, e anche WeWork."
    ms = detect_mentions(text, idx)
    assert all(m.list_position is None for m in ms)


def test_analyze_text_full(idx):
    text = "1. Talent Garden\n2. WeWork\n"
    result = analyze_text(text, brand_index=idx)
    assert result.has_target_mention is True
    assert result.target_position_in_list == 1
    assert len(result.mentions) == 2


def test_analyze_empty_text(idx):
    result = analyze_text("", brand_index=idx)
    assert result.has_target_mention is False
    assert result.mentions == []


def test_context_snippet_present(idx):
    text = "blah " * 50 + "Talent Garden " + "blah " * 50
    ms = detect_mentions(text, idx)
    assert len(ms) == 1
    assert "Talent Garden" in ms[0].context_snippet
    assert len(ms[0].context_snippet) > 50


def test_loads_real_brand_index():
    from src.analyzer import load_brand_index
    idx = load_brand_index()
    target_brands = [b for b in idx.brands if b.is_target]
    assert len(target_brands) == 1
    assert target_brands[0].name == "Talent Garden"
    assert any(b.name == "WeWork" for b in idx.brands)
