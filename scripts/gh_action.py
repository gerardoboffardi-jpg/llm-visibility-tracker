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
    elif action == "bulk-create":
        items = payload.get("prompts") or []
        added = 0
        for it in items:
            txt = (it.get("text") or "").strip()
            if not txt:
                continue
            try:
                ps.create_prompt(text=txt, category=it.get("category"), geo=it.get("geo"),
                                 intent=it.get("intent"), created_by="pdf-generate")
                added += 1
            except ps.DuplicatePromptError:
                pass
        print(f"  bulk-create: {added}/{len(items)} aggiunti")
    elif action == "seo-plan":
        _generate_seo_plan(payload)
    else:
        raise SystemExit(f"Azione sconosciuta: {action}")

    print("✓ fatto")


def _generate_seo_plan(payload: dict) -> None:
    """Genera un piano SEO/GEO (AEO) in italiano via Claude e lo salva in seo_plans.

    Se `prompt_id` è nel payload → piano MIRATO a quel gap specifico (testo del
    prompt, competitor citati per quel prompt). Altrimenti piano globale.
    """
    import json as _json
    from sqlalchemy import text
    from src.storage import get_session

    pid = payload.get("prompt_id")
    pid = int(pid) if pid not in (None, "", "null") else None
    title = None

    with get_session() as s:
        if pid is not None:
            # Contesto MIRATO al singolo prompt/gap
            row = s.execute(text("select text, category, geo from prompts where id=:i"), {"i": pid}).fetchone()
            if not row:
                raise SystemExit(f"seo-plan: prompt {pid} non trovato")
            title = row[0]
            agg = s.execute(text(
                "select count(*) tot, count(*) filter (where has_target_mention) men, "
                "count(*) filter (where has_target_citation) cit from responses where prompt_id=:i"
            ), {"i": pid}).fetchone()
            comp = s.execute(text(
                "select c.domain, count(*) n from citations c join responses r on c.response_id=r.id "
                "where r.prompt_id=:i and c.is_competitor_domain group by c.domain order by n desc limit 10"
            ), {"i": pid}).fetchall()
            other = s.execute(text(
                "select c.domain, count(*) n from citations c join responses r on c.response_id=r.id "
                "where r.prompt_id=:i and not c.is_target_domain and not c.is_competitor_domain group by c.domain order by n desc limit 10"
            ), {"i": pid}).fetchall()
            ctx = {
                "prompt": row[0], "category": row[1], "geo": row[2],
                "risposte": agg[0], "mention_rate": round((agg[1] or 0)/agg[0], 3) if agg[0] else 0,
                "citation_rate": round((agg[2] or 0)/agg[0], 3) if agg[0] else 0,
                "competitor_citati": [f"{c[0]} ({c[1]})" for c in comp],
                "altri_domini_citati": [f"{o[0]} ({o[1]})" for o in other],
            }
            user = (
                "Gap di visibilità di Talent Garden su questo specifico prompt utente:\n"
                + _json.dumps(ctx, ensure_ascii=False, indent=2)
                + "\n\nScrivi un PIANO SEO/GEO (AEO) MIRATO a questo singolo prompt, in ITALIANO markdown: "
                "perché gli LLM non citano talentgarden.com qui, quali contenuti creare per questo intento, "
                "su quali domini (di quelli citati) farsi linkare, e azioni concrete prioritizzate. Max 500 parole."
            )
        else:
            # Contesto GLOBALE
            n = s.execute(text("select count(*) from responses")).scalar() or 0
            n_cit = s.execute(text("select count(*) from responses where has_target_citation")).scalar() or 0
            n_men = s.execute(text("select count(*) from responses where has_target_mention")).scalar() or 0
            gap_rows = s.execute(text(
                "select p.text from prompts p join responses r on r.prompt_id=p.id group by p.id,p.text "
                "having count(*) filter (where r.has_target_mention) > count(*) filter (where r.has_target_citation) limit 12"
            )).fetchall()
            comp = s.execute(text(
                "select domain, count(*) c from citations where is_competitor_domain group by domain order by c desc limit 10"
            )).fetchall()
            ctx = {
                "citation_rate": round(n_cit/n, 3) if n else 0, "mention_rate": round(n_men/n, 3) if n else 0,
                "n_responses": n, "gap_prompts": [g[0] for g in gap_rows],
                "competitor_domains": [f"{c[0]} ({c[1]})" for c in comp],
            }
            user = (
                "Dati di visibilità di Talent Garden (talentgarden.com) negli LLM:\n"
                + _json.dumps(ctx, ensure_ascii=False, indent=2)
                + "\n\nScrivi un PIANO SEO/GEO (AEO) GLOBALE operativo in ITALIANO markdown: priorità, contenuti, "
                "domini su cui farsi linkare, prompt/temi da presidiare. Max 700 parole, sezioni con bullet azionabili."
            )

    import anthropic
    client = anthropic.Anthropic()
    model = "claude-sonnet-5"
    resp = client.messages.create(
        model=model, max_tokens=2000,
        thinking={"type": "disabled"},  # Sonnet 5: evita che il thinking eroda i 2000 token del piano
        system="Sei un consulente senior SEO/GEO esperto di come gli LLM scelgono e citano le fonti. Scrivi piani concreti e prioritizzati.",
        messages=[{"role": "user", "content": user}],
    )
    content = "".join(b.text for b in resp.content if hasattr(b, "text"))
    with get_session() as s:
        s.execute(text("insert into seo_plans(content, model_used, prompt_id, title) values(:c,:m,:p,:t)"),
                  {"c": content, "m": model, "p": pid, "t": title})
        s.commit()
    print(f"  piano SEO/GEO {'per prompt '+str(pid) if pid else 'globale'} generato ({len(content)} char)")


if __name__ == "__main__":
    main()
