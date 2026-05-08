"""Factory per istanziare i provider da config/models.yaml."""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from src.providers.base import LLMProvider, ProviderError

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "models.yaml"


def _load_models_config() -> list[dict]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def build_provider(model_cfg: dict) -> LLMProvider:
    """Costruisce un provider dato la sua entry in models.yaml."""
    provider = model_cfg["provider"]
    model_id = model_cfg["id"]
    model = model_cfg["model"]

    if provider == "perplexity":
        from src.providers.perplexity_provider import PerplexityProvider
        return PerplexityProvider(model_id=model_id, model=model)
    if provider == "openai":
        from src.providers.openai_search_provider import OpenAISearchProvider
        return OpenAISearchProvider(model_id=model_id, model=model)
    if provider == "anthropic":
        from src.providers.anthropic_search_provider import AnthropicSearchProvider
        return AnthropicSearchProvider(model_id=model_id, model=model)
    if provider == "gemini":
        from src.providers.gemini_search_provider import GeminiSearchProvider
        return GeminiSearchProvider(model_id=model_id, model=model)

    raise ProviderError(f"Provider sconosciuto: {provider}")


def build_all_enabled() -> list[LLMProvider]:
    """Costruisce tutti i provider enabled in models.yaml. Salta quelli che
    falliscono inizializzazione (es. API key mancante) loggando un warning."""
    providers: list[LLMProvider] = []
    for cfg in _load_models_config():
        if not cfg.get("enabled", True):
            continue
        try:
            providers.append(build_provider(cfg))
        except Exception as e:  # noqa: BLE001
            logger.warning("Skipping %s: %s", cfg.get("id"), e)
    return providers
