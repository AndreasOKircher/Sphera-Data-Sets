# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Python toolkit for downloading, parsing, viewing, and LLM-enriching **Sphera LCA datasets** (ILCD XML format). Datasets describe industrial processes for Life Cycle Assessment (LCA). The pipeline converts verbose ILCD XML into flat JSON, indexes it into ChromaDB for semantic search, and exposes a Flask web viewer with LLM-driven Q&A.

See `README.md` for full field definitions, workflow, and LLM provider setup.

## Environment

**Windows venv accessed from WSL.** Python is at `.venv/Scripts/python.exe` — not `.venv/bin/python`.

```bash
# All commands from Windows terminal or via WSL:
.venv\Scripts\python <script>
.venv\Scripts\pytest tests/ -v
```

## Key Commands

See **Tools and Helpers** in `README.md` for all CLI commands and flags.

## Architecture

Core pipeline: `download.py` → `dataset/output/{uuid}.xml + .json` → `index.py` → `dataset/chroma/` → `viewer/app.py`

| Layer | Module | Role |
|---|---|---|
| Parsing | `core/parser.py` | ILCD XML → flat dict (36 fields) |
| XLS manifest | `core/xls_manifest.py` | Injects `source_url`, `process_type`, `databases` into JSON |
| Vector index | `core/chroma_store.py` | ChromaDB build + semantic search + metadata filters |
| LLM abstraction | `core/llm.py` | Anthropic / VIO, single `complete()` interface |
| Enrichment | `core/enricher.py` | LLM summary + formatted rewrite of `technology_description` |
| Viewer | `viewer/app.py` | Flask: list, detail, `/search` (RAG), `/chat` (multi-turn) |
| Field layout | `viewer/sections.py` | Which fields appear in which viewer section |

See `docs/architecture.md` for deeper design notes (to be created as needed).

## Key Conventions

- **Never modify raw XML** — `dataset/output/{uuid}.xml` is the source of truth
- **Enrichment is a sidecar** — lives in `dataset/enriched/{uuid}.json`, never merged into the original JSON
- **All LLM calls go through `core/llm.py`** — never call Anthropic or VIO APIs directly
- **Field priority tiers: MUST / NICE / Other** — defined in `README.md` and enforced in `core/parser.py` (`MUST_FIELDS`, `NICE_FIELDS`) and `viewer/sections.py`
- **ChromaDB search design:** semantic on `technology_description_summary` (10a); keyword on `name_base` + `synonyms`; metadata filters on `location`, `databases`, `process_type`, `dataset_type` — see `README.md` for full search design
- **`/chat` result enrichment:** after `run_query()` returns, `/chat` injects `location` and `process_type` from the dataset metadata into each result dict before responding — these are not returned by `/query`
- **Chat bubble format:** `**rank. name** · location · process_type — score/5` + comment; rendered via `renderMarkdown()` in `index.html`; `@keyframes spin` in `base.html` drives the ⏳ busy indicator

## Testing

Tests live in `tests/`. Run all with `.venv\Scripts\pytest tests/ -v`.

- LLM calls are mocked in tests — no API key required
- ChromaDB tests use an in-memory store
- Add tests for any new `core/` module; viewer route tests go in `test_search_endpoint.py` / `test_chat_endpoint.py`

## Ideas & Planning

- `idea/` — scratch space, not tracked in git
- `docs/superpowers/plans/` — implementation plans for major features

## Safety & Execution Rules

- Always read relevant code and tests before editing. If behavior or constraints are unclear, ask 1–3 focused questions before making changes.
- Treat schema changes, data migrations, bulk file edits, and destructive operations as **high-risk**: propose a step-by-step plan first, wait for explicit approval before executing.
- Prefer small, reviewable patches. Run or add tests where possible; report failing tests rather than guessing fixes.
- Never fabricate confidence. If uncertain, say so and offer options.
