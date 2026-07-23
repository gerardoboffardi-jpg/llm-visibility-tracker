"""Prompt generator da URL o brochure PDF.

Estrae il testo dalla sorgente (URL HTML o file PDF), poi chiede a un LLM
(Claude di default) di generare 15-30 prompt rilevanti per tracking visibility.

Esempio d'uso:
    >>> from src.prompt_generator import generate_from_url
    >>> result = generate_from_url("https://talentgarden.com/it/coworking-milano")
    >>> for p in result.prompts:
    ...     print(p.text, p.category, p.geo, p.intent)

Le funzioni NON salvano sul DB: ritornano una struttura serializzabile da mostrare
in UI per review/checkbox, poi importare con `prompt_service.create_prompt` o
`bulk_import` come fa già il bottone "Import YAML/CSV".
"""
from __future__ import annotations

import io
import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Literal

import requests


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GeneratedPrompt:
    """Un prompt suggerito dall'LLM, non ancora salvato."""

    text: str
    category: str | None = None
    geo: str | None = None
    intent: str | None = None
    notes: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class GenerationResult:
    """Risultato della generazione: prompt suggeriti + meta sulla sorgente."""

    source_type: Literal["url", "pdf"]
    source_label: str  # URL o filename
    source_text_chars: int  # quante char di testo abbiamo estratto
    prompts: list[GeneratedPrompt]
    model_used: str
    raw_response: str | None = None  # debug


# ---------------------------------------------------------------------------
# Source extraction
# ---------------------------------------------------------------------------


MAX_INPUT_CHARS = 40_000  # ~10k token, dentro context window Sonnet/Opus
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_text_from_url(url: str, timeout: int = 20) -> str:
    """Scarica un URL HTML e ritorna il testo principale (rimuove script/nav/footer).

    Best-effort: usa BeautifulSoup, cerca <main> / <article> se presenti.
    """
    from bs4 import BeautifulSoup

    resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Rimuovi rumore tipico
    for tag in soup(["script", "style", "noscript", "iframe", "nav", "footer", "header", "form"]):
        tag.decompose()

    # Preferisci <main> o <article> se presenti
    root = soup.find("main") or soup.find("article") or soup.body or soup

    text = root.get_text("\n", strip=True)
    # Comprimi righe vuote multiple
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:MAX_INPUT_CHARS]


def fetch_text_from_pdf(file_bytes: bytes) -> str:
    """Estrae testo da un PDF (bytes già letti)."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            continue
    text = "\n\n".join(parts).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:MAX_INPUT_CHARS]


# ---------------------------------------------------------------------------
# LLM prompt generation
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = """Sei un SEO/AEO strategist esperto. Il tuo compito è generare \
una lista di prompt realistici che utenti italiani potrebbero porre a ChatGPT, \
Perplexity, Claude o Gemini per scoprire prodotti/servizi/aziende del settore \
descritto nel testo che ti viene fornito.

Ogni prompt deve essere:
- in **italiano**
- realistico: come lo scriverebbe davvero un utente (non un keyword secco)
- coprire intenti diversi: discovery, comparison, pricing, location-based, problem-solving
- variegato: mix di prompt brand-aware ("migliori coworking a Milano"), \
problem-aware ("come scegliere un corso di AI"), e prompt comparativi.

NON inserire mai il nome del brand target dentro al prompt — devono essere prompt \
che un utente fa SENZA conoscere ancora il brand.

Ritorna ESCLUSIVAMENTE un JSON valido con questa struttura:
{
  "brand_detected": "Talent Garden",
  "topics_detected": ["coworking Milano", "corsi AI", ...],
  "prompts": [
    {
      "text": "Migliori coworking a Milano per startup",
      "category": "coworking",
      "geo": "Milano",
      "intent": "discovery"
    },
    ...
  ]
}

Genera 20-30 prompt. Niente testo prima o dopo il JSON."""


_USER_TEMPLATE = """Ecco il contenuto estratto dalla sorgente ({source_type}):

---SORGENTE---
{label}
---FINE SORGENTE---

---TESTO ESTRATTO ({n_chars} caratteri)---
{text}
---FINE TESTO---

