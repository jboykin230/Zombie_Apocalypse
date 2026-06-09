# 🧟 Zombie Outbreak Monitor

An eerie [Streamlit](https://streamlit.io) app with a Retrieval-Augmented Generation
(RAG) pipeline over `Zombie_Plan.pdf`, plus a live AI-generated outbreak feed.

- **Left panel** — a live feed of fictional zombie events across the United States,
  generated 50 at a time by Claude. Stored in SQLite, hard-capped at **1000** entries
  (oldest evicted first).
- **Center console** — ask what to do next. Answers are grounded in excerpts retrieved
  from `Zombie_Plan.pdf` (ChromaDB + local embeddings) **and** the current live feed,
  then streamed from Claude.

## Stack

| Concern        | Choice |
| -------------- | ------ |
| UI             | Streamlit |
| LLM            | Claude Opus 4.8 (`claude-opus-4-8`) via the official `anthropic` SDK |
| Embeddings/RAG | ChromaDB with its built-in local `all-MiniLM-L6-v2` model (offline, no extra key) |
| PDF parsing    | `pypdf` |
| Event store    | SQLite (capped at 1000) |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # then edit .env and add your ANTHROPIC_API_KEY
```

## Run

```bash
streamlit run app.py
```

A **pre-built `chroma_db/` index ships with the repo**, and a fresh database is **seeded
from `seed_events.json` (50 events) on first boot** — so the feed is populated immediately
without waiting for the first Claude call or an index build. The ~80 MB MiniLM embedding
model is still downloaded on first use (it embeds your console questions).

To rebuild the index manually:

```bash
python ingest.py
```

## How the feed works

The event feed only generates while a browser tab is **actively viewing** the app.
The auto-refreshing panel sends a heartbeat every few seconds; the background thread
produces a new batch of 50 events at most once per minute, and **only** when a
heartbeat has arrived within the last ~15 seconds. Close the tab and generation
stops within ~15s — so there are **no API calls when nobody is watching**.

## Cost note

While a tab is open and watching, the feed makes ~1 Claude call per minute
(`effort: low`). The survival console makes one streamed call per question.

## Files

| File             | Purpose |
| ---------------- | ------- |
| `app.py`         | Streamlit UI (live feed + survival console) |
| `rag.py`         | PDF → Chroma index → retrieve → stream Claude answer |
| `events.py`      | Heartbeat-gated background event generator |
| `db.py`          | SQLite store, capped at 1000 entries |
| `ingest.py`      | CLI to (re)build the Chroma index |
| `reset.py`       | CLI to clear the SQLite store and Chroma index |

## Disclaimer

Entirely fictional. The generated events reference real US place names purely for
atmosphere and describe an imaginary scenario.
