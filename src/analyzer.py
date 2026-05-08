"""Mention analyzer.

Rileva menzioni di brand (target + competitor) nel testo di una risposta LLM.
Per ogni menzione produce:
- nome del brand, is_target
- posizione carattere nel testo
- snippet di contesto (~200 char)
- posizione in lista (se la menzione appare in una lista numerata/puntata)
- sentiment + context_label (opzionali, via Claude Haiku con cache)

Strategia:
- match case-sensitive sul brand name esatto e sugli alias (per evitare falsi positivi
  su "talent garden" generico in contesti diversi). Su alias palesemente case-insensitive
  (es. ["TAG"]) si applica match esatto su parola intera.
- whole-word matching (regex \\b) per evitare match parziali (es. "WeWorker")
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "brands.yaml"
SENTIMENT_CACHE_PATH = Path(__file__).resolve().parent.parent / ".sentiment_cache.json"
SENTIMENT_MODEL = "claude-haiku-4-5"  # economico
CONTEXT_CHARS = 120  # caratteri prima/dopo per lo snippet


# ---------------------------------------------------------------------------
# Brand index
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BrandEntry:
    name: str
    aliases: tuple[str, ...]
    is_target: bool


@dataclass(frozen=True)
class BrandIndex:
    brands: tuple[BrandEntry, ...]


def load_brand_index(path: Path | str | None = None) -> BrandIndex:
    cfg_path = Path(path) if path else CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    entries: list[BrandEntry] = []
    target = data.get("target") or {}
    if target.get("name"):
        all_aliases = {target["name"]} | set(target.get("aliases") or [])
        entries.append(BrandEntry(
            name=target["name"],
            aliases=tuple(sorted(all_aliases, key=len, reverse=True)),
            is_target=True,
        ))
    for comp in data.get("competitors") or []:
        if not comp.get("name"):
            continue
        all_aliases = {comp["name"]} | set(comp.get("aliases") or [])
        entries.append(BrandEntry(
            name=comp["name"],
            aliases=tuple(sorted(all_aliases, key=len, reverse=True)),
            is_target=False,
        ))
    return BrandIndex(brands=tuple(entries))


# ---------------------------------------------------------------------------
# Mention detection
# ---------------------------------------------------------------------------


@dataclass
class DetectedMention:
    brand_name: str
    is_target: bool
    matched_alias: str
    position_in_text: int
    context_snippet: str
    list_position: int | None = None  # se la menzione è in una lista (1-based)
    sentiment: str | None = None       # popolato in fase di sentiment
    context_label: str | None = None


def _build_alias_pattern(alias: str) -> re.Pattern:
    """Whole-word, case-sensitive sul brand name; case-insensitive solo per alias
    palesemente uppercase-acronym (es. 'TAG' → match solo se appare uppercase)."""
    escaped = re.escape(alias)
    return re.compile(rf"(?<!\w){escaped}(?!\w)")


def _list_position_for(text: str, char_pos: int) -> int | None:
    """Se la menzione è all'interno di una riga che è elemento di una lista
    (numerata o puntata), ritorna la sua posizione 1-based all'interno della lista
    contigua. Altrimenti None.
    """
    lines = text.split("\n")
    # individua la riga
    cum = 0
    line_idx = 0
    for i, ln in enumerate(lines):
        if char_pos < cum + len(ln) + 1:
            line_idx = i
            break
        cum += len(ln) + 1
    else:
        return None

    list_pat = re.compile(r"^\s*(?:\d+[\.\)]|[-*•])\s+")
    if not list_pat.match(lines[line_idx]):
        return None

    # cammina indietro fino a trovare l'inizio della lista contigua
    start = line_idx
    while start > 0 and (list_pat.match(lines[start - 1]) or not lines[start - 1].strip()):
        start -= 1
    # conta gli elementi lista da start a line_idx (inclusi solo righe lista)
    count = 0
    for i in range(start, line_idx + 1):
        if list_pat.match(lines[i]):
            count += 1
    return count or None


def detect_mentions(text: str, brand_index: BrandIndex | None = None) -> list[DetectedMention]:
    """Trova tutte le menzioni nei brand. Ogni alias produce al massimo 1 menzione
    per ogni occorrenza nel testo. Per evitare duplicati (es. brand name + alias
    sulla stessa posizione) prendiamo solo il primo match per posizione."""
    if not text:
        return []
    idx = brand_index or load_brand_index()
    seen_positions: set[tuple[int, str]] = set()  # (start, brand_name)
    out: list[DetectedMention] = []

    for brand in idx.brands:
        for alias in brand.aliases:
            pat = _build_alias_pattern(alias)
            for m in pat.finditer(text):
                key = (m.start(), brand.name)
                if key in seen_positions:
                    continue
                seen_positions.add(key)
                start = max(0, m.start() - CONTEXT_CHARS)
                end = min(len(text), m.end() + CONTEXT_CHARS)
                snippet = text[start:end].replace("\n", " ").strip()
                out.append(
                    DetectedMention(
                        brand_name=brand.name,
                        is_target=brand.is_target,
                        matched_alias=alias,
                        position_in_text=m.start(),
                        context_snippet=snippet,
                        list_position=_list_position_for(text, m.start()),
                    )
                )
    out.sort(key=lambda m: m.position_in_text)
    return out


# ---------------------------------------------------------------------------
# Sentiment / context classification (opzionale, con cache)
# ---------------------------------------------------------------------------


def _load_sentiment_cache() -> dict[str, dict]:
    if not SENTIMENT_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(SENTIMENT_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_sentiment_cache(cache: dict[str, dict]) -> None:
    try:
        SENTIMENT_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _cache_key(brand_name: str, snippet: str) -> str:
    # normalizza spazi
    snippet_norm = re.sub(r"\s+", " ", snippet).strip().lower()
    return f"{brand_name}::{snippet_norm[:500]}"


SENTIMENT_PROMPT = """Analizza in che modo il seguente testo parla del brand "{brand}".

