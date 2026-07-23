"""OpenAI provider — Responses API con tool `web_search`.

Dal 2026 il web search di OpenAI è un TOOL della Responses API (non più un
modello `*-search-preview` dedicato): lo stesso modello (es. gpt-5.6-terra) fa
sia ricerca — con `tools=[{"type": "web_search"}]` — sia chat senza tool.

Le citazioni arrivano come annotation `url_citation` sui content block dell'output.
Docs: https://developers.openai.com/api/docs/guides/tools-web-search
"""
from __future__ import annotations

import os
import time

from openai import OpenAI

from src.providers.base import Citation, LLMProvider, LLMResponse, ProviderError


class OpenAISearchProvider(LLMProvider):
    provider_name = "openai"

    def __init__(self, model_id: str, model: str,
                 enable_web_search: bool = True, **kwargs):
        super().__init__(model_id, model, **kwargs)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ProviderError("OPENAI_API_KEY non configurata")
        self.client = OpenAI(api_key=api_key)
        self.enable_web_search = enable_web_search

    def _do_query(self, prompt: str) -> LLMResponse:
        start = time.time()
        kwargs: dict = {"model": self.model, "input": prompt}
        if self.enable_web_search:
            kwargs["tools"] = [{"type": "web_search"}]
        response = self.client.responses.create(**kwargs)
        latency_ms = int((time.time() - start) * 1000)

        # `output_text` concatena i blocchi testuali dell'output
        text = getattr(response, "output_text", "") or ""

        usage = getattr(response, "usage", None)
        tokens = getattr(usage, "total_tokens", None) if usage else None

        # Citazioni: annotation `url_citation` sui content block dell'output
        citations: list[Citation] = []
        seen_urls: set[str] = set()
        position = 0
        for item in (getattr(response, "output", None) or []):
            for block in (getattr(item, "content", None) or []):
                for ann in (getattr(block, "annotations", None) or []):
                    ann_d = ann.model_dump() if hasattr(ann, "model_dump") else dict(ann)
                    if ann_d.get("type") != "url_citation":
                        continue
                    url = ann_d.get("url")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    position += 1
                    citations.append(
                        Citation(
                            url=url,
                            position=position,
                            title=ann_d.get("title"),
                            snippet=None,
                        )
                    )

        return LLMResponse(
            model_id=self.model_id,
            text=text,
            citations=citations,
            latency_ms=latency_ms,
            tokens_used=tokens,
            raw_response=response.model_dump(),
        )
