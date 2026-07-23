# LLM Visibility Tracker

Monitora la presenza di **talentgarden.com** (e del brand "Talent Garden") nelle risposte degli LLM con **web search attivo**: Perplexity (sonar / sonar-pro), OpenAI (GPT-5.6 Terra + tool `web_search` della Responses API), Anthropic (Claude Sonnet 5 + tool `web_search_20250305`), Google (Gemini 3.6 Flash + `google_search` grounding).

**Metrica chiave**: `citation_rate` = % di risposte in cui il dominio target è citato come fonte.

## Architettura (attuale)

Niente più Streamlit. Stack statico + serverless:

```
Sito statico (docs/index.html) — greenhouse.talentgarden (SSO org)
   │  READ  → Supabase (Postgres) via REST + chiave anon (RLS read-only)
   │  WRITE → webhook n8n
   ▼
n8n (talentgarden.app.n8n.cloud)  → GitHub API repository_dispatch
   ▼
GitHub Actions (.github/workflows/visibility-actions.yml)
   │  esegue scripts/gh_action.py (riusa src/): run/run-batch/delete/create/generate/seo-plan
   ▼
Supabase  ← unica fonte di verità
```

- **Sito interno**: https://greenhouse.talentgarden.com/gerardo-boffardi/llm-visibility-tracker (8 tab, read-only velocissimo, accesso SSO Talent Garden)
- **Azioni di scrittura** (rilancia/elimina/aggiungi/genera/piano SEO): bottoni del sito → n8n → GitHub Actions → Supabase
- **DB**: Supabase Postgres (pooler `aws-1-eu-central-1`)

## Comandi principali (CLI locale, opzionali)

| Comando | Descrizione |
|---|---|
| `python -m scripts.seed_db` | Inizializza/aggiorna DB e popola prompt iniziali (idempotente) |
| `python -m scripts.run_single_prompt --prompt-id 5 --repeat 3` | Esegue un singolo prompt |
| `python -m scripts.run_batch --repeat 3` | Esegue tutti i prompt attivi su tutti i modelli abilitati |
| `python -m scripts.gh_action` | Dispatcher azioni (usato da GitHub Actions; legge env `PAYLOAD`) |
| `python -m scripts.gen_models` | Rigenera il blocco `MODELS` in `docs/index.html` da `config/models.yaml` (`--check` per CI) |
| `pytest` | Esegue i test |

Setup locale: `pip install -r requirements-api.txt`, poi `cp .env.example .env` e inserisci le API key + `DATABASE_URL`.

## Configurazione

- **`config/brands.yaml`** — target (Talent Garden) + competitor con domini → modifica per aggiornare la lista
- **`config/models.yaml`** — modelli LLM, flag `enabled: true/false` per attivarli
- **`config/seed_prompts.yaml`** — 30 prompt iniziali (puoi aggiungerne dalla dashboard o via `bulk_import`)

## Struttura

```
llm-visibility-tracker/
├── config/                  # YAML editabili
├── src/
│   ├── storage.py           # SQLAlchemy models (prompts, runs, responses, citations, mentions)
│   ├── prompt_service.py    # CRUD + dedup fuzzy
│   ├── citation_analyzer.py # normalizza URL, classifica target/competitor/other
│   ├── analyzer.py          # mention detection nel testo + sentiment opzionale
│   ├── runner.py            # orchestrazione prompt × modello × repeat
│   ├── alerting.py          # detection drop + Slack webhook
│   ├── api.py               # FastAPI (opzionale, integrazione n8n/Zapier/HubSpot)
│   └── providers/           # adapter Perplexity / OpenAI search / Claude search / Gemini search
├── docs/                    # Sito statico (greenhouse SSO): index.html SPA multi-tab
├── scripts/                 # CLI + gh_action.py (dispatcher Actions) + gen_models.py
├── tests/                   # test (pytest)
└── .github/workflows/       # visibility-actions.yml (azioni on-demand) + biweekly_batch.yml (cron)
```

## Sito (greenhouse.talentgarden, SSO)

Single-file `docs/index.html` (Tailwind + Chart.js + supabase-js via CDN, brand TAG coral + Poppins). Legge in sola lettura da Supabase; le azioni di scrittura passano dai webhook n8n. 8 tab con navigazione client-side istantanea:

1. **📊 Overview** — KPI (citation/mention rate, share, gap), domain mix, trend
2. **📝 Prompts** — lista + selezione multipla (rilancia/elimina) + Aggiungi/Genera da URL
3. **💬 Risposte** — feed filtrabile (prompt, modello, stato), risposte full-width in slider orizzontale per modello, markdown renderizzato
4. **🔬 Prompt Detail** — singolo prompt, ripetizioni affiancate per modello
5. **🤖 Models** — confronto search vs chat
6. **🔗 Citations** — domain mix target/competitor/altri
7. **🎯 Recommendations** — gap + **piano SEO/GEO con l'AI** (globale o per singolo gap)
8. **💰 Costi & Run** — spesa stimata per modello/run

## Deploy / configurazione (architettura attuale)