Testo:
\"\"\"{snippet}\"\"\"

Rispondi SOLO con JSON valido in questo formato:
{{"sentiment": "positive|neutral|negative", "context": "<una di: recommendation, listing, comparison, factual, criticism, mention>"}}

- "positive" = raccomandato, lodato, prima scelta
- "neutral" = elencato senza giudizio, citato in modo informativo
- "negative" = criticato, sconsigliato
- "recommendation" = consigliato esplicitamente
- "listing" = nominato in lista insieme ad altri
- "comparison" = confrontato con altri brand
- "factual" = informazione fattuale (es. dove ha sede)
- "criticism" = critica
- "mention" = menzione generica"""


def classify_sentiment(
    mentions: Iterable[DetectedMention],
    *,
    use_cache: bool = True,
    enabled: bool | None = None,
) -> None:
    """Popola in-place `sentiment` e `context_label` per ogni menzione.

    Se `enabled` è None, è attivo solo se ANTHROPIC_API_KEY è presente.
    Errori di chiamata API non bloccano: si lascia il campo a None.
    """
    if enabled is None:
        enabled = bool(os.getenv("ANTHROPIC_API_KEY"))
    if not enabled:
        return

    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic SDK non installato — skip sentiment")
        return

    client = anthropic.Anthropic()
    cache = _load_sentiment_cache() if use_cache else {}
    cache_dirty = False

    for m in mentions:
        key = _cache_key(m.brand_name, m.context_snippet)
        if key in cache:
            m.sentiment = cache[key].get("sentiment")
            m.context_label = cache[key].get("context")
            continue

        try:
            resp = client.messages.create(
                model=SENTIMENT_MODEL,
                max_tokens=80,
                messages=[{
                    "role": "user",
                    "content": SENTIMENT_PROMPT.format(brand=m.brand_name, snippet=m.context_snippet),
                }],
            )
            raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            # Estrai JSON anche se ci sono caratteri attorno
            mt = re.search(r"\{.*\}", raw, re.DOTALL)
            if mt:
                parsed = json.loads(mt.group(0))
                m.sentiment = parsed.get("sentiment")
                m.context_label = parsed.get("context")
                cache[key] = {"sentiment": m.sentiment, "context": m.context_label}
                cache_dirty = True
        except Exception as e:  # noqa: BLE001
            logger.warning("Sentiment classification fallita per %s: %s", m.brand_name, e)

    if cache_dirty and use_cache:
        _save_sentiment_cache(cache)


# ---------------------------------------------------------------------------
# Public API: full analysis
# ---------------------------------------------------------------------------


@dataclass
class MentionAnalysis:
    mentions: list[DetectedMention] = field(default_factory=list)

    @property
    def has_target_mention(self) -> bool:
        return any(m.is_target for m in self.mentions)

    @property
    def target_position_in_list(self) -> int | None:
        """Posizione in lista della prima menzione target che appare in una lista."""
        for m in self.mentions:
            if m.is_target and m.list_position is not None:
                return m.list_position
        return None


def analyze_text(
    text: str,
    *,
    brand_index: BrandIndex | None = None,
    do_sentiment: bool = False,
) -> MentionAnalysis:
    mentions = detect_mentions(text, brand_index)
    if do_sentiment and mentions:
        classify_sentiment(mentions)
    return MentionAnalysis(mentions=mentions)
