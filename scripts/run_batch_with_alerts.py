"""Esegue un batch e invia eventuali alert su Slack.

Uso (locale o GitHub Actions):
    python -m scripts.run_batch_with_alerts --repeat 3
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=True)

from src.alerting import detect_alerts, send_to_slack  # noqa: E402
from src.runner import run_batch  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--drop-threshold", type=float,
                        default=float(os.getenv("ALERT_DROP_THRESHOLD", "0.10")))
    parser.add_argument("--baseline-runs", type=int,
                        default=int(os.getenv("ALERT_BASELINE_RUNS", "3")))
    parser.add_argument("--skip-alerts", action="store_true",
                        help="Esegui solo il batch, salta la fase di alerting")
    args = parser.parse_args()

    print("→ Avvio batch su tutti i prompt attivi…")
    stats = run_batch(repeat=args.repeat, max_workers=args.max_workers)
    print(f"\n✓ Run #{stats.run_id}: {stats.n_success}/{stats.n_attempted} OK, "
          f"{stats.n_errors} errori in {stats.elapsed_s:.1f}s")

    if args.skip_alerts:
        return

    print("\n→ Calcolo alert…")
    report = detect_alerts(
        stats.run_id,
        drop_threshold=args.drop_threshold,
        baseline_runs=args.baseline_runs,
    )
    if not report.alerts:
        print("  Nessun alert.")
        return

    for a in report.alerts:
        print(f"  [{a.severity.upper()}] {a.title} — {a.message}")

    if send_to_slack(report):
        print("✓ Notifica Slack inviata")
    else:
        print("⊘ Notifica Slack non inviata (webhook non configurato o errore)")


if __name__ == "__main__":
    main()
