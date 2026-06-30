# Machine 1 → Machine 2 Transfer Plan

**Date:** 2026-06-30  
**Goal:** Download the complete Sphera dataset corpus on Machine 1, test enrichment and the
web viewer locally, then transfer the gitignored data files to Machine 2 (company environment,
restricted internet) for VIO-based enrichment and ongoing viewer use.

**Machine 2 setup assumed:** Python environment installed, repo cloned/pulled from git,
`pip install -r requirements.txt` already done.

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

- Reads all `dataset/output/*.json`, merges any enrichment sidecars
- Builds/updates `dataset/chroma/`
- On first run, downloads the ChromaDB ONNX embedding model (~80 MB) to:
  `C:\Users\Andre\.cache\chroma\onnx_models\`  
  **Run this on Machine 1 before copying to USB** so the cache is populated.

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
- Press Ctrl+C to stop when enough are done — completed sidecars and dedup cache persist
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

Browse to `http://localhost:5000` and verify:
- Dataset list loads
- Semantic search returns results
- LLM Q&A and chat work (Anthropic via `.env`)
- Enriched datasets show the summary card on the detail page

---

## Phase E — USB Transfer to Machine 2

### E1. What to copy to the USB stick

These are all gitignored — everything else comes from the repo.

| What | Source path on Machine 1 | Est. size |
|---|---|---|
| Downloaded datasets | `dataset/output/` | ~4–5 GB |
| ChromaDB index | `dataset/chroma/` | ~500–700 MB |
| Enrichment sidecars | `dataset/enriched/` | ~10–50 MB |
| Dedup cache | `dataset/dedup/` | <1 MB |
| XLS manifest | `dataset/input/Sphera-Dataset-List-MLC-Databases-2026.1-Edition.xlsx` | <1 MB |
| ChromaDB ONNX model cache | `C:\Users\Andre\.cache\chroma\onnx_models\` | ~80 MB |

**Minimum USB size: 16 GB**

> The `.env` file with VIO credentials is also gitignored. Either copy it from Machine 1
> or create a fresh one on Machine 2 from `.env.example`.

### E2. What Machine 2 gets from the repo (nothing to copy)

- All Python source code (`core/`, `viewer/`, `*.py`)
- `requirements.txt`, `.env.example`, `README.md`, `CLAUDE.md`
- `dataset/input/*.txt` (URL lists, if any)

---

## Phase F — Machine 2 Setup

### F1. Clone/pull the repo and install dependencies

```bash
git clone <repo-url>   # or git pull if already cloned
cd Sphera-Data-Sets
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

> If PyPI is blocked: run `pip download -r requirements.txt -d usb_packages/` on Machine 1
> first, copy `usb_packages/` to the USB stick, then on Machine 2 use:
> `.venv\Scripts\pip install --no-index --find-links usb_packages/ -r requirements.txt`
> The full download is ~115 wheel files / 253 MB.

### F2. Copy USB data into the project folder

Place the USB contents into the matching paths:

```
usb:\dataset\output\        →  <project>\dataset\output\
usb:\dataset\chroma\        →  <project>\dataset\chroma\
usb:\dataset\enriched\      →  <project>\dataset\enriched\
usb:\dataset\dedup\         →  <project>\dataset\dedup\
usb:\Sphera-Dataset-List-MLC-Databases-2026.1-Edition.xlsx  →  <project>\dataset\input\
```

### F3. Copy the ChromaDB ONNX model cache

```
usb:\onnx_models\   →   C:\Users\<username>\.cache\chroma\onnx_models\
```

Create `C:\Users\<username>\.cache\chroma\` first if it does not exist.
ChromaDB finds the model automatically — no env var needed.

### F4. Configure `.env` for VIO

Copy `.env.example` → `.env`, then fill in:

```
LLM_PROVIDER=vio
LLM_MODEL=Default
API_TOKEN=<your VIO token>
VIO_BASE_URL=https://vio.automotive-wan.com:446
VIO_TENANT_ID=default_tenant
```

### F5. Start the web viewer

```bash
.venv\Scripts\python viewer/app.py
```

Browse to `http://localhost:5000` — all datasets load from the copied `dataset/` folders.

### F6. Continue enrichment with VIO

```bash
.venv\Scripts\python enrich.py --all --workers 4 --provider vio
```

Skips datasets already enriched on Machine 1. Only `vio.automotive-wan.com` needs to be
reachable — no other internet access required.

### F7. Re-index after each enrichment session

```bash
.venv\Scripts\python index.py
```

---

## Internet Access Summary

| Step | Machine | Internet required |
|---|---|---|
| Download datasets from Sphera | Machine 1 | Yes — Sphera portal + session cookie |
| Anthropic test enrichment | Machine 1 | Yes — Anthropic API |
| `pip install -r requirements.txt` | Machine 2 | Yes — PyPI (fallback: wheels on USB) |
| ChromaDB ONNX model | Machine 2 | **No** — cache copied from Machine 1 |
| Embedding / indexing | Machine 2 | **No** — local ONNX model |
| Web viewer | Machine 2 | **No** |
| VIO enrichment | Machine 2 | Yes — VIO API only (`vio.automotive-wan.com`) |

---

## Execution Checklist

### Machine 1
- [x] A1 — Refresh `cookie.txt`
- [ ] A2 — Run `download.py --xls` (all 19,644 datasets)
- [ ] A3 — Retry any failed downloads
- [ ] B  — Run `index.py` (full index + populates ONNX model cache)
- [x] C1 — Set Anthropic key in `.env`
- [ ] C2 — Run `enrich.py --all` (stop after 200–500 new enrichments)
- [ ] C3 — Re-run `index.py`
- [ ] D  — Verify web viewer at localhost:5000
- [ ] E1 — Copy all listed items to USB stick

### Machine 2
- [ ] F1 — Clone/pull repo + `pip install -r requirements.txt`
- [ ] F2 — Copy USB data into `dataset/` folder
- [ ] F3 — Copy ONNX cache to `C:\Users\<username>\.cache\chroma\onnx_models\`
- [ ] F4 — Create `.env` with VIO credentials
- [ ] F5 — Verify web viewer at localhost:5000
- [ ] F6 — Run `enrich.py --all --provider vio`
- [ ] F7 — Re-run `index.py` after enrichment
