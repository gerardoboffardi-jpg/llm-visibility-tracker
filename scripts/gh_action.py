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
    elif action == "seo-plan":
        _generate_seo_plan()
    else:
        raise SystemExit(f"Azione sconosciuta: {action}")

    print("✓ fatto")


def _generate_seo_plan() -> None:
    """Costruisce un contesto dai dati (metriche + gap + competitor) e fa scrivere
    a Claude un piano SEO/GEO (AEO) in italiano; salva il risultato in seo_plans."""
    import os as _os
    from collections import Counter
    from sqlalchemy import text
    from src.storage import get_session

    with get_session() as s:
        n = s.execute(text("select count(*) from responses")).scalar() or 0
        n_cit = s.execute(text("select count(*) from responses where has_target_citation")).scalar() or 0
        n_men = s.execute(text("select count(*) from responses where has_target_mention")).scalar() or 0
        gap_rows = s.execute(text(
            "select p.text, count(*) filter (where r.has_target_mention) as men, "
            "count(*) filter (where r.has_target_citation) as cit, count(*) as tot "
            "from prompts p join responses r on r.prompt_id=p.id group by p.id, p.text "
            "having count(*) filter (where r.has_target_mention) > count(*) filter (where r.has_target_citation) "
            "order by (count(*) filter (where r.has_target_mention)-count(*) filter (where r.has_target_citation)) desc limit 12"
        )).fetchall()
        comp = s.execute(text(
            "select domain, count(*) c from citations where is_competitor_domain group by domain order by c desc limit 10"
        )).fetchall()
        nocit = s.execute(text(
            "select p.text from prompts p join responses r on r.prompt_id=p.id "
            "group by p.id,p.text having count(*) filter (where r.has_target_citation)=0 limit 12"
        )).fetchall()

    cr = (n_cit / n) if n else 0
    mr = (n_men / n) if n else 0
    ctx = {
        "citation_rate": round(cr, 3), "mention_rate": round(mr, 3), "n_responses": n,
        "gap_prompts": [g[0] for g in gap_rows],
        "never_cited_prompts": [g[0] for g in nocit],
        "competitor_domains": [f"{c[0]} ({c[1]})" for c in comp],
    }
    import json as _json
    user = (
        "Dati di visibilità di Talent Garden (talentgarden.com) negli LLM:\n"
        + _json.dumps(ctx, ensure_ascii=False, indent=2)
        + "\n\nScrivi un PIANO SEO/GEO (Generative Engine Optimization / AEO) operativo in ITALIANO, in markdown, "
        "che spieghi azioni concrete per aumentare citation rate e mention rate: priorità, contenuti da creare, "
        "domini su cui farsi linkare (dove i competitor dominano), prompt/temi da presidiare. Massimo 700 parole, "
        "strutturato in sezioni con bullet azionabili."
    )
    import anthropic
    client = anthropic.Anthropic()
    model = "claude-sonnet-4-5"
    resp = client.messages.create(
        model=model, max_tokens=2000,
        system="Sei un consulente senior SEO/GEO esperto di come gli LLM scelgono e citano le fonti. Scrivi piani concreti e prioritizzati.",
        messages=[{"role": "user", "content": user}],
    )
    content = "".join(b.text for b in resp.content if hasattr(b, "text"))
    with get_session() as s:
        s.execute(text("insert into seo_plans(content, model_used) values(:c, :m)"),
                  {"c": content, "m": model})
        s.commit()
    print(f"  piano SEO/GEO generato ({len(content)} char) e salvato")


if __name__ == "__main__":
    main()
