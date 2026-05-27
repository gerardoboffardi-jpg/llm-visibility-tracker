"""Dispatcher per GitHub Actions: esegue un'azione del tracker leggendo il
payload da env `PAYLOAD` (JSON). Riusa la logica Python esistente — niente server.

Azioni supportate (campo "action"):
- "run" / "run-single": esegue run_single per ogni prompt_id (repeat ripetizioni)
- "run-batch": esegue run_batch (prompt_ids opzionale; None = tutti gli attivi)
- "delete": elimina i prompt_ids (+ risposte/citazioni/menzioni)
- "create": crea un prompt (text + category/geo/intent)
- "generate": genera prompt da URL e li crea direttamente (salta i duplicati)

Le chiavi LLM e DATABASE_URL arrivano dalle env (GitHub Actions secrets).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _parse_ids(v):
    if v is None or v == "":
        return None
    if isinstance(v, list):
        return [int(x) for x in v]
    return [int(x) for x in str(v).replace(" ", "").split(",") if x.strip()]


def main() -> None:
    payload = json.loads(os.environ.get("PAYLOAD", "{}") or "{}")
    action = (payload.get("action") or "run-batch").strip()
    repeat = int(payload.get("repeat") or 1)
    ids = _parse_ids(payload.get("prompt_ids"))
    print(f"→ azione: {action} | prompt_ids={ids} | repeat={repeat}")

    from src import prompt_service as ps
    from src.runner import run_batch, run_single

    if action in ("run", "run-single"):
        for pid in (ids or []):
            stats = run_single(pid, repeat=repeat, trigger_type="api")
            print(f"  prompt #{pid}: {stats.n_success}/{stats.n_attempted} OK")
    elif action == "run-batch":
        stats = run_batch(prompt_ids=ids, repeat=repeat, trigger_type="api")
        print(f"  batch: run #{stats.run_id} — {stats.n_success}/{stats.n_attempted} OK in {stats.elapsed_s:.1f}s")
    elif action == "delete":
        n = ps.delete_prompts(ids or [])
        print(f"  eliminati: {n}")
    elif action == "create":
        text = (payload.get("text") or "").strip()
        if not text:
            raise SystemExit("create: 'text' mancante")
        p = ps.create_prompt(
            text=text, category=payload.get("category"), geo=payload.get("geo"),
            intent=payload.get("intent"), force=True, created_by="gh-action",
        )
        print(f"  creato prompt #{p.id}")
    elif action == "generate":
        from src import prompt_generator as pg
        url = (payload.get("url") or "").strip()
        if not url:
            raise SystemExit("generate: 'url' mancante")
        res = pg.generate_from_url(url, provider=payload.get("provider", "auto"))
        added = 0
        for gp in res.prompts:
            try:
                ps.create_prompt(text=gp.text, category=gp.category, geo=gp.geo,
                                 intent=gp.intent, created_by="gh-generate")
                added += 1
            except ps.DuplicatePromptError:
                pass
        print(f"  generati {len(res.prompts)} prompt da {url}, aggiunti {added} (modello {res.model_used})")
    else:
        raise SystemExit(f"Azione sconosciuta: {action}")

    print("✓ fatto")


if __name__ == "__main__":
    main()
