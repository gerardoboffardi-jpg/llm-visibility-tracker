"""Base classes per tutti i provider LLM con web search."""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """Una citazione URL emessa da un LLM con web search.

    Schema normalizzato comune a tutti i provider.
    """

    url: str
    position: int  # 1-based: ordine in cui appare nella risposta
    title: str | None = None
    snippet: str | None = None


@dataclass
class LLMResponse:
    """Risposta normalizzata da un provider."""

    model_id: str
    text: str
    citations: list[Citation] = field(default_factory=list)
    latency_ms: int = 0
    tokens_used: int | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def is_success(self) -> bool:
        return self.error is None


class ProviderError(Exception):
    pass


class LLMProvider(ABC):
    """Interfaccia base per ogni provider."""

    provider_name: str = "base"

    def __init__(self, model_id: str, model: str, **kwargs):
        self.model_id = model_id  # id logico es. "perplexity-sonar"
        self.model = model        # nome reale del modello passato all'API
        self.config = kwargs

    @abstractmethod
    def _do_query(self, prompt: str) -> LLMResponse:
        """Implementazione concreta della query. Da sovrascrivere."""

    def query(self, prompt: str, max_retries: int = 3, retry_backoff: float = 2.0) -> LLMResponse:
        """Esegue la query con retry exponential backoff."""
        start = time.time()
        last_err: Exception | None = None
        for attempt in range(max_retries):
            try:
                resp = self._do_query(prompt)
                if resp.latency_ms == 0:
                    resp.latency_ms = int((time.time() - start) * 1000)
                return resp
            except Exception as e:  # noqa: BLE001
                last_err = e
                wait = retry_backoff ** attempt
                logger.warning(
                    "Provider %s query failed (attempt %d/%d): %s — retry in %.1fs",
                    self.model_id, attempt + 1, max_retries, e, wait,
                )
                time.sleep(wait)
        # Tutti i retry falliti
        logger.error("Provider %s definitively failed: %s", self.model_id, last_err)
        return LLMResponse(
            model_id=self.model_id,
            text="",
            citations=[],
            latency_ms=int((time.time() - start) * 1000),
            error=str(last_err),
        )
