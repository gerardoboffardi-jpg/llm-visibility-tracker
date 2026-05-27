"""Cost tracking per le chiamate LLM.

Calcola una stima del costo USD di ogni Response basata sui token (campo `tokens`
di `Response`) e sul pricing per modello definito in `config/models.yaml`.

Visto che `Response.tokens` è il totale (input + output), usiamo un'euristica
70/30 (input/output) per applicare il prezzo medio. È una stima — se hai i conteggi
split, modifica `estimate_cost`.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "models.yaml"

# Euristica split input/output sul totale `tokens`. Le risposte LLM
# tipicamente hanno più input (prompt + context + web search results) che output.
INPUT_RATIO = 0.70
OUTPUT_RATIO = 0.30


@dataclass(frozen=True)
class ModelPricing:
    model_id: str  # id locale (es. "claude-sonnet-search")
    provider: str
    model: str  # id provider (es. "claude-sonnet-4-5")
    input_price_per_1m: float
    output_price_per_1m: float
    web_search_price: float  # USD per query


@lru_cache(maxsize=1)
def load_model_pricing() -> dict[str, ModelPricing]:
    """Legge config/models.yaml e ritorna una mappa model_id → ModelPricing.

    Cached: per ricaricare dopo modifiche al file, chiamare `load_model_pricing.cache_clear()`.
    """
    out: dict[str, ModelPricing] = {}
    if not CONFIG_PATH.exists():
        return out
    with CONFIG_PATH.open() as f:
        rows = yaml.safe_load(f) or []
    for row in rows:
        out[row["id"]] = ModelPricing(
            model_id=row["id"],
            provider=row.get("provider", ""),
            model=row.get("model", ""),
            input_price_per_1m=float(row.get("input_price_per_1m") or 0.0),
            output_price_per_1m=float(row.get("output_price_per_1m") or 0.0),
            web_search_price=float(row.get("web_search_price") or 0.0),
        )
    return out


def estimate_cost(
    model_id: str,
    tokens: int | None,
    *,
    has_web_search: bool = True,
    n_web_queries: int = 1,
    pricing: dict[str, ModelPricing] | None = None,
) -> float:
    """Stima il costo USD di una risposta.

    Args:
        model_id: id locale (es. "claude-sonnet-search").
        tokens: totale token (input + output). Se None o 0, ritorna solo costo web search.
        has_web_search: se la chiamata ha usato web search.
        n_web_queries: numero di query web (default 1).
        pricing: mappa pricing custom (per testing); default carica da YAML.

    Returns:
        Costo stimato in USD (può essere 0 se mancano prezzi e tokens).
    """
    pr = pricing if pricing is not None else load_model_pricing()
    p = pr.get(model_id)
    if p is None:
        return 0.0
    tokens = tokens or 0
    input_tok = tokens * INPUT_RATIO
    output_tok = tokens * OUTPUT_RATIO
    cost = (
        input_tok * p.input_price_per_1m / 1_000_000
        + output_tok * p.output_price_per_1m / 1_000_000
    )
    if has_web_search:
        cost += p.web_search_price * n_web_queries
    return round(cost, 6)
