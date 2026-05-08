"""Esegue un singolo prompt su tutti i modelli abilitati (o un subset).

Uso:
    python -m scripts.run_single_prompt --prompt-id 5
    python -m scripts.run_single_prompt --prompt-id 5 --models perplexity-sonar gpt-4o-search
    python -m scripts.run_single_prompt --prompt-id 5 --repeat 3
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

from src.runner import run_single  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-id", type=int, required=True)
    parser.add_argument("--models", nargs="*", default=None,
                        help="Lista di model_id; se omesso, tutti gli enabled")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--sentiment", action="store_true",
                        help="Classifica sentiment/contesto delle menzioni via Claude Haiku")
    args = parser.parse_args()

    stats = run_single(
        args.prompt_id,
        model_ids=args.models,
        repeat=args.repeat,
        trigger_type="manual",
        do_sentiment=args.sentiment,
    )
    print(f"\nRun #{stats.run_id}: {stats.n_success}/{stats.n_attempted} OK, "
          f"{stats.n_errors} errori in {stats.elapsed_s:.1f}s")


if __name__ == "__main__":
    main()
