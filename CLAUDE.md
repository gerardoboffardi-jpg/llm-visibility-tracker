# LLM Visibility Tracker — context per AI

> Per setup, comandi e architettura **leggere prima**: [`README.md`](./README.md). Questo file aggiunge solo guidance specifica per assistenti AI.

## TL;DR

Monitora la presenza di **talentgarden.com** e del brand "Talent Garden" nelle risposte degli LLM con **web search attivo**:
- Perplexity (`sonar`, `sonar-pro`)
- OpenAI (`gpt-5.6-terra` + tool `web_search` Responses API)
- Anthropic (Claude Sonnet 5 + `web_search_20250305`, thinking disabilitato)
- Google (Gemini 3.6 Flash + `google_search` grounding)

**Metrica chiave**: `citation_rate` = % di risposte che citano il dominio target come fonte.

Repo Git autonomo (`.git/` proprio).

## Stack (architettura attuale — niente Streamlit)

```
Sito statico (docs/index.html)  →  hostato su greenhouse.talentgarden (SSO org)
   │  READ  → Supabase (Postgres) via REST + publishable key (RLS read-only)
   │  WRITE → webhook n8n → GitHub API repository_dispatch
   ▼
GitHub Actions
   ├── visibility-actions.yml   → azioni on-demand (scripts/gh_action.py)
   ├── biweekly_batch.yml       → batch schedulato (settimane ISO pari)
   └── supabase_keepalive.yml   → ping REST lun+gio (evita la pausa free-tier)
   ▼
Supabase Postgres  ← unica fonte di verità (env DATABASE_URL)
```

- **Python** 3.11+ con `pyproject.toml` (`pip install -e .`), core: provider + scoring + ETL in `src/`.
- **SQLite** (`llm_visibility.db`) solo come default di sviluppo locale; **produzione = Supabase Postgres** (`DATABASE_URL`).
- API key in `.env` locale / secret GitHub Actions: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `PERPLEXITY_API_KEY`, `DATABASE_URL`.

## File chiave

| Path | Cosa è |
|---|---|
| `README.md` | quick start, comandi, metriche, deploy |
| `pyproject.toml` | dipendenze + entrypoint |
| `src/` | core: provider (`providers/`), analyzer, citation_analyzer, runner (ETL), storage (ORM), api (FastAPI opzionale) |
| `scripts/` | CLI: `seed_db`, `run_batch`, `gh_action` (dispatcher Actions), `gen_models` |
| `config/` | `models.yaml` (registro modelli + pricing), `brands.yaml` (target+competitor), `seed_prompts.yaml` |
| `docs/index.html` | sito statico SPA (8 tab), legge Supabase, scrive via n8n |
| `llm_visibility.db` | DB SQLite locale — **non pushare** se contiene dati reali |
| `.env` | API keys + DATABASE_URL — **mai committare** |

## Cosa NON committare

- `.env`
- `llm_visibility.db` (contiene risultati di run reali)
- `.venv/`, `.pytest_cache/`, `__pycache__/`, `.sentiment_cache.json`

`.gitignore` interno li copre — verificare con `git status` prima di pushare.

## Come lavorarci (per AI)

- **Aggiungere un provider**: nuovo modulo in `src/providers/` che estende `LLMProvider` (vedi gli esistenti), registrarlo in `src/providers/factory.py`; aggiungere la voce in `config/models.yaml`.
- **Modificare i modelli** (`config/models.yaml`): è l'**unica fonte** del registro. Dopo ogni modifica rigenerare il blocco `MODELS` del sito con `python -m scripts.gen_models` (idempotente; `--check` in CI).
- **Modificare prompt seed**: editare `config/seed_prompts.yaml` e ri-eseguire `python -m scripts.seed_db` (idempotente, appende i mancanti).
- **Run batch**: in produzione `--repeat 3` (smoothing), in dev `--repeat 1`.
- **Sito**: single-file, si apre localmente da browser; punta a Supabase di produzione.

## Operatività (deploy & infra)

- **Deploy del sito = MANUALE** (non più auto-deploy come il vecchio GitHub Pages). Dopo ogni modifica a `docs/index.html`:
  1. se hai toccato i modelli, `python -m scripts.gen_models`;
  2. commit + merge su `main` (sorgente di verità);
  3. **ridistribuisci su greenhouse** — app **id 53** (`LLM Visibility Tracker`), via MCP greenhouse `prepare_cli_upload` (zip con `index.html` a root) → `curl upload` → publish. Solo dopo l'upload il sito live cambia.
- **URL sito**: `https://greenhouse.talentgarden.com/gerardo-boffardi/llm-visibility-tracker` (SSO org-only). Il vecchio GitHub Pages è dismesso.
- **Supabase free-tier va in pausa dopo ~7 gg di inattività.** Il `supabase_keepalive.yml` (lun+gio) lo previene. Se la dashboard dà *"errore caricamento dati"* o *"Could not find table public.prompts"*:
  1. controlla lo stato progetto (`ref` `qbcmnqfnaixbhbuwfgdf`) via Supabase Management API o dashboard;
  2. se `INACTIVE` → **Restore** (dashboard o `POST /v1/projects/{ref}/restore`);
  3. dopo il restore ricarica la schema cache PostgREST: `notify pgrst, 'reload schema';`.
- **MCP Supabase**: richiede un **personal access token `sbp_…`** (non una `sb_secret_…`, che è una chiave API di progetto). Config in `.mcp.json`/`~/.claude.json` con `--project-ref=qbcmnqfnaixbhbuwfgdf`. La Management API (`api.supabase.com`) è raggiungibile col token `sbp_`; il subdominio `*.supabase.co` del progetto può non risolvere da alcuni ambienti sandbox.

## Cosa NON fare

- Non chiamare le API LLM senza `--repeat` configurato — i costi possono esplodere iterando su molti prompt.
- Non cambiare lo schema DB senza migrazione — i dati storici servono per i trend. `seo_plans` è modellata in `storage.py` ma la tabella prod vive su Supabase.
- Non disabilitare il web search nei provider: il senso del tracker è misurare la citazione *con* grounding attivo.
- Non editare a mano il blocco `MODELS` in `docs/index.html` (tra i marker `MODELS:GEN`): è generato da `models.yaml`.
- Non far girare batch schedulati senza `DATABASE_URL` in env: scriverebbero su SQLite locale invisibile alla dashboard.
