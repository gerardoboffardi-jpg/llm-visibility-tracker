"""Anthropic provider — Claude Sonnet con tool web_search_20250305.

Docs: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/web-search-tool
Le citazioni arrivano come oggetti `citation` annidati nei content blocks `text`,
e i risultati di ricerca come blocchi `web_search_tool_result`.

NB: su Claude Sonnet 5 il thinking adattivo è attivo di default; qui lo
disabilitiamo (`thinking: disabled`) perché al tracker interessa la risposta
groundata con le citazioni, non il ragionamento — e con thinking on l'output
utile verrebbe eroso dal budget `max_tokens`.
"""
from __future__ import annotations

import os
import time

import anthropic

from src.providers.base import Citation, LLMProvider, LLMResponse, ProviderError


class AnthropicSearchProvider(LLMProvider):
    provider_name = "anthropic"

    def __init__(self, model_id: str, model: str, max_uses: int = 5,
                 enable_web_search: bool = True, **kwargs):
        super().__init__(model_id, model, **kwargs)
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ProviderError("ANTHROPIC_API_KEY non configurata")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.max_uses = max_uses
        self.enable_web_search = enable_web_search

    def _do_query(self, prompt: str) -> LLMResponse:
        start = time.time()
        kwargs: dict = {
            "model": self.model,
            "max_tokens": 2048,
            "thinking": {"type": "disabled"},
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.enable_web_search:
            kwargs["tools"] = [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": self.max_uses,
                }
            ]
        message = self.client.messages.create(**kwargs)
        latency_ms = int((time.time() - start) * 1000)

        # Concatena tutto il testo dai blocchi `text` e raccoglie le citation
        text_parts: list[str] = []
        citations: list[Citation] = []
        seen_urls: set[str] = set()
        position = 0

        for block in message.content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(getattr(block, "text", ""))
                # Le citazioni inline sui blocchi text
                inline_cits = getattr(block, "citations", None) or []
                for c in inline_cits:
                    c_dict = c.model_dump() if hasattr(c, "model_dump") else dict(c)
                    url = c_dict.get("url")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    position += 1
                    citations.append(
                        Citation(
                            url=url,
                            position=position,
                            title=c_dict.get("title"),
                            snippet=c_dict.get("cited_text"),
                        )
                    )
            elif block_type == "web_search_tool_result":
                # I risultati raw del tool — utili come fallback se l'inline manca
                content = getattr(block, "content", []) or []
                for r in content:
                    r_dict = r.model_dump() if hasattr(r, "model_dump") else dict(r)
                    if r_dict.get("type") != "web_search_result":
                        continue
                    url = r_dict.get("url")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    position += 1
                    citations.append(
                        Citation(
                            url=url,
                            position=position,
                            title=r_dict.get("title"),
                            snippet=None,
                        )
                    )

        text = "".join(text_parts)
        usage = message.usage
        tokens = (usage.input_tokens + usage.output_tokens) if usage else None

        return LLMResponse(
            model_id=self.model_id,
            text=text,
            citations=citations,
            latency_ms=latency_ms,
            tokens_used=tokens,
            raw_response=message.model_dump(),
        )
