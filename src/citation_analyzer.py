"""Citation analyzer.

Normalizza gli URL emessi dai provider e classifica ogni citazione come:
- target_domain   → talentgarden.com (e additional_domains)
- competitor_domain → uno dei domini in competitor_domains
- other           → tutto il resto (utile per scoprire fonti neutre ricorrenti)

Output: lista di `AnalyzedCitation` pronta per essere persistita nella tabella `citations`.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import tldextract
import yaml

from src.providers.base import Citation

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "brands.yaml"

# Tracking params da rimuovere durante la normalizzazione
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "utm_creative_format", "utm_marketing_tactic",
    "fbclid", "gclid", "gclsrc", "dclid", "mc_cid", "mc_eid",
    "yclid", "msclkid", "_ga", "_gl",
    "ref", "ref_src", "ref_url",
    "igshid", "twclid", "li_fat_id",
}


@dataclass(frozen=True)
class BrandConfig:
    target_domains: frozenset[str]            # talentgarden.com + additional
    target_name: str
    competitor_domains: dict[str, str]        # domain -> brand_name


def load_brand_config(path: Path | str | None = None) -> BrandConfig:
    cfg_path = Path(path) if path else CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    target = data.get("target", {}) or {}
    target_domains = {target.get("domain", "").lower()}
    for d in target.get("additional_domains") or []:
        target_domains.add(d.lower())
    target_domains.discard("")

    competitors: dict[str, str] = {}
    for comp in data.get("competitors") or []:
        name = comp.get("name", "")
        for d in comp.get("domains") or []:
            competitors[d.lower()] = name

    return BrandConfig(
        target_domains=frozenset(target_domains),
        target_name=target.get("name", "Target"),
        competitor_domains=competitors,
    )


# ---------------------------------------------------------------------------
# URL normalization & domain extraction
# ---------------------------------------------------------------------------


def normalize_url(url: str) -> str:
    """Normalizza un URL: lowercase scheme/host, rimuove tracking params,
    rimuove trailing slash, rimuove fragment."""
    if not url:
        return url
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return url

    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    # Rimuovi default port
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    # Filtra query params di tracking
    if parsed.query:
        kept = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                if k.lower() not in TRACKING_PARAMS]
        query = urlencode(kept)
    else:
        query = ""

    path = parsed.path or "/"
    # Rimuovi trailing slash tranne quando il path è "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    return urlunparse((scheme, netloc, path, "", query, ""))


def extract_domain(url: str) -> str:
    """Estrae il dominio registrabile (es. 'talentgarden.com' da
    'https://www.talentgarden.com/it/coworking/milano')."""
    if not url:
        return ""
    ext = tldextract.extract(url)
    if not ext.domain or not ext.suffix:
        # senza TLD valido non è un dominio reale
        return ""
    return f"{ext.domain}.{ext.suffix}".lower()


def _domain_matches(domain: str, target_set: Iterable[str]) -> bool:
    """True se `domain` è uno dei target o un sottodominio di uno di essi."""
    domain = domain.lower()
    for t in target_set:
        if domain == t or domain.endswith(f".{t}"):
            return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class AnalyzedCitation:
    position: int
    url: str                # URL normalizzato
    original_url: str       # URL originale (per debug)
    domain: str
    is_target_domain: bool
    is_competitor_domain: bool
    competitor_brand: str | None  # nome del competitor se is_competitor_domain
    page_title: str | None
    snippet: str | None


@dataclass
class CitationAnalysis:
    """Risultato dell'analisi di tutte le citazioni di una risposta."""

    citations: list[AnalyzedCitation]

    @property
    def total(self) -> int:
        return len(self.citations)

    @property
    def has_target_citation(self) -> bool:
        return any(c.is_target_domain for c in self.citations)

    @property
    def target_citation_position(self) -> int | None:
        """Posizione (1-based) della prima citazione target, o None."""
        for c in self.citations:
            if c.is_target_domain:
                return c.position
        return None

    @property
    def target_count(self) -> int:
        return sum(1 for c in self.citations if c.is_target_domain)

    @property
    def competitor_count(self) -> int:
        return sum(1 for c in self.citations if c.is_competitor_domain)


def analyze_citations(
    citations: list[Citation],
    brand_config: BrandConfig | None = None,
) -> CitationAnalysis:
    """Analizza le citazioni grezze emesse da un provider.

    Le citazioni vengono **deduplicate per dominio normalizzato + path**, mantenendo
    la prima occorrenza (così la `position` resta stabile).
    """
    cfg = brand_config or load_brand_config()
    seen_norm: set[str] = set()
    out: list[AnalyzedCitation] = []
    for c in citations:
        if not c.url:
            continue
        norm = normalize_url(c.url)
        if norm in seen_norm:
            continue
        seen_norm.add(norm)
        domain = extract_domain(norm)

        is_target = _domain_matches(domain, cfg.target_domains)
        # Un dominio target NON è anche competitor (anche se per errore comparisse in entrambe le liste)
        is_competitor = (not is_target) and _domain_matches(domain, cfg.competitor_domains.keys())
        competitor_brand: str | None = None
        if is_competitor:
            for cd, name in cfg.competitor_domains.items():
                if domain == cd or domain.endswith(f".{cd}"):
                    competitor_brand = name
                    break

        out.append(
            AnalyzedCitation(
                position=len(out) + 1,  # ri-numera dopo dedup
                url=norm,
                original_url=c.url,
                domain=domain,
                is_target_domain=is_target,
                is_competitor_domain=is_competitor,
                competitor_brand=competitor_brand,
                page_title=c.title,
                snippet=c.snippet,
            )
        )
    return CitationAnalysis(citations=out)
