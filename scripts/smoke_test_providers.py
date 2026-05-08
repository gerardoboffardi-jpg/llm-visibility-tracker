"""Smoke test rapido su tutti i provider abilitati.

Uso:
    python -m scripts.smoke_test_providers
    python -m scripts.smoke_test_providers --prompt "Testo custom"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=True)

from src.providers import build_all_enabled  # noqa: E402

DEFAULT_PROMPT = "Quali sono i migliori spazi di coworking a Milano? Cita le fonti."


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = parser.parse_args()

    providers = build_all_enabled()
    if not providers:
        print("⚠ Nessun provider disponibile (controlla le API key in .env e models.yaml)")
        return

    print(f"Prompt: {args.prompt}\n")
    print(f"Provider attivi: {[p.model_id for p in providers]}\n")

    for p in providers:
        print(f"━━━━━ {p.model_id} ━━━━━")
        resp = p.query(args.prompt)
        if resp.error:
            print(f"  ✗ ERROR: {resp.error}")
            continue
        print(f"  latency: {resp.latency_ms} ms | tokens: {resp.tokens_used}")
        print(f"  testo (primi 200 char): {resp.text[:200].strip()}…")
        print(f"  citazioni: {len(resp.citations)}")
        for c in resp.citations[:5]:
            print(f"    [{c.position}] {c.url}  — {c.title or ''}")
        if len(resp.citations) > 5:
            print(f"    ... e altre {len(resp.citations) - 5}")
        print()


if __name__ == "__main__":
    main()
