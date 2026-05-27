# LLM Visibility Tracker — context per AI

> Per setup, comandi e architettura **leggere prima**: [`README.md`](./README.md). Questo file aggiunge solo guidance specifica per assistenti AI.

## TL;DR

Monitora la presenza di **talentgarden.com** e del brand "Talent Garden" nelle risposte degli LLM con **web search attivo**:
- Perplexity (`sonar`, `sonar-pro`)
- OpenAI (`gpt-4o-search-preview`)
- Anthropic (Claude Sonnet 4.5 + `web_search_20250305`)
- Google (Gemini 2.0 + `google_search` grounding)

**Metrica chiave**: `citation_rate` = % di risposte che citano il dominio target come fonte.

Repo Git autonomo (`.git/` proprio).

## Stack

- **Python** 3.x con `pyproject.toml` (installabile via `pip install -e .`)
- **SQLite** locale (`llm_visibility.db`) — non un DB cloud
- **Streamlit** per la dashboard (`dashboard/app.py`)
- API key in `.env` (NON committare): `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `PERPLEXITY_API_KEY`

## File chiave

| Path | Cosa è |
|---|---|
| `README.md` | quick start, comandi, metriche |
| `pyproject.toml` | dipendenze + entrypoint |
| `src/` | core: provider, scoring, ETL |
| `scripts/` | CLI: `seed_db`, `run_batch` |
| `dashboard/` | app Streamlit |
| `config/` | prompt + target dominio |
| `llm_visibility.db` | DB SQLite — **non pushare** se contiene dati reali |
| `.env` | API keys — **mai committare** |

## Cosa NON committare

- `.env`
- `llm_visibility.db` (1.6 MB, contiene risultati di run reali)
- `.pytest_cache/`, `__pycache__/`

`.gitignore` interno dovrebbe già coprirli — verificare con `git status` prima di pushare.

## Come lavorarci (per AI)

- **Aggiungere un provider**: nuovo modulo in `src/` che implementa l'interfaccia provider (vedi quelli esistenti come reference), registrarlo nell'ETL `run_batch`.
- **Modificare prompt seed**: editare `config/` e ri-eseguire `python -m scripts.seed_db` (controllare se sovrascrive o appende).
- **Run batch**: in produzione `--repeat 3` (per smoothing), in dev `--repeat 1`.
- **Dashboard**: `streamlit run dashboard/app.py` — usa il DB SQLite locale, non serve setup cloud.

## Cosa NON fare

- Non chiamare le API LLM senza `--repeat` configurato — i costi possono esplodere se itera su molti prompt.
- Non cambiare lo schema del DB SQLite senza migrazione — i dati storici servono per i trend.
- Non disabilitare il web search nei provider: il senso del tracker è misurare la citazione *con* grounding attivo.
