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
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

load_dotenv(override=True)

from src import prompt_service as ps  # noqa: E402
from src.runner import run_single  # noqa: E402

app = FastAPI(
    title="LLM Visibility Tracker API",
    version="0.1.0",
    description="Aggiungi prompt e triggera run da sistemi esterni.",
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
