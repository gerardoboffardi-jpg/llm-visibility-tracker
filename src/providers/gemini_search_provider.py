"""Gemini provider con Google Search grounding (nuova SDK google-genai).

Docs: https://ai.google.dev/gemini-api/docs/grounding
Citazioni in `response.candidates[0].grounding_metadata.grounding_chunks`.
"""
from __future__ import annotations

import os
import time

from google import genai
from google.genai import types

from src.providers.base import Citation, LLMProvider, LLMResponse, ProviderError


class GeminiSearchProvider(LLMProvider):
    provider_name = "gemini"

    def __init__(self, model_id: str, model: str,
                 enable_web_search: bool = True, **kwargs):
        super().__init__(model_id, model, **kwargs)
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ProviderError("GOOGLE_API_KEY non configurata")
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
