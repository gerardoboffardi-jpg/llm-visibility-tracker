# LLM Visibility Tracker

Monitora la presenza di **talentgarden.com** (e del brand "Talent Garden") nelle risposte degli LLM con **web search attivo**: Perplexity (sonar / sonar-pro), OpenAI (gpt-4o-search-preview), Anthropic (Claude Sonnet 4.5 + tool `web_search_20250305`), Google (Gemini 2.0 + `google_search` grounding).

**Metrica chiave**: `citation_rate` = % di risposte in cui il dominio target è citato come fonte.

## Quick start

```bash
# 1. Setup
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. API key
cp .env.example .env
# poi inserisci ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY, PERPLEXITY_API_KEY

# 3. Inizializza DB e seed con 30 prompt iniziali
python -m scripts.seed_db

# 4. Esegui il primo batch (1 ripetizione per velocità; in produzione usa --repeat 3)
python -m scripts.run_batch --repeat 1

# 5. Apri la dashboard
streamlit run dashboard/app.py
```

## Comandi principali

| Comando | Descrizione |
|---|---|
| `python -m scripts.seed_db` | Inizializza/aggiorna DB e popola prompt iniziali (idempotente) |
| `python -m scripts.smoke_test_providers` | Verifica che le API key funzionino su tutti i provider |
| `python -m scripts.run_single_prompt --prompt-id 5 --repeat 3` | Esegue un singolo prompt |
| `python -m scripts.run_batch --repeat 3` | Esegue tutti i prompt attivi su tutti i modelli abilitati |
| `python -m scripts.run_batch_with_alerts --repeat 3` | Come sopra + invia alert su Slack |
| `streamlit run dashboard/app.py` | Avvia la dashboard |
| `pytest` | Esegue i test (40 test, ~1s) |

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
├── dashboard/               # Streamlit multipagina
├── scripts/                 # CLI runnable
├── tests/                   # 40 test (pytest)
└── .github/workflows/       # batch settimanale automatico
```

## Dashboard

Stile ispirato a [HubSpot AEO](https://www.hubspot.com/products/aeo): palette TAG coral + Poppins, card moderne, risposte LLM in formato **chat con bubble** (prompt + risposta + avatar engine).

7 viste:

1. **Home** — hero stile HubSpot con KPI (citation rate, mention rate, share, gap) + preview ultime risposte LLM in chat-style
2. **📊 Overview** — top 10 per citation rate, top 10 citation gap, domain mix, trend
3. **💬 Risposte** — feed cronologico di **tutte** le risposte LLM con filtri (prompt, modello, citazione/menzione/gap), engine summary cards e bubble chat
4. **📝 Prompts** — tabella prompt + 3 modalità di aggiunta:
   - **🪄 Genera da URL/Brochure** — incolla un URL o carica un PDF, l'LLM (Claude → fallback OpenAI) estrae il contenuto e propone 20-30 prompt realistici da revisionare e importare
   - **➕ Aggiungi prompt** singolo con dedup fuzzy
   - **📤 Import YAML/CSV** in bulk
5. **🔬 Prompt Detail** — singolo prompt con tutte le risposte in chat-style raggruppate per engine
6. **🔗 Citations** — URL aggregate (target, competitor, neutri ricorrenti)
7. **🤖 Models** — confronto performance modelli

### Come usare con il team (no-code)

Una volta deployata su Streamlit Cloud (vedi sotto):

1. Mandi al team il link `https://llm-visibility-tracker-tuoaccount.streamlit.app` + la `APP_PASSWORD` condivisa
2. Ogni persona accede da browser, inserisce la password una volta
3. La dashboard è in lettura/scrittura: chiunque può aggiungere prompt dalla pagina **📝 Prompts**, rilanciare un singolo prompt dalla pagina **🔬 Prompt Detail**, esplorare risposte dalla pagina **💬 Risposte**
4. I batch settimanali girano in automatico via GitHub Actions — nessuno deve toccare la CLI

## Deploy su Streamlit Community Cloud (gratis, link condivisibile)

### 1. Database Postgres su Supabase (gratis)

1. Crea un progetto su [supabase.com](https://supabase.com) → region **Frankfurt**
2. Dopo creazione → **Settings → Database → Connection string** → tab "URI"
3. Spunta "Use connection pooling" (importante per Streamlit Cloud)
4. Copia la stringa, formato:
   ```
   postgresql://postgres.xxxxxx:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
   ```
5. Sostituisci `[YOUR-PASSWORD]` con la password del DB

### 2. Streamlit Community Cloud

1. Vai su [share.streamlit.io](https://share.streamlit.io) → sign in con GitHub
2. "Create app" → seleziona repo `llm-visibility-tracker`, branch `main`, main file `dashboard/app.py`
3. Prima del deploy clicca **Advanced settings → Secrets** e incolla (vedi `.streamlit/secrets.toml.example`):
   ```toml
   APP_PASSWORD = "una-password-condivisa"
   DATABASE_URL = "postgresql://..."  # da Supabase
   ANTHROPIC_API_KEY = "sk-ant-..."
   OPENAI_API_KEY = "sk-..."
   GOOGLE_API_KEY = "AIza..."
   PERPLEXITY_API_KEY = "pplx-..."
   ```
4. "Deploy" → 2 min e ottieni un link tipo `https://llm-visibility-tracker-tuoaccount.streamlit.app`
5. Il DB sarà inizializzato automaticamente al primo avvio (schema vuoto)

### 3. Seed iniziale dei prompt (da locale, una volta sola)

Imposta in locale `DATABASE_URL` puntando a Supabase, poi:
```bash
DATABASE_URL="postgresql://..." python -m scripts.seed_db
DATABASE_URL="postgresql://..." python -m scripts.run_batch --repeat 1
```

In alternativa: aggiungi le righe al workflow GitHub Actions e lascia che le esegua lui.

### 4. Condividi il link
Chi riceve il link inserisce la `APP_PASSWORD` e accede.

## Automazione

### GitHub Actions (settimanale)

Il workflow `.github/workflows/weekly_batch.yml` esegue il batch ogni **lunedì alle 06:00 UTC**.

**Setup secrets** (Settings → Secrets and variables → Actions):
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `PERPLEXITY_API_KEY`
- `SLACK_WEBHOOK_URL` (opzionale, per alerting)

Il DB SQLite è salvato come **artifact** tra le run (retention 90 giorni).
Per uso in produzione consigliato **DB esterno** (Postgres su Supabase/Neon) — modifica `DATABASE_URL` in env.

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

- ~$20-30 per run completa con 50 prompt × 5 modelli × 3 ripetizioni
- ~$80-120/mese con cadenza settimanale
- Nota: Anthropic addebita ~$10 per 1000 ricerche web extra

## Sviluppo / contribuire

```bash
pip install -e ".[dev]"
pytest                    # 40 test
ruff check .              # lint
```
