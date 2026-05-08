"""Test per citation_analyzer."""
from __future__ import annotations

import pytest

from src.citation_analyzer import (
    BrandConfig,
    analyze_citations,
    extract_domain,
    normalize_url,
)
from src.providers.base import Citation


@pytest.fixture
def cfg():
    return BrandConfig(
        target_domains=frozenset({"talentgarden.com"}),
        target_name="Talent Garden",
        competitor_domains={
            "wework.com": "WeWork",
            "copernicomilano.it": "Copernico",
            "regus.com": "Regus",
        },
    )


# ---------- normalize_url ----------

def test_normalize_strips_tracking_params():
    out = normalize_url("https://example.com/path?utm_source=google&id=42&fbclid=abc")
    assert out == "https://example.com/path?id=42"


def test_normalize_lowercases_host():
    assert normalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path"


def test_normalize_strips_trailing_slash():
    assert normalize_url("https://example.com/path/") == "https://example.com/path"
    # Root path resta
    assert normalize_url("https://example.com/") == "https://example.com/"


def test_normalize_removes_fragment():
    assert normalize_url("https://example.com/page#section") == "https://example.com/page"


def test_normalize_empty():
    assert normalize_url("") == ""


# ---------- extract_domain ----------

def test_extract_domain_basic():
    assert extract_domain("https://www.talentgarden.com/it/coworking") == "talentgarden.com"


def test_extract_domain_subdomain():
    assert extract_domain("https://blog.talentgarden.com/post") == "talentgarden.com"


def test_extract_domain_country_tld():
    assert extract_domain("https://copernicomilano.it/spazi") == "copernicomilano.it"


def test_extract_domain_empty():
    assert extract_domain("") == ""
    assert extract_domain("not-a-url") == ""


# ---------- analyze_citations ----------

def test_target_classification(cfg):
    cits = [
        Citation(url="https://www.talentgarden.com/it/", position=1, title="TAG"),
        Citation(url="https://wework.com/it/milano", position=2),
        Citation(url="https://wikipedia.org/coworking", position=3),
    ]
    result = analyze_citations(cits, cfg)
    assert result.total == 3
    assert result.has_target_citation is True
    assert result.target_citation_position == 1
    assert result.target_count == 1
    assert result.competitor_count == 1
    assert result.citations[0].is_target_domain is True
    assert result.citations[1].is_competitor_domain is True
    assert result.citations[1].competitor_brand == "WeWork"
    assert result.citations[2].is_target_domain is False
    assert result.citations[2].is_competitor_domain is False
    assert result.citations[2].domain == "wikipedia.org"


def test_target_subdomain_matches(cfg):
    cits = [Citation(url="https://blog.talentgarden.com/articolo", position=1)]
    result = analyze_citations(cits, cfg)
    assert result.has_target_citation is True


def test_dedup_by_normalized_url(cfg):
    cits = [
        Citation(url="https://wework.com/page?utm_source=ad", position=1),
        Citation(url="https://wework.com/page", position=2),  # stessa pagina dopo normalize
        Citation(url="https://wework.com/other", position=3),
    ]
    result = analyze_citations(cits, cfg)
    assert result.total == 2
    # Posizioni rinumerate
    assert [c.position for c in result.citations] == [1, 2]


def test_target_position_is_first_target(cfg):
    cits = [
        Citation(url="https://wework.com/a", position=1),
        Citation(url="https://copernicomilano.it/b", position=2),
        Citation(url="https://talentgarden.com/c", position=3),
        Citation(url="https://talentgarden.com/d", position=4),
    ]
    result = analyze_citations(cits, cfg)
    assert result.target_citation_position == 3


def test_no_target_citations(cfg):
    cits = [
        Citation(url="https://wework.com/a", position=1),
        Citation(url="https://regus.com/b", position=2),
    ]
    result = analyze_citations(cits, cfg)
    assert result.has_target_citation is False
    assert result.target_citation_position is None
    assert result.competitor_count == 2


def test_empty_citations(cfg):
    result = analyze_citations([], cfg)
    assert result.total == 0
    assert result.has_target_citation is False
    assert result.target_citation_position is None


def test_skips_empty_urls(cfg):
    cits = [
        Citation(url="", position=1),
        Citation(url="https://talentgarden.com", position=2),
    ]
    result = analyze_citations(cits, cfg)
    assert result.total == 1
    assert result.has_target_citation is True


def test_loads_real_brand_config():
    """Verifica che brands.yaml reale carichi senza errori."""
    from src.citation_analyzer import load_brand_config
    cfg = load_brand_config()
    assert "talentgarden.com" in cfg.target_domains
    assert "wework.com" in cfg.competitor_domains
    assert cfg.competitor_domains["wework.com"] == "WeWork"
