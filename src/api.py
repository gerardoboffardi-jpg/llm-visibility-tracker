"""Endpoint FastAPI minimale per integrazione con altri sistemi.

Casi d'uso:
- aggiungere prompt da n8n / Zapier / HubSpot workflow
- triggerare run on-demand da fuori
- leggere KPI per dashboard esterne

Avvio:
    uvicorn src.api:app --reload --port 8000

Auth: header `X-Api-Key` con valore da env `API_TOKEN` (se non settato, l'API è aperta).
"""
from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv(override=True)

from src import prompt_service as ps  # noqa: E402
from src.runner import run_batch, run_single  # noqa: E402

app = FastAPI(
    title="LLM Visibility Tracker API",
    version="0.1.0",
    description="Aggiungi prompt e triggera run da sistemi esterni.",
)

# CORS: il sito statico (GitHub Pages) e n8n possono chiamare l'API.
# Origini extra via env CORS_ORIGINS (csv). Le chiamate da n8n sono server-to-server
# (CORS irrilevante), ma serve se il sito chiamasse direttamente.
_origins = [
    "https://gerardoboffardi-jpg.github.io",
    "http://localhost:8788",
    "http://localhost:8767",
]
_extra = os.getenv("CORS_ORIGINS", "")
if _extra:
    _origins += [o.strip() for o in _extra.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def auth(x_api_key: Optional[str] = Header(default=None, alias="X-Api-Key")):
    expected = os.getenv("API_TOKEN")
    if not expected:
        return  # auth disattivata
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ---------- Schemi ----------

class CreatePromptIn(BaseModel):
    text: str
    category: str | None = None
    geo: str | None = None
    intent: str | None = None
    notes: str | None = None
    force: bool = False
    run_now: bool = False


class PromptOut(BaseModel):
    id: int
    text: str
    category: str | None
    geo: str | None
    intent: str | None
    is_active: bool


class RunResult(BaseModel):
    run_id: int
    n_attempted: int
    n_success: int
    n_errors: int
    elapsed_s: float


# ---------- Endpoint ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/prompts", response_model=list[PromptOut], dependencies=[Depends(auth)])
def list_prompts(active_only: bool = True):
    items = ps.list_prompts(only_active=True if active_only else None)
    return [
        PromptOut(
            id=p.id, text=p.text, category=p.category, geo=p.geo,
            intent=p.intent, is_active=p.is_active,
        )
        for p in items
    ]


@app.post("/prompts", response_model=PromptOut, dependencies=[Depends(auth)])
def create_prompt(payload: CreatePromptIn):
    try:
        p = ps.create_prompt(
            text=payload.text, category=payload.category, geo=payload.geo,
            intent=payload.intent, notes=payload.notes, force=payload.force,
            created_by="api",
        )
    except ps.DuplicatePromptError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "duplicate",
                "existing_id": e.warning.existing_id,
                "similarity": e.warning.similarity,
                "existing_text": e.warning.existing_text,
            },
        )
    if payload.run_now:
        run_single(p.id, repeat=1, trigger_type="api")
    return PromptOut(
        id=p.id, text=p.text, category=p.category, geo=p.geo,
        intent=p.intent, is_active=p.is_active,
    )


@app.post("/prompts/{prompt_id}/run", response_model=RunResult, dependencies=[Depends(auth)])
def run_prompt(prompt_id: int, repeat: int = 1, models: list[str] | None = None):
    p = ps.get_prompt(prompt_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    stats = run_single(prompt_id, model_ids=models, repeat=repeat, trigger_type="api")
    return RunResult(
        run_id=stats.run_id,
        n_attempted=stats.n_attempted,
        n_success=stats.n_success,
        n_errors=stats.n_errors,
        elapsed_s=stats.elapsed_s,
    )


@app.delete("/prompts/{prompt_id}", dependencies=[Depends(auth)])
def deactivate(prompt_id: int):
    if ps.get_prompt(prompt_id) is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    ps.deactivate_prompt(prompt_id)
    return {"status": "deactivated", "id": prompt_id}


# ---------- Endpoint bulk / batch / generate (per il sito statico via n8n) ----------

class IdsIn(BaseModel):
    prompt_ids: list[int]


class RunBatchIn(BaseModel):
    prompt_ids: list[int] | None = None  # None = tutti gli attivi
    repeat: int = 1


class GenerateUrlIn(BaseModel):
    url: str
    provider: str = "auto"


class BulkCreateIn(BaseModel):
    prompts: list[CreatePromptIn]


@app.post("/prompts/bulk-delete", dependencies=[Depends(auth)])
def bulk_delete(payload: IdsIn):
    """Elimina definitivamente i prompt indicati (+ risposte/citazioni/menzioni)."""
    n = ps.delete_prompts(payload.prompt_ids)
    return {"status": "deleted", "count": n}


@app.post("/prompts/run-batch", dependencies=[Depends(auth)])
def run_batch_endpoint(payload: RunBatchIn, background: BackgroundTasks):
    """Esegue un batch in BACKGROUND (fire-and-forget): risponde subito, le
    risposte compaiono su Supabase man mano. Il sito ricarica i dati."""
    background.add_task(
        run_batch,
        prompt_ids=payload.prompt_ids,
        repeat=payload.repeat,
        trigger_type="api",
    )
    n = len(payload.prompt_ids) if payload.prompt_ids else None
    return {"status": "started", "prompt_ids": payload.prompt_ids, "n": n, "repeat": payload.repeat}


@app.post("/prompts/bulk-create", dependencies=[Depends(auth)])
def bulk_create(payload: BulkCreateIn):
    """Crea più prompt in una volta (es. dopo generazione). Salta i duplicati."""
    added, dup = [], 0
    for item in payload.prompts:
        try:
            p = ps.create_prompt(
                text=item.text, category=item.category, geo=item.geo,
                intent=item.intent, notes=item.notes, force=item.force, created_by="api",
            )
            added.append(p.id)
        except ps.DuplicatePromptError:
            dup += 1
    return {"status": "ok", "added": added, "skipped_duplicates": dup}


@app.post("/generate/url", dependencies=[Depends(auth)])
def generate_url(payload: GenerateUrlIn):
    """Genera prompt da un URL (no save): ritorna la lista per review."""
    from src import prompt_generator as pg
    try:
        result = pg.generate_from_url(payload.url, provider=payload.provider)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "source_label": result.source_label,
        "model_used": result.model_used,
        "prompts": [p.as_dict() for p in result.prompts],
    }
