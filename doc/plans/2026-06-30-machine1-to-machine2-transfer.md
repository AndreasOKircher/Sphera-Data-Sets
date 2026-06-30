# Machine 1 → Machine 2 Transfer Plan

**Date:** 2026-06-30  
**Goal:** Download the complete Sphera dataset corpus on Machine 1, test enrichment and the web viewer locally, then transfer everything to Machine 2 (limited internet) for VIO-based enrichment and ongoing viewer use.

---

## Current State on Machine 1

| Item | Count / Size |
|---|---|
| XLS manifest entries | 19,644 datasets |
| Downloaded datasets (`dataset/output/`) | 6,723 JSON+XML pairs — 1.5 GB |
| Enrichment sidecars (`dataset/enriched/`) | 388 files — 3 MB |
| ChromaDB index (`dataset/chroma/`) | Partial — 238 MB |

---

## README Deviations Fixed (2026-06-30)

Five corrections applied to `README.md`:

| Location | Was | Fixed to |
|---|---|---|
| Workflow §1 | `download.py --urls urls.txt` | `download.py --xls <manifest>.xlsx` as primary; `--urls` as alternative |
| Workflow §3 index | "text indexed: name_base + classification + general_comment" | Accurate: enriched summary primary, fallback for unenriched datasets |
| Tools table | `--urls urls.txt` | `--xls <manifest>.xlsx` |
| CLI flags `download.py` | Missing `--xls` and `--databases` | Both added with descriptions |
| I/O table | "33 fields" + no XLS entry | "36 fields" + XLS manifest row added |

---

## Phase A — Complete the Download on Machine 1

### A1. Refresh the Sphera session cookie

1. Log in to the Sphera portal in Chrome
2. F12 → Network → click any request → copy the full `Cookie:` header value
3. Overwrite `cookie.txt` with the new value

### A2. Run the bulk download

```bash
.venv\Scripts\python download.py --xls "dataset/input/Sphera-Dataset-List-MLC-Databases-2026.1-Edition.xlsx" --cookie-file cookie.txt
```

- Auto-skips the 6,723 already downloaded — safe to re-run at any time
- Prints `[OK]`, `[SKIP]`, or `[FAIL]` per dataset
- On completion: `Done. N ok · N skipped · N failed.`
- If failures occur → `dataset/output/failed_uuids_<timestamp>.txt` is written

### A3. Retry failures

The session cookie can expire during a long run. If any datasets fail:

```bash
# Refresh cookie.txt first if needed
.venv\Scripts\python download.py --urls "dataset/output/failed_uuids_<timestamp>.txt" --cookie-file cookie.txt
```

Repeat until 0 failures. Target: ~19,644 JSON+XML pairs in `dataset/output/`.

**Estimated final size of `dataset/output/`: 4–5 GB**

---

## Phase B — Build the Full ChromaDB Index

```bash
.venv\Scripts\python index.py
```

- Reads all `dataset/output/*.json`
- Merges enrichment sidecars from `dataset/enriched/` (if present)
- Builds/updates `dataset/chroma/`
- Uses local sentence-transformers — no internet needed after the model is cached
- **The embedding model (~90 MB) downloads once from HuggingFace on first use.** Ensure this completes on Machine 1 before copying to USB (see Phase E).

Estimated runtime: 30–60 min for the full corpus.

---

## Phase C — Test Enrichment with Anthropic on Machine 1

Target: enrich 200–500 datasets to verify the pipeline end-to-end before transfer.

### C1. Configure `.env` for Anthropic

```
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-...
```

### C2. Run enrichment

```bash
.venv\Scripts\python enrich.py --all --workers 4 --provider anthropic
```

- Skips the 388 already enriched
- Deduplication: datasets sharing identical `technology_description` text share one API call (cheaper)
- Press Ctrl+C to stop when enough are done — completed sidecars and the dedup cache persist
- Re-running is safe (idempotent)

### C3. Re-index to pick up new summaries

```bash
.venv\Scripts\python index.py
```

---

## Phase D — Test the Web Viewer on Machine 1

```bash
.venv\Scripts\python viewer/app.py
```

Browse to `http://localhost:5000`

Verify:
- Dataset list loads
- Semantic search returns results
- LLM Q&A and chat work (Anthropic via `.env`)
- Enriched datasets show the summary card on the detail page

