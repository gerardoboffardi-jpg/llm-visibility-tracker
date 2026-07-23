"""Perplexity provider — search nativo su sonar / sonar-pro.

API docs: https://docs.perplexity.ai/api-reference/chat-completions
"""
from __future__ import annotations

import os
import time

import requests

from src.providers.base import Citation, LLMProvider, LLMResponse, ProviderError

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


class PerplexityProvider(LLMProvider):
    provider_name = "perplexity"

    def __init__(self, model_id: str, model: str, **kwargs):
        super().__init__(model_id, model, **kwargs)
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ProviderError("PERPLEXITY_API_KEY non configurata")

    def _do_query(self, prompt: str) -> LLMResponse:
        start = time.time()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # NB: le citazioni sono restituite di default (campo `citations` /
        # `search_results`); il vecchio flag `return_citations` è deprecato.
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        r = requests.post(PERPLEXITY_URL, headers=headers, json=payload, timeout=60)
        latency_ms = int((time.time() - start) * 1000)
        if r.status_code != 200:
            raise ProviderError(f"Perplexity {r.status_code}: {r.text[:300]}")
        data = r.json()

        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        tokens = (data.get("usage") or {}).get("total_tokens")

        # Perplexity può restituire citazioni in 2 forme: stringhe semplici (urls)
        # o oggetti con metadata. Gestiamo entrambi.
        citations: list[Citation] = []
        raw_citations = data.get("citations") or data.get("search_results") or []
        for i, c in enumerate(raw_citations, start=1):
            if isinstance(c, str):
                citations.append(Citation(url=c, position=i))
            elif isinstance(c, dict):
                citations.append(
                    Citation(
                        url=c.get("url") or c.get("link") or "",
                        position=i,
                        title=c.get("title"),
                        snippet=c.get("snippet") or c.get("text"),
                    )
                )
        # Filtra eventuali url vuoti
        citations = [c for c in citations if c.url]

        return LLMResponse(
            model_id=self.model_id,
            text=text,
            citations=citations,
            latency_ms=latency_ms,
            tokens_used=tokens,
            raw_response=data,
        )
