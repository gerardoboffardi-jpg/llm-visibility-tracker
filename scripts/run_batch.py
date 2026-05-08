"""Esegue il batch su tutti i prompt attivi (o un subset).

Uso:
    python -m scripts.run_batch
    python -m scripts.run_batch --repeat 3
    python -m scripts.run_batch --prompt-ids 1 2 3 --models perplexity-sonar
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=True)

from src.runner import run_batch  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-ids", nargs="*", type=int, default=None)
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--sentiment", action="store_true")
    args = parser.parse_args()

    stats = run_batch(
        prompt_ids=args.prompt_ids,
        model_ids=args.models,
        repeat=args.repeat,
        max_workers=args.max_workers,
        do_sentiment=args.sentiment,
    )
    print(f"\nRun #{stats.run_id}: {stats.n_success}/{stats.n_attempted} OK, "
          f"{stats.n_errors} errori in {stats.elapsed_s:.1f}s")


if __name__ == "__main__":
    main()