Genera una lista di 20-30 prompt rilevanti come JSON."""


def _extract_json(raw: str) -> dict:
    """Estrae il primo blob JSON da una risposta che potrebbe avere ```json ... ```."""
    raw = raw.strip()
    # rimuovi fence ```json ... ``` se presenti
    fence = re.match(r"```(?:json)?\s*(.+?)\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    # cerca primo "{" fino all'ultimo "}"
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Nessun JSON trovato nella risposta LLM")
    return json.loads(raw[start : end + 1])


def generate_prompts_with_claude(
    text: str,
    *,
    source_type: Literal["url", "pdf"],
    source_label: str,
    model: str = "claude-sonnet-5",
) -> tuple[list[GeneratedPrompt], str]:
    """Chiama Anthropic Claude e ritorna (lista prompt, raw response)."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY non impostato. Configura `.env` o i secret CI."
        )

    import anthropic

    client = anthropic.Anthropic()
    user_msg = _USER_TEMPLATE.format(
        source_type=source_type,
        label=source_label,
        n_chars=len(text),
        text=text,
    )

    resp = client.messages.create(
        model=model,
        max_tokens=4000,
        thinking={"type": "disabled"},  # Sonnet 5: niente thinking, serve solo il JSON dei prompt
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = "".join(b.text for b in resp.content if hasattr(b, "text"))
    data = _extract_json(raw)
    out: list[GeneratedPrompt] = []
    for item in data.get("prompts", []):
        if not isinstance(item, dict) or not item.get("text"):
            continue
        out.append(
            GeneratedPrompt(
                text=str(item["text"]).strip(),
                category=item.get("category"),
                geo=item.get("geo"),
                intent=item.get("intent"),
            )
        )
    return out, raw


def generate_prompts_with_openai(
    text: str,
    *,
    source_type: Literal["url", "pdf"],
    source_label: str,
    model: str = "gpt-4o-mini",
) -> tuple[list[GeneratedPrompt], str]:
    """Fallback: usa OpenAI (più economico) se ANTHROPIC non è disponibile."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY non impostato. Configura `.env` o i secret CI."
        )
    import openai

    client = openai.OpenAI()
    user_msg = _USER_TEMPLATE.format(
        source_type=source_type,
        label=source_label,
        n_chars=len(text),
        text=text,
    )
    resp = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = resp.choices[0].message.content or "{}"
    data = _extract_json(raw)
    out: list[GeneratedPrompt] = []
    for item in data.get("prompts", []):
        if not isinstance(item, dict) or not item.get("text"):
            continue
        out.append(
            GeneratedPrompt(
                text=str(item["text"]).strip(),
                category=item.get("category"),
                geo=item.get("geo"),
                intent=item.get("intent"),
            )
        )
    return out, raw


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_from_url(
    url: str,
    *,
    provider: Literal["claude", "openai", "auto"] = "auto",
) -> GenerationResult:
    """Estrae testo dall'URL e genera prompt. provider='auto' prova Claude poi OpenAI."""
    text = fetch_text_from_url(url)
    if not text or len(text) < 100:
        raise ValueError(
            f"Estratto solo {len(text)} caratteri dall'URL — sorgente troppo povera per generare prompt."
        )
    return _run(text, source_type="url", source_label=url, provider=provider)


def generate_from_pdf(
    file_bytes: bytes,
    filename: str,
    *,
    provider: Literal["claude", "openai", "auto"] = "auto",
) -> GenerationResult:
    """Estrae testo dal PDF (bytes) e genera prompt."""
    text = fetch_text_from_pdf(file_bytes)
    if not text or len(text) < 100:
        raise ValueError(
            f"Estratto solo {len(text)} caratteri dal PDF — il file potrebbe essere "
            f"un'immagine scansionata (serve OCR, non supportato qui)."
        )
    return _run(text, source_type="pdf", source_label=filename, provider=provider)


def _run(
    text: str,
    *,
    source_type: Literal["url", "pdf"],
    source_label: str,
    provider: Literal["claude", "openai", "auto"],
) -> GenerationResult:
    last_err: Exception | None = None
    tried: list[str] = []

    order: list[str]
    if provider == "claude":
        order = ["claude"]
    elif provider == "openai":
        order = ["openai"]
    else:
        order = ["claude", "openai"]

    for p in order:
        tried.append(p)
        try:
            if p == "claude":
                prompts, raw = generate_prompts_with_claude(
                    text, source_type=source_type, source_label=source_label,
                )
                model = "claude-sonnet-5"
            else:
                prompts, raw = generate_prompts_with_openai(
                    text, source_type=source_type, source_label=source_label,
                )
                model = "gpt-4o-mini"
            return GenerationResult(
                source_type=source_type,
                source_label=source_label,
                source_text_chars=len(text),
                prompts=prompts,
                model_used=model,
                raw_response=raw,
            )
        except Exception as e:  # noqa: BLE001
            last_err = e

    raise RuntimeError(
        f"Generazione fallita con provider {tried}: {last_err}"
    )