### 1. Supabase (DB)
Tabelle create + RLS con policy `SELECT` per ruolo `anon` (sola lettura). Il sito usa la **publishable key**; le scritture passano dalle GitHub Actions via `DATABASE_URL` (pooler, bypassa RLS).

### 2. greenhouse.talentgarden (sito)
App interna `LLM Visibility Tracker` (id 53), accesso **SSO org-only**. URL: `https://greenhouse.talentgarden.com/gerardo-boffardi/llm-visibility-tracker`.

**Deploy del sito**: non è auto-deploy da git (a differenza del vecchio GitHub Pages). Dopo aver modificato `docs/index.html` (o rigenerato il blocco `MODELS`), ricaricare il file su greenhouse — via piattaforma interna greenhouse (MCP `prepare_cli_upload` / `push_file`, app id 53). Nota storica: prima il sito era su GitHub Pages (`gerardoboffardi-jpg.github.io/llm-visibility-tracker`), ora dismesso.

### 3. GitHub Actions (motore azioni)
`visibility-actions.yml` su `repository_dispatch (type: visibility)` + `workflow_dispatch`. Secret repo: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `PERPLEXITY_API_KEY`, `DATABASE_URL`.

### 4. n8n (bridge scrittura)
Workflow "LLM Visibility — Bridge": webhook `…/webhook/llmv-visibility` → GitHub API `repository_dispatch` con `client_payload = {action, ...}`. Token GitHub come header (consigliato: PAT fine-grained, `Actions: write`).

Il sito posta `{action: "run-batch"|"delete"|"create"|"generate"|"seo-plan", ...}` all'unico webhook.

## Automazione

### GitHub Actions (biweekly)

Il workflow `.github/workflows/biweekly_batch.yml` parte ogni **lunedì alle 06:00 UTC** (`cron: '0 6 * * 1'`) ma un job `gate` esegue il batch **solo nelle settimane ISO pari** → cadenza effettiva **ogni 2 settimane** (per contenere i costi API). `workflow_dispatch` forza sempre l'esecuzione.

**Setup secrets** (Settings → Secrets and variables → Actions):
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `PERPLEXITY_API_KEY`
- `SLACK_WEBHOOK_URL` (opzionale, per alerting)

Scrive su **Supabase Postgres** (env `DATABASE_URL`), unica fonte di verità. Nota storica: le prime versioni salvavano un DB SQLite come artifact tra le run — ora superato da Supabase.

### Supabase Keep-Alive (lun + gio)

`.github/workflows/supabase_keepalive.yml` fa un ping REST leggero al DB **due volte a settimana** (nessuna chiamata LLM, costo zero). Serve perché i progetti Supabase **free vanno in pausa dopo ~7 giorni di inattività**: con il batch biweekly (14 gg) la DB si ripauserebbe tra una run e l'altra. Girando lun+gio, l'intervallo tra due richieste resta sempre < 7 giorni. Se il progetto è già in pausa il ping fallisce (serve un **Restore** manuale dalla dashboard Supabase). URL + publishable key sono valori pubblici (come nel sito); sovrascrivibili con le repo Variables `SUPABASE_URL` / `SUPABASE_ANON_KEY`.

### Cron locale (alternativa)

```cron
# crontab -e
0 7 * * 1  cd /path/to/llm-visibility-tracker && /path/to/.venv/bin/python -m scripts.run_batch_with_alerts --repeat 3 >> ~/llm-visibility.log 2>&1
```

### Alerting Slack

Imposta `SLACK_WEBHOOK_URL` in `.env` (Incoming Webhook). Variabili opzionali:
- `ALERT_DROP_THRESHOLD=0.10` — soglia drop citation rate (default 10pt %)
- `ALERT_BASELINE_RUNS=3` — n. run precedenti usate come baseline

Trigger automatici:
- 🚨 **critical** se citation rate scende ≥ soglia rispetto alla baseline
- ⚠️ **warning** se appaiono nuovi domini competitor mai citati prima
- ℹ️ **info** se citation rate sale ≥ soglia (good news)

### API HTTP (FastAPI, opzionale)

```bash
pip install -e ".[api]"
uvicorn src.api:app --reload --port 8000
```

Esempi (utili da n8n/Zapier/HubSpot):
```bash
# Aggiungi un prompt da workflow esterno
curl -X POST http://localhost:8000/prompts \
  -H "X-Api-Key: $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Migliori coworking a Bologna","category":"coworking","geo":"Bologna","run_now":true}'

# Triggera run on-demand
curl -X POST "http://localhost:8000/prompts/5/run?repeat=3" -H "X-Api-Key: $API_TOKEN"
```

Auth: opzionale via `API_TOKEN` in env (header `X-Api-Key`). Se non settato, l'API è aperta (usa solo in localhost).

## Costi stimati

- ~$15-25 per run completa con 30 prompt × 8 modelli × 3 ripetizioni
- ~$30-50/mese con cadenza biweekly (2 run/mese)
- Nota: Anthropic addebita ~$10 per 1000 ricerche web extra

## Sviluppo / contribuire

```bash
pip install -e ".[dev]"
pytest                    # 40 test
ruff check .              # lint
```
