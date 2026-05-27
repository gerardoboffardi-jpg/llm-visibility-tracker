"""Gemini provider con Google Search grounding (nuova SDK google-genai).

Docs: https://ai.google.dev/gemini-api/docs/grounding
Citazioni in `response.candidates[0].grounding_metadata.grounding_chunks`.

Autenticazione — due modalità:
1. **Vertex AI + ADC** (Application Default Credentials): impostare
   `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`.
   In locale le credenziali arrivano da `gcloud auth application-default login`
   (lo script setup_adc.sh). Su Streamlit Cloud si passa il JSON del service
   account come secret `GCP_SERVICE_ACCOUNT_JSON`: viene scritto su file e
   esposto via `GOOGLE_APPLICATION_CREDENTIALS`.
2. **API key** (fallback): `GOOGLE_API_KEY`.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from google import genai
from google.genai import types

from src.providers.base import Citation, LLMProvider, LLMResponse, ProviderError


def _cfg(key: str, default: str | None = None) -> str | None:
    """Legge una config da env var, con fallback su st.secrets (Streamlit Cloud
    non espone i secrets come env var automaticamente)."""
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st  # type: ignore
        v = st.secrets.get(key)  # type: ignore[attr-defined]
        if v:
            return str(v)
    except Exception:  # noqa: BLE001
        pass
    return default


def _ensure_adc_credentials() -> None:
    """Su Streamlit Cloud non si può fare `gcloud auth`: se è presente il JSON
    del service account (secret/env `GCP_SERVICE_ACCOUNT_JSON`), lo scrive su un
    file temporaneo e imposta GOOGLE_APPLICATION_CREDENTIALS per ADC."""
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return  # già configurato (es. ADC locale)
    sa_json = _cfg("GCP_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        return
    try:
        # valida che sia JSON
        json.loads(sa_json)
        path = Path(tempfile.gettempdir()) / "llmvt_gcp_sa.json"
        path.write_text(sa_json, encoding="utf-8")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path)
    except Exception:  # noqa: BLE001
        pass


def _use_vertex() -> bool:
    return (_cfg("GOOGLE_GENAI_USE_VERTEXAI", "") or "").strip().lower() in ("1", "true", "yes")


class GeminiSearchProvider(LLMProvider):
    provider_name = "gemini"

    def __init__(self, model_id: str, model: str,
                 enable_web_search: bool = True, **kwargs):
        super().__init__(model_id, model, **kwargs)

        if _use_vertex():
            # Vertex AI + ADC
            _ensure_adc_credentials()
            project = _cfg("GOOGLE_CLOUD_PROJECT")
            location = _cfg("GOOGLE_CLOUD_LOCATION", "us-central1")
            if not project:
                raise ProviderError(
                    "Vertex AI abilitato ma GOOGLE_CLOUD_PROJECT non configurato"
                )
            self.client = genai.Client(vertexai=True, project=project, location=location)
        else:
            # Gemini Developer API con API key
            api_key = _cfg("GOOGLE_API_KEY")
            if not api_key:
                raise ProviderError(
                    "Gemini: configura GOOGLE_API_KEY oppure ADC/Vertex "
                    "(GOOGLE_GENAI_USE_VERTEXAI=true + GOOGLE_CLOUD_PROJECT)"
                )
            self.client = genai.Client(api_key=api_key)

        self.enable_web_search = enable_web_search

    def _do_query(self, prompt: str) -> LLMResponse:
        start = time.time()
        try:
            cfg = (
                types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                )
                if self.enable_web_search
                else None
            )
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=cfg,
            )
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"Gemini error: {e}") from e
        latency_ms = int((time.time() - start) * 1000)

        # Estrai testo
        text = ""
        try:
            text = response.text or ""
        except Exception:  # noqa: BLE001
            for cand in (response.candidates or []):
                content = getattr(cand, "content", None)
                if content is None:
                    continue
                for part in (content.parts or []):
                    if hasattr(part, "text") and part.text:
                        text += part.text

        # Estrai citazioni dai grounding_chunks
        citations: list[Citation] = []
        seen_urls: set[str] = set()
        position = 0
        for cand in (response.candidates or []):
            grounding = getattr(cand, "grounding_metadata", None)
            if grounding is None:
                continue
            chunks = getattr(grounding, "grounding_chunks", None) or []
            for ch in chunks:
                web = getattr(ch, "web", None)
                if web is None:
                    continue
                url = getattr(web, "uri", None)
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                position += 1
                citations.append(
                    Citation(
                        url=url,
                        position=position,
                        title=getattr(web, "title", None),
                        snippet=None,
                    )
                )

        # Tokens
        tokens = None
        try:
            usage = response.usage_metadata
            if usage:
                tokens = usage.total_token_count
        except Exception:  # noqa: BLE001
            pass

        raw = {"text": text, "n_citations": len(citations), "model": self.model}

        return LLMResponse(
            model_id=self.model_id,
            text=text,
            citations=citations,
            latency_ms=latency_ms,
            tokens_used=tokens,
            raw_response=raw,
        )
