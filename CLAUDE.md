# CLAUDE.md

Guidance for working in this repo.

## What this is

**Zombie Outbreak Monitor** — a Streamlit app with a RAG pipeline over `Zombie_Plan.pdf`
plus a live, AI-generated outbreak feed. Entirely fictional/atmospheric.

Two halves of the UI ([app.py](app.py)):
- **Left** — a live feed of fictional zombie events across the US, generated 50 at a time
  by Claude, plus an interactive D3 US map (explosions for the current batch, persistent
  dots for past high/critical events, a marker for the joined survivor).
- **Right** — the **Survival Console**: ask what to do next; answers are grounded in
  excerpts retrieved from `Zombie_Plan.pdf` (ChromaDB + local embeddings) **and** the
  current live feed, then streamed from Claude.

## Stack

| Concern | Choice |
| --- | --- |
| UI | Streamlit (fragments + sandboxed HTML/JS iframes) |
| LLM | Claude Opus 4.8 (`claude-opus-4-8`) via the official `anthropic` SDK |
| Embeddings/RAG | ChromaDB built-in local `all-MiniLM-L6-v2` (offline, no extra key) |
| PDF parsing | `pypdf` |
| Event store | SQLite, FIFO-capped at 1000 entries |
| Map | D3 + topojson + us-atlas (loaded from CDN — needs internet) |

## Files

| File | Purpose |
| --- | --- |
| [app.py](app.py) | Streamlit UI — boot, feed/map fragments, join dialog, survival console |
| [rag.py](rag.py) | PDF → chunk → Chroma index → retrieve top-k → stream Claude answer |
| [events.py](events.py) | Heartbeat-gated background batch generator (JSON-schema output) |
| [db.py](db.py) | SQLite store: `events` (capped 1000), `users`, `queries` |
| [ui_components.py](ui_components.py) | Render helpers: feed, D3 map, join tutorial (HTML/JS in iframes) |
| [ingest.py](ingest.py) | CLI to (re)build the Chroma index |

## Setup & run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add a real ANTHROPIC_API_KEY
streamlit run app.py
```

First launch downloads the ~80 MB MiniLM model once. **Every** startup re-extracts and
re-indexes `Zombie_Plan.pdf` into `./chroma_db` (see "Reinitialize on startup" below).
Rebuild the index manually with `python ingest.py`.

## Key behaviors / gotchas

- **Reinitialize on startup**: `boot()` in [app.py](app.py) (an `@st.cache_resource`, so it
  runs **once per Streamlit server process**, not per browser rerun) calls
  `db.reset_db()` and `rag.reset_index()`. Each server start therefore **drops all
  events/users/queries** and **re-embeds the whole PDF** (~252 chunks, a few seconds). A
  page refresh does *not* re-trigger it; only restarting `streamlit run` does.
- **Heartbeat gating**: the feed generator ([events.py](events.py)) only produces batches
  while a browser tab is actively watching. The UI calls `heartbeat()` on every fragment
  refresh; if none arrives within `ACTIVE_TIMEOUT` (30s), the thread idles and makes **no
  API calls**. New batch at most once per `INTERVAL_SECONDS` (60s), 50 events each.
- **Cost**: while watched, ~1 Claude call/min for the feed (`effort: low`); one streamed
  call per console question (`effort: medium`).
- **Data flow into the map/feed iframes is one-way (Python → iframe)**. All data *entry*
  uses native Streamlit widgets in [app.py](app.py) so it reliably reaches SQLite.
- **Batch identity** = the shared `created_at` timestamp. Map explosions / feed fade-ins
  fire only when `batch_id` changes (guarded via `sessionStorage`).
- **Persistent markers**: only `high`/`critical` events survive across minutes
  (see `_update_persistent` in [app.py](app.py)); `low`/`moderate` are dropped.
- The model id `claude-opus-4-8` and the `output_config`/`effort` params are used in both
  [rag.py](rag.py) and [events.py](events.py) — keep them in sync if changing the model.

## Git

`.env`, `chroma_db/`, `zombie_events.db`, `.venv/`, `__pycache__/`, and `*.log` are
gitignored. Don't commit secrets or the generated DB/index.
