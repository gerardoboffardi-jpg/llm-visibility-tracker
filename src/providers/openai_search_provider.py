"""OpenAI search provider — gpt-4o-search-preview / gpt-4o-mini-search-preview.

I modelli search-preview eseguono il web search automaticamente. Le citazioni
arrivano in `message.annotations` con type `url_citation`.
"""
from __future__ import annotations

import os
import time

from openai import OpenAI

from src.providers.base import Citation, LLMProvider, LLMResponse, ProviderError


class OpenAISearchProvider(LLMProvider):
    provider_name = "openai"

    def __init__(self, model_id: str, model: str, **kwargs):
        super().__init__(model_id, model, **kwargs)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ProviderError("OPENAI_API_KEY non configurata")
        self.client = OpenAI(api_key=api_key)

    def _do_query(self, prompt: str) -> LLMResponse:
        start = time.time()
        # I search-preview models non supportano tutti i parametri (es. temperature)
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        latency_ms = int((time.time() - start) * 1000)

        msg = completion.choices[0].message
        text = msg.content or ""
        tokens = completion.usage.total_tokens if completion.usage else None

        citations: list[Citation] = []
        annotations = getattr(msg, "annotations", None) or []
        position = 0
        seen_urls: set[str] = set()
        for ann in annotations:
            ann_dict = ann.model_dump() if hasattr(ann, "model_dump") else dict(ann)
            if ann_dict.get("type") != "url_citation":
                continue
            url_cit = ann_dict.get("url_citation") or {}
            url = url_cit.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            position += 1
            citations.append(
                Citation(
                    url=url,
                    position=position,
                    title=url_cit.get("title"),
                    snippet=None,
                )
            )

        return LLMResponse(
            model_id=self.model_id,
            text=text,
            citations=citations,
            latency_ms=latency_ms,
            tokens_used=tokens,
            raw_response=completion.model_dump(),
        )