---

## Phase E — Package for USB Transfer

### E1. Cache the sentence-transformers model

Run Phase B (index.py) first. This downloads and caches the embedding model at:

```
C:\Users\<username>\.cache\torch\sentence_transformers\
```

Copy this folder to the USB stick. On Machine 2, set before first run:

```
SENTENCE_TRANSFORMERS_HOME=<path-to-copied-model-cache>
```

Add this to `.env` on Machine 2 so the Flask app picks it up automatically.

### E2. Contents of the USB stick

| What | Source path | Est. size |
|---|---|---|
| Codebase (all `.py`, `viewer/`, `core/`, `tests/`, `requirements.txt`, `.env.example`, `README.md`, `CLAUDE.md`) | project root | ~5 MB |
| Downloaded datasets | `dataset/output/` | ~4–5 GB |
| ChromaDB index | `dataset/chroma/` | ~500–700 MB |
| Enrichment sidecars | `dataset/enriched/` | ~10–50 MB |
| Dedup cache | `dataset/dedup/` | <1 MB |
| XLS manifest | `dataset/input/` | <1 MB |
| Sentence-transformers model cache | `C:\Users\<username>\.cache\torch\sentence_transformers\` | ~90 MB |

**Do NOT copy:** `.venv/` (recreate on Machine 2), `.git/` (not needed)

**Minimum USB size: 16 GB**

---

## Phase F — Machine 2 Setup

### F1. Install Python 3.12

From python.org (one-time internet download, can be done before receiving the USB stick).

### F2. Create venv and install dependencies

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

This is the only step requiring internet on Machine 2. All packages install from PyPI.

### F3. Configure `.env` for VIO

Copy `.env.example` → `.env`, then fill in:

```
LLM_PROVIDER=vio
LLM_MODEL=Default
API_TOKEN=<your VIO token>
VIO_BASE_URL=https://vio.automotive-wan.com:446
VIO_TENANT_ID=default_tenant

# Point at the copied model cache so no HuggingFace download is needed:
SENTENCE_TRANSFORMERS_HOME=C:\path\to\copied\sentence_transformers\cache
```

### F4. Start the web viewer

```bash
.venv\Scripts\python viewer/app.py
```

Browse to `http://localhost:5000` — loads all datasets from the USB-transferred `dataset/` folders.

### F5. Continue enrichment with VIO

```bash
.venv\Scripts\python enrich.py --all --workers 4 --provider vio
```

Skips datasets already enriched on Machine 1. Run repeatedly until complete.

### F6. Re-index after each enrichment session

```bash
.venv\Scripts\python index.py
```

Run this after any enrichment session so that newly enriched summaries appear in semantic search.

---

## Internet Access Summary

| Step | Machine | Internet required |
|---|---|---|
| Download datasets from Sphera | Machine 1 | Yes (portal + session cookie) |
| Anthropic test enrichment | Machine 1 | Yes (Anthropic API) |
| `pip install -r requirements.txt` | Machine 2 | Yes (one-time) |
| VIO enrichment | Machine 2 | Yes (VIO API only) |
| Embedding / indexing | Both | No (local model after cache is copied) |
| Web viewer | Both | No |

---

## Execution Checklist

### Machine 1
- [ ] A1 — Refresh `cookie.txt`
- [ ] A2 — Run `download.py --xls` (all 19,644 datasets)
- [ ] A3 — Retry any failed downloads
- [ ] B  — Run `index.py` (full index + caches embedding model)
- [ ] C1 — Set Anthropic key in `.env`
- [ ] C2 — Run `enrich.py --all` (stop after 200–500 new enrichments)
- [ ] C3 — Re-run `index.py`
- [ ] D  — Verify web viewer at localhost:5000
- [ ] E1 — Locate and copy sentence-transformers cache
- [ ] E2 — Copy all items to USB stick

### Machine 2
- [ ] F1 — Install Python 3.12
- [ ] F2 — Create venv + `pip install -r requirements.txt`
- [ ] F3 — Create `.env` with VIO credentials + `SENTENCE_TRANSFORMERS_HOME`
- [ ] F4 — Verify web viewer at localhost:5000
- [ ] F5 — Run `enrich.py --all --provider vio`
- [ ] F6 — Re-run `index.py` after enrichment
