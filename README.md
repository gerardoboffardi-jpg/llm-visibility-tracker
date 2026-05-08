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

5 pagine:

1. **Home** — KPI globali (citation rate, mention rate, share of citations, citation gap)
2. **Overview** — top 10 prompt per citation rate, top 10 citation gap, domain mix, trend
3. **Prompts** — tabella con citation rate evidenziato + filtri + form "➕ Aggiungi prompt" con dedup fuzzy e checkbox "esegui subito"
4. **Prompt Detail** — risposte per modello con brand evidenziati e citazioni colorate; bottoni Rilancia / Modifica / Disattiva / Duplica
5. **Citations** — esplora URL aggregate (target, competitor, neutri ricorrenti)
6. **Models** — confronto performance modelli

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
