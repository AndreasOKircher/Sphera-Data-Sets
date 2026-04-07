# Sphera Dataset New Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Sphera LCA dataset pipeline with XLS-driven metadata ingestion (Step A), ChromaDB vector search with RAG (Step B), and conversational follow-up Q&A in the viewer (Step C).

**Architecture:** New fields (`source_url`, `xls_dataset_type`, `databases`) are merged into the existing output JSON at download time from the XLS manifest. A separate ChromaDB index is built from those JSON files via a new `index.py` CLI. The viewer gains a `/search` endpoint (RAG + metadata filter) and a multi-turn `/chat` endpoint; `enrich.py` is unchanged.

**Tech Stack:** Python 3.11+, Flask, openpyxl, chromadb, sentence-transformers (local embeddings), existing LLM abstraction (`core/llm.py`).

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `core/xls_manifest.py` | **New** | Load XLS → `dict[uuid, ManifestEntry]`; filter by database name |
| `core/chroma_store.py` | **New** | ChromaDB wrapper: build index, similarity search, metadata filters |
| `index.py` | **New** | CLI: build/update ChromaDB index from dataset/output + dataset/enriched |
| `download.py` | **Modify** | Add `--xls` / `--databases` mode; inject manifest fields before export |
| `viewer/app.py` | **Modify** | Add `/search` (RAG) and `/chat` (multi-turn) endpoints |
| `viewer/query.py` | **Modify** | Add `history` parameter to `run_query` for multi-turn support |
| `viewer/sections.py` | **Modify** | Add "Catalogue" section with `source_url`, `xls_dataset_type`, `databases` |
| `viewer/templates/dataset.html` | **Modify** | Show new catalogue fields |
| `viewer/templates/index.html` | **Modify** | Add filter dropdowns + search box + chat panel |
| `requirements.txt` | **Modify** | Add `openpyxl`, `chromadb`, `sentence-transformers` |
| `tests/test_xls_manifest.py` | **New** | Unit tests for manifest loader |
| `tests/test_chroma_store.py` | **New** | Unit tests for chroma store build + query |
| `tests/test_query_history.py` | **New** | Unit tests for multi-turn query |

---

## Step A — XLS Manifest + New Fields

### Task 1: core/xls_manifest.py — XLS manifest loader

**Files:**
- Create: `core/xls_manifest.py`
- Create: `tests/test_xls_manifest.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_xls_manifest.py
import pytest
from unittest.mock import patch, MagicMock
from core.xls_manifest import load_manifest, get_uuids_for_databases, ManifestEntry

FAKE_ROWS = [
    # header row handled by openpyxl iter_rows(min_row=2)
    ("aaa-111", "https://example.com/aaa", "Unit process", "Professional database 2026"),
    ("bbb-222", "https://example.com/bbb", "Aggregated process", "Extension database XI: electronics 2026"),
    ("ccc-333", "https://example.com/ccc", "Unit process", "Professional database 2026\nExtension database XI: electronics 2026"),
]


def _make_ws(rows):
    ws = MagicMock()
    ws.iter_rows.return_value = [
        [MagicMock(value=v) for v in row] for row in rows
    ]
    return ws


def test_load_manifest_returns_dict_keyed_by_uuid():
    ws = _make_ws(FAKE_ROWS)
    with patch("core.xls_manifest.openpyxl.load_workbook") as mock_wb:
        mock_wb.return_value.active = ws
        result = load_manifest("fake.xlsx")
    assert "aaa-111" in result
    assert isinstance(result["aaa-111"], ManifestEntry)


def test_load_manifest_parses_fields():
    ws = _make_ws(FAKE_ROWS)
    with patch("core.xls_manifest.openpyxl.load_workbook") as mock_wb:
        mock_wb.return_value.active = ws
        result = load_manifest("fake.xlsx")
    entry = result["aaa-111"]
    assert entry.source_url == "https://example.com/aaa"
    assert entry.xls_dataset_type == "Unit process"
    assert "Professional database 2026" in entry.databases


def test_load_manifest_splits_multi_database_cell():
    ws = _make_ws(FAKE_ROWS)
    with patch("core.xls_manifest.openpyxl.load_workbook") as mock_wb:
        mock_wb.return_value.active = ws
        result = load_manifest("fake.xlsx")
    assert len(result["ccc-333"].databases) == 2


def test_get_uuids_for_databases_filters_correctly():
    ws = _make_ws(FAKE_ROWS)
    with patch("core.xls_manifest.openpyxl.load_workbook") as mock_wb:
        mock_wb.return_value.active = ws
        manifest = load_manifest("fake.xlsx")
    uuids = get_uuids_for_databases(manifest, ["Professional database 2026"])
    assert "aaa-111" in uuids
    assert "bbb-222" not in uuids
    assert "ccc-333" in uuids  # has both databases


def test_load_manifest_skips_rows_with_no_guid():
    rows_with_blank = [("", "https://x.com", "Unit process", "Professional database 2026")]
    ws = _make_ws(rows_with_blank)
    with patch("core.xls_manifest.openpyxl.load_workbook") as mock_wb:
        mock_wb.return_value.active = ws
        result = load_manifest("fake.xlsx")
    assert len(result) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_xls_manifest.py -v
```
Expected: `ModuleNotFoundError: No module named 'core.xls_manifest'`

- [ ] **Step 3: Implement core/xls_manifest.py**

```python
# core/xls_manifest.py
from __future__ import annotations
from dataclasses import dataclass, field
import openpyxl


@dataclass
class ManifestEntry:
    uuid: str
    source_url: str
    xls_dataset_type: str
    databases: list[str]


# Column indices (0-based) in the XLS sheet
_COL_GUID = 0
_COL_URL = 1
_COL_TYPE = 2
_COL_DBS = 3


def load_manifest(xls_path: str) -> dict[str, ManifestEntry]:
    """Load the Sphera XLS manifest and return a dict keyed by GUID.

    Skips rows where GUID cell is blank.
    Multi-database cells are split on newline.
    """
    wb = openpyxl.load_workbook(xls_path, read_only=True, data_only=True)
    ws = wb.active
    result: dict[str, ManifestEntry] = {}

    for row in ws.iter_rows(min_row=2, values_only=False):
        def _cell(idx: int) -> str:
            v = row[idx].value if idx < len(row) else None
            return str(v).strip() if v is not None else ""

        guid = _cell(_COL_GUID)
        if not guid:
            continue

        raw_dbs = _cell(_COL_DBS)
        databases = [db.strip() for db in raw_dbs.splitlines() if db.strip()]

        result[guid] = ManifestEntry(
            uuid=guid,
            source_url=_cell(_COL_URL),
            xls_dataset_type=_cell(_COL_TYPE),
            databases=databases,
        )

    wb.close()
    return result


def get_uuids_for_databases(
    manifest: dict[str, ManifestEntry],
    db_names: list[str],
) -> list[str]:
    """Return UUIDs whose databases list overlaps with db_names."""
    target = set(db_names)
    return [
        entry.uuid
        for entry in manifest.values()
        if target.intersection(entry.databases)
    ]
```

- [ ] **Step 4: Install openpyxl, run tests to verify they pass**

```bash
pip install openpyxl
python -m pytest tests/test_xls_manifest.py -v
```
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/xls_manifest.py tests/test_xls_manifest.py
git commit -m "feat: add XLS manifest loader (core/xls_manifest.py)"
```

---

### Task 2: Extend download.py with --xls mode

**Files:**
- Modify: `download.py`

> Note: `export_dataset()` in `core/exporter.py` writes whatever dict it receives — no changes needed there.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_download_xls.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from core.xls_manifest import ManifestEntry


MANIFEST = {
    "aaa-111": ManifestEntry(
        uuid="aaa-111",
        source_url="https://example.com/aaa",
        xls_dataset_type="Unit process",
        databases=["Professional database 2026"],
    )
}


def test_process_url_from_manifest_merges_fields(tmp_path):
    """process_url_from_manifest injects source_url, xls_dataset_type, databases into exported JSON."""
    fake_xml = b"<xml/>"
    fake_data = {"uuid": "aaa-111", "name_base": "Test", "technology_description": ""}

    with patch("download.download_xml", return_value=fake_xml), \
         patch("download.parse_dataset", return_value=fake_data), \
         patch("download.export_dataset") as mock_export:

        from download import process_url_from_manifest
        entry = MANIFEST["aaa-111"]
        process_url_from_manifest(entry, tmp_path)

        args = mock_export.call_args[0]
        exported_data = args[0]
        assert exported_data["source_url"] == "https://example.com/aaa"
        assert exported_data["xls_dataset_type"] == "Unit process"
        assert exported_data["databases"] == ["Professional database 2026"]


def test_process_url_from_manifest_skips_existing(tmp_path):
    """Skips download if <uuid>.json already exists in output_dir."""
    existing = tmp_path / "aaa-111.json"
    existing.write_text("{}")

    with patch("download.download_xml") as mock_dl:
        from download import process_url_from_manifest
        entry = MANIFEST["aaa-111"]
        result = process_url_from_manifest(entry, tmp_path)
        mock_dl.assert_not_called()
        assert result == "skip"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_download_xls.py -v
```
Expected: `ImportError: cannot import name 'process_url_from_manifest' from 'download'`

- [ ] **Step 3: Add process_url_from_manifest and --xls CLI mode to download.py**

Add this function after the existing `process_url()`:

```python
# In download.py — add after process_url()

from core.xls_manifest import load_manifest, get_uuids_for_databases, ManifestEntry


def process_url_from_manifest(
    entry: ManifestEntry,
    output_dir: Path,
    headers: dict | None = None,
) -> str:
    """Download and export one manifest entry. Returns 'ok', 'skip', or 'fail'."""
    json_path = output_dir / f"{entry.uuid}.json"
    if json_path.exists():
        print(f"[SKIP] {entry.uuid} — already exists")
        return "skip"
    try:
        xml_bytes = download_xml(entry.source_url, headers=headers)
        data = parse_dataset(xml_bytes)
        # Inject manifest-sourced fields into the data model
        data["source_url"] = entry.source_url
        data["xls_dataset_type"] = entry.xls_dataset_type
        data["databases"] = entry.databases
        export_dataset(data, xml_bytes, output_dir)
        print(f"[OK]   {entry.uuid} — {data.get('name_base', '')}")
        return "ok"
    except DownloadError as e:
        print(f"[FAIL] {entry.uuid} — {e}", file=sys.stderr)
        return "fail"
    except Exception as e:
        print(f"[FAIL] {entry.uuid} — unexpected error: {e}", file=sys.stderr)
        return "fail"
```

In `main()`, extend the argument parser (add to the existing mutually exclusive group):

```python
    group.add_argument("--xls", help="Path to Sphera XLS manifest file")
    parser.add_argument(
        "--databases",
        nargs="+",
        default=None,
        help='Filter to specific databases (e.g. "Professional database 2026")',
    )
```

Add an `--xls` branch at the end of `main()` before the existing URL loop:

```python
    if args.xls:
        manifest = load_manifest(args.xls)
        if args.databases:
            uuids = get_uuids_for_databases(manifest, args.databases)
            entries = [manifest[u] for u in uuids if u in manifest]
        else:
            entries = list(manifest.values())

        counts = {"ok": 0, "skip": 0, "fail": 0}
        for entry in entries:
            result = process_url_from_manifest(entry, output_dir, headers=headers)
            counts[result] += 1

        print(f"\nDone. {counts['ok']} ok · {counts['skip']} skipped · {counts['fail']} failed.")
        if counts["fail"]:
            sys.exit(1)
        return
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_download_xls.py -v
```
Expected: 2 tests PASS

- [ ] **Step 5: Smoke-test with the real XLS (no download — just manifest loading)**

```bash
python download.py --xls dataset/input/Sphera-Dataset-List-MLC-Databases-2026.1-Edition.xlsx \
    --databases "Professional database 2026" --output /tmp/smoke_test 2>&1 | head -5
```
Expected: lines like `[OK] <uuid>` or `[SKIP]` — no Python traceback.

- [ ] **Step 6: Commit**

```bash
git add download.py tests/test_download_xls.py
git commit -m "feat: add --xls / --databases mode to download.py; inject manifest fields into JSON"
```

---

### Task 3: Viewer — show new catalogue fields

**Files:**
- Modify: `viewer/sections.py`
- Modify: `viewer/templates/dataset.html`
- Modify: `viewer/templates/index.html`

- [ ] **Step 1: Add "Catalogue" section to viewer/sections.py**

Open `viewer/sections.py` and append to `SECTIONS`:

```python
    ("Catalogue", [
        "source_url", "xls_dataset_type", "databases",
    ]),
```

- [ ] **Step 2: Verify the sections list is correct**

```bash
python -c "from viewer.sections import SECTIONS; [print(s[0]) for s in SECTIONS]"
```
Expected output ends with `Catalogue`.

- [ ] **Step 3: Show new fields in dataset detail view**

In `viewer/templates/dataset.html`, find the section that iterates over fields and renders values. The three new fields need a custom renderer because:
- `source_url` should be a clickable `<a>` tag
- `databases` is a list and should render as bullet items

Add a Jinja2 block before or after existing field rendering. Find the loop that renders field values (it uses `data[field]`) and add special-case rendering:

```html
{# In the field rendering loop in dataset.html #}
{% if field == "source_url" and data[field] %}
  <a href="{{ data[field] }}" target="_blank" rel="noopener">{{ data[field] }}</a>
{% elif field == "databases" and data[field] %}
  <ul class="mb-0 ps-3">
    {% for db in data[field] %}
      <li>{{ db }}</li>
    {% endfor %}
  </ul>
{% else %}
  {{ data.get(field, "") }}
{% endif %}
```

- [ ] **Step 4: Add xls_dataset_type column to index.html dataset list**

In `viewer/templates/index.html`, in the table `<thead>`, add after the existing Type column (or after Name if no Type column exists):

```html
<th>DB Type</th>
```

In the table `<tbody>` row loop, add:

```html
<td>{{ d.get("xls_dataset_type", "") }}</td>
```

- [ ] **Step 5: Manual verification**

```bash
python -m flask --app viewer/app.py run --debug
```
Open `http://localhost:5000` — confirm the new "DB Type" column appears.
Open any dataset detail — confirm "Catalogue" section appears (may be empty for existing datasets without manifest fields).

- [ ] **Step 6: Commit**

```bash
git add viewer/sections.py viewer/templates/dataset.html viewer/templates/index.html
git commit -m "feat: show xls_dataset_type, source_url, databases in viewer"
```

---

## Step B — ChromaDB Vector Search + RAG

### Task 4: Install dependencies and scaffold core/chroma_store.py

**Files:**
- Create: `core/chroma_store.py`
- Create: `tests/test_chroma_store.py`

- [ ] **Step 1: Install dependencies**

```bash
pip install chromadb sentence-transformers
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_chroma_store.py
import json
import pytest
from pathlib import Path


@pytest.fixture
def sample_datasets(tmp_path):
    """Write two minimal dataset JSON files to tmp_path."""
    d1 = {
        "uuid": "uuid-001",
        "name_base": "Steel sheet",
        "technology_description": "Production of cold-rolled steel sheet using electric arc furnace.",
        "xls_dataset_type": "Unit process",
        "databases": ["Professional database 2026"],
        "location": "DE",
        "classification": "Metals",
    }
    d2 = {
        "uuid": "uuid-002",
        "name_base": "Aluminium ingot",
        "technology_description": "Production of secondary aluminium ingot from post-consumer scrap.",
        "xls_dataset_type": "Unit process",
        "databases": ["Extension database XI: electronics 2026"],
        "location": "GLO",
        "classification": "Metals",
    }
    (tmp_path / "uuid-001.json").write_text(json.dumps(d1))
    (tmp_path / "uuid-002.json").write_text(json.dumps(d2))
    return tmp_path


def test_build_index_creates_collection(sample_datasets, tmp_path):
    from core.chroma_store import build_index, get_client
    chroma_path = tmp_path / "chroma"
    build_index(sample_datasets, enriched_dir=None, chroma_path=chroma_path)
    client = get_client(chroma_path)
    col = client.get_collection("sphera_datasets")
    assert col.count() == 2


def test_query_similar_returns_results(sample_datasets, tmp_path):
    from core.chroma_store import build_index, query_similar
    chroma_path = tmp_path / "chroma"
    build_index(sample_datasets, enriched_dir=None, chroma_path=chroma_path)
    results = query_similar("aluminium recycling scrap", chroma_path=chroma_path, n_results=2)
    assert len(results) >= 1
    uuids = [r["uuid"] for r in results]
    assert "uuid-002" in uuids  # aluminium dataset should rank first


def test_query_similar_with_metadata_filter(sample_datasets, tmp_path):
    from core.chroma_store import build_index, query_similar
    chroma_path = tmp_path / "chroma"
    build_index(sample_datasets, enriched_dir=None, chroma_path=chroma_path)
    results = query_similar(
        "metal production",
        chroma_path=chroma_path,
        n_results=5,
        where={"xls_dataset_type": "Unit process"},
    )
    assert all(r["xls_dataset_type"] == "Unit process" for r in results)


def test_build_index_is_idempotent(sample_datasets, tmp_path):
    from core.chroma_store import build_index, get_client
    chroma_path = tmp_path / "chroma"
    build_index(sample_datasets, enriched_dir=None, chroma_path=chroma_path)
    build_index(sample_datasets, enriched_dir=None, chroma_path=chroma_path)
    client = get_client(chroma_path)
    col = client.get_collection("sphera_datasets")
    assert col.count() == 2  # no duplicates
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python -m pytest tests/test_chroma_store.py -v
```
Expected: `ModuleNotFoundError: No module named 'core.chroma_store'`

- [ ] **Step 4: Implement core/chroma_store.py**

```python
# core/chroma_store.py
from __future__ import annotations
import json
from pathlib import Path
import chromadb

COLLECTION_NAME = "sphera_datasets"


def get_client(chroma_path: Path) -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(chroma_path))


def _text_for_embedding(data: dict, enriched: dict) -> str:
    """Prefer enriched formatted description; fall back to raw technology_description."""
    text = enriched.get("technology_description_formatted") or \
           data.get("technology_description") or \
           data.get("name_base") or ""
    return text[:8000]  # ChromaDB default model has a token limit


def build_index(
    output_dir: Path,
    enriched_dir: Path | None,
    chroma_path: Path,
) -> None:
    """Build or update ChromaDB index from dataset/output JSON files.

    Uses upsert so re-running is safe (idempotent by uuid).
    """
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = get_client(chroma_path)

    try:
        col = client.get_collection(COLLECTION_NAME)
    except Exception:
        col = client.create_collection(
            COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    ids, documents, metadatas = [], [], []

    for json_file in sorted(Path(output_dir).glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        uuid = data.get("uuid")
        if not uuid:
            continue

        enriched: dict = {}
        if enriched_dir:
            ep = Path(enriched_dir) / f"{uuid}.json"
            if ep.exists():
                try:
                    enriched = json.loads(ep.read_text(encoding="utf-8"))
                except Exception:
                    pass

        text = _text_for_embedding(data, enriched)
        if not text:
            continue

        # Metadata must be flat scalars for ChromaDB
        databases = data.get("databases") or []
        meta = {
            "uuid": uuid,
            "name_base": data.get("name_base") or "",
            "xls_dataset_type": data.get("xls_dataset_type") or "",
            "location": data.get("location") or "",
            "classification": data.get("classification") or "",
            # Store as newline-joined string — ChromaDB doesn't support list metadata
            "databases": "\n".join(databases),
        }

        ids.append(uuid)
        documents.append(text)
        metadatas.append(meta)

    if ids:
        col.upsert(ids=ids, documents=documents, metadatas=metadatas)
        print(f"[INDEX] Upserted {len(ids)} datasets into ChromaDB at {chroma_path}")
    else:
        print("[INDEX] No datasets found to index.")


def query_similar(
    question: str,
    chroma_path: Path,
    n_results: int = 20,
    where: dict | None = None,
) -> list[dict]:
    """Similarity search. Returns list of metadata dicts with 'uuid' key.

    Parameters
    ----------
    where : ChromaDB metadata filter dict, e.g. {"xls_dataset_type": "Unit process"}
    """
    client = get_client(chroma_path)
    try:
        col = client.get_collection(COLLECTION_NAME)
    except Exception:
        return []

    kwargs: dict = {"query_texts": [question], "n_results": min(n_results, col.count())}
    if where:
        kwargs["where"] = where

    results = col.query(**kwargs)
    metadatas = results.get("metadatas", [[]])[0]

    # Restore databases list from newline-joined string
    for m in metadatas:
        raw = m.get("databases", "")
        m["databases"] = [db for db in raw.splitlines() if db]

    return metadatas
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_chroma_store.py -v
```
Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add core/chroma_store.py tests/test_chroma_store.py
git commit -m "feat: add ChromaDB store (core/chroma_store.py) with build_index and query_similar"
```

---

### Task 5: index.py — CLI to build the ChromaDB index

**Files:**
- Create: `index.py`

- [ ] **Step 1: Write the file**

```python
# index.py
"""CLI to build or update the ChromaDB vector index from dataset/output JSON files."""

import argparse
from pathlib import Path
from core.chroma_store import build_index

DEFAULT_OUTPUT   = Path("dataset/output")
DEFAULT_ENRICHED = Path("dataset/enriched")
DEFAULT_CHROMA   = Path("dataset/chroma")


def main():
    parser = argparse.ArgumentParser(
        description="Build or update ChromaDB index from Sphera LCA datasets."
    )
    parser.add_argument("--output",   default=str(DEFAULT_OUTPUT),   help="dataset/output directory")
    parser.add_argument("--enriched", default=str(DEFAULT_ENRICHED), help="dataset/enriched directory")
    parser.add_argument("--db",       default=str(DEFAULT_CHROMA),   help="ChromaDB persistence directory")
    args = parser.parse_args()

    output_dir   = Path(args.output)
    enriched_dir = Path(args.enriched) if Path(args.enriched).exists() else None
    chroma_path  = Path(args.db)

    if not output_dir.exists():
        print(f"[ERROR] Output directory not found: {output_dir}")
        raise SystemExit(1)

    build_index(output_dir, enriched_dir, chroma_path)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test**

```bash
python index.py --output dataset/output --enriched dataset/enriched --db dataset/chroma
```
Expected: `[INDEX] Upserted N datasets into ChromaDB at dataset/chroma` with no traceback.

- [ ] **Step 3: Commit**

```bash
git add index.py
git commit -m "feat: add index.py CLI to build ChromaDB index"
```

---

### Task 6: Viewer — /search endpoint (RAG + metadata filters)

**Files:**
- Modify: `viewer/app.py`
- Modify: `viewer/templates/index.html`

- [ ] **Step 1: Write failing test**

```python
# tests/test_search_endpoint.py
import json
import pytest
from unittest.mock import patch


@pytest.fixture
def client(tmp_path):
    import viewer.app as app_module
    app_module.app.config["TESTING"] = True
    app_module.OUTPUT_DIR = tmp_path
    app_module.ENRICHED_DIR = tmp_path
    return app_module.app.test_client()


def test_search_endpoint_returns_uuids(client):
    fake_results = [{"uuid": "aaa-111", "name_base": "Steel", "xls_dataset_type": "Unit process",
                     "location": "DE", "classification": "Metals", "databases": []}]
    with patch("viewer.app.query_similar", return_value=fake_results):
        resp = client.post("/search", json={"question": "steel production"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "uuids" in data
    assert "aaa-111" in data["uuids"]


def test_search_endpoint_requires_question(client):
    resp = client.post("/search", json={})
    assert resp.status_code == 400


def test_search_endpoint_applies_where_filter(client):
    fake_results = []
    with patch("viewer.app.query_similar", return_value=fake_results) as mock_qs:
        client.post("/search", json={
            "question": "aluminium",
            "filters": {"xls_dataset_type": "Unit process"},
        })
        call_kwargs = mock_qs.call_args[1]
        assert call_kwargs["where"] == {"xls_dataset_type": "Unit process"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_search_endpoint.py -v
```
Expected: `404` on `/search` or import error.

- [ ] **Step 3: Add /search endpoint to viewer/app.py**

Add these imports near the top of `viewer/app.py`:

```python
from pathlib import Path
CHROMA_DIR = _BASE / "dataset" / "chroma"
```

Add the endpoint:

```python
@app.route("/search", methods=["POST"])
def search():
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    filters = body.get("filters") or None

    from core.chroma_store import query_similar
    results = query_similar(
        question,
        chroma_path=CHROMA_DIR,
        n_results=20,
        where=filters,
    )
    uuids = [r["uuid"] for r in results]
    return jsonify({"uuids": uuids, "matches": results})
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_search_endpoint.py -v
```
Expected: 3 tests PASS

- [ ] **Step 5: Add search UI to index.html**

In `viewer/templates/index.html`, add a search form above the dataset table:

```html
<div class="card mb-3">
  <div class="card-body">
    <h6 class="card-title">Semantic Search</h6>
    <div class="input-group">
      <input id="search-input" type="text" class="form-control"
             placeholder="e.g. aluminium with post-consumer recycling content">
      <button class="btn btn-primary" onclick="doSearch()">Search</button>
    </div>
    <div class="mt-2">
      <select id="filter-type" class="form-select form-select-sm d-inline-block w-auto me-2">
        <option value="">All dataset types</option>
        {% for ds_type in datasets | map(attribute='xls_dataset_type') | unique | sort %}
          {% if ds_type %}<option value="{{ ds_type }}">{{ ds_type }}</option>{% endif %}
        {% endfor %}
      </select>
    </div>
    <div id="search-results" class="mt-2 text-muted small"></div>
  </div>
</div>

<script>
async function doSearch() {
  const question = document.getElementById("search-input").value.trim();
  if (!question) return;
  const dsType = document.getElementById("filter-type").value;
  const body = { question };
  if (dsType) body.filters = { xls_dataset_type: dsType };

  document.getElementById("search-results").textContent = "Searching…";
  const resp = await fetch("/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (data.error) {
    document.getElementById("search-results").textContent = "Error: " + data.error;
    return;
  }
  const uuids = new Set(data.uuids);
  // Highlight matching rows
  document.querySelectorAll("tbody tr").forEach(row => {
    const rowUuid = row.dataset.uuid;
    row.style.background = uuids.has(rowUuid) ? "#fffde7" : "";
  });
  document.getElementById("search-results").textContent =
    `${data.uuids.length} matching datasets highlighted.`;
}
</script>
```

Also add `data-uuid="{{ d.uuid }}"` to each `<tr>` in the dataset table body.

- [ ] **Step 6: Commit**

```bash
git add viewer/app.py viewer/templates/index.html tests/test_search_endpoint.py
git commit -m "feat: add /search RAG endpoint and semantic search UI"
```

---

## Step C — Multi-turn Conversational Q&A

### Task 7: Extend viewer/query.py with conversation history

**Files:**
- Modify: `viewer/query.py`
- Create: `tests/test_query_history.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_query_history.py
from unittest.mock import MagicMock
from viewer.query import build_prompt, run_query


def test_build_prompt_includes_history():
    history = [
        {"role": "user", "content": "What is steel?"},
        {"role": "assistant", "content": "Steel is an alloy of iron."},
    ]
    datasets = [{"uuid": "x", "name_base": "Steel", "technology_description": "desc"}]
    prompt = build_prompt("tell me more", datasets, history=history)
    assert "What is steel?" in prompt
    assert "Steel is an alloy of iron." in prompt


def test_build_prompt_no_history_unchanged():
    datasets = [{"uuid": "x", "name_base": "Steel", "technology_description": "desc"}]
    prompt_no_history = build_prompt("question", datasets)
    prompt_empty_history = build_prompt("question", datasets, history=[])
    assert prompt_no_history == prompt_empty_history


def test_run_query_passes_history_to_client():
    mock_client = MagicMock()
    mock_client.complete.return_value = "[]"
    history = [{"role": "user", "content": "prior question"},
               {"role": "assistant", "content": "prior answer"}]
    datasets = [{"uuid": "x", "name_base": "Test", "technology_description": "some text"}]
    run_query("follow-up", datasets, client=mock_client, history=history)
    call_args = mock_client.complete.call_args
    # The user message passed to the LLM should contain history
    user_message = call_args[0][1]
    assert "prior question" in user_message
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_query_history.py -v
```
Expected: `TypeError: build_prompt() got an unexpected keyword argument 'history'`

- [ ] **Step 3: Add history parameter to build_prompt and run_query**

In `viewer/query.py`, modify `build_prompt`:

```python
def build_prompt(
    question: str,
    datasets: list[dict],
    fields: list[str] | None = None,
    history: list[dict] | None = None,
) -> str:
    """Build the user message for the LLM query.

    history : list of {"role": "user"|"assistant", "content": str}
              Prior conversation turns prepended before the current question.
    """
    if fields is None:
        fields = list(_ALL_FIELDS)
    field_set = set(fields)

    lines = []

    # Prepend conversation history if provided
    if history:
        lines.append("Prior conversation:")
        for turn in history:
            role = turn.get("role", "user").capitalize()
            content = turn.get("content", "")
            lines.append(f"{role}: {content}")
        lines.append("")  # blank separator

    lines.append(f"Question: {question}\n")
    lines.append("Datasets:")

    for d in datasets:
        entry_lines = [
            "\n---",
            f"UUID: {d.get('uuid', '')}",
            f"Name: {d.get('name_base', '')}",
        ]
        if "classification" in field_set:
            entry_lines.append(f"Classification: {d.get('classification', '')}")
        if "location" in field_set:
            entry_lines.append(f"Location: {d.get('location', '')}")
        if "year" in field_set:
            entry_lines.append(f"Year: {d.get('reference_year', '')}")
        if "synonyms" in field_set and d.get("synonyms"):
            entry_lines.append(f"Synonyms: {d.get('synonyms', '')}")
        if "dataset_type" in field_set and d.get("dataset_type"):
            entry_lines.append(f"Type: {d.get('dataset_type', '')}")
        if "description" in field_set:
            desc = d.get("_summary") or (d.get("technology_description") or "")[:500]
            entry_lines.append(f"Description: {desc}")
        lines.append("\n".join(entry_lines))

    return "\n".join(lines)
```

Modify `run_query` and `run_query_with_usage` to accept and forward `history`:

```python
def run_query(
    question: str,
    datasets: list[dict],
    client: LLMClient,
    fields: list[str] | None = None,
    history: list[dict] | None = None,
) -> list[dict]:
    results, _ = run_query_with_usage(question, datasets, client=client,
                                      fields=fields, history=history)
    return results


def run_query_with_usage(
    question: str,
    datasets: list[dict],
    client: LLMClient,
    fields: list[str] | None = None,
    history: list[dict] | None = None,
) -> tuple[list[dict], dict]:
    user_message = build_prompt(question, datasets, fields=fields, history=history)
    text = client.complete(QUERY_SYSTEM, user_message, 4000)
    usage = {
        "input_tokens": 0, "output_tokens": 0,
        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
    }
    return parse_response(text), usage
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_query_history.py -v
```
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add viewer/query.py tests/test_query_history.py
git commit -m "feat: add conversation history support to run_query / build_prompt"
```

---

### Task 8: /chat endpoint + conversational UI

**Files:**
- Modify: `viewer/app.py`
- Modify: `viewer/templates/index.html`

- [ ] **Step 1: Write failing test**

```python
# tests/test_chat_endpoint.py
import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def client(tmp_path):
    import viewer.app as app_module
    app_module.app.config["TESTING"] = True
    app_module.OUTPUT_DIR = tmp_path
    app_module.ENRICHED_DIR = tmp_path
    # Provide a fake LLM client
    mock_llm = MagicMock()
    mock_llm.complete.return_value = '[{"uuid":"x","name":"X","rank":1,"relevance_score":5,"comment":"good"}]'
    app_module.app.config["LLM_CLIENT"] = mock_llm
    return app_module.app.test_client()


def test_chat_endpoint_accepts_history(client, tmp_path):
    # Write a minimal dataset JSON so load_all finds something
    (tmp_path / "x.json").write_text(json.dumps({
        "uuid": "x", "name_base": "Test", "technology_description": "some text"
    }))
    resp = client.post("/chat", json={
        "question": "follow-up question",
        "uuids": ["x"],
        "history": [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"},
        ],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "results" in data


def test_chat_endpoint_requires_question(client):
    resp = client.post("/chat", json={"uuids": ["x"]})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_chat_endpoint.py -v
```
Expected: 404 on `/chat`.

- [ ] **Step 3: Add /chat endpoint to viewer/app.py**

```python
@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()
    uuids = body.get("uuids")
    history = body.get("history") or []

    if not question:
        return jsonify({"error": "question is required"}), 400
    if not uuids:
        return jsonify({"error": "uuids is required"}), 400

    llm_client = app.config.get("LLM_CLIENT")
    if llm_client is None:
        return jsonify({"error": "LLM client not configured"}), 503

    all_datasets = load_all()
    uuid_set = set(uuids)
    selected = [d for d in all_datasets if d.get("uuid") in uuid_set]
    if not selected:
        return jsonify({"error": "No matching datasets found"}), 400

    fields = body.get("fields") or None
    try:
        from viewer.query import run_query
        results = run_query(question, selected, client=llm_client,
                            fields=fields, history=history)
        return jsonify({"results": results})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_chat_endpoint.py -v
```
Expected: 2 tests PASS

- [ ] **Step 5: Add conversational UI to index.html**

In the query section of `viewer/templates/index.html`, extend the existing query JS to maintain a chat history and send it with each request. Replace the existing `/query` fetch with `/chat`:

```html
<!-- Chat history state (add alongside existing JS) -->
<script>
let _chatHistory = [];
let _selectedUuids = [];  // populated when user checks dataset rows

async function doChat() {
  const question = document.getElementById("query-input").value.trim();
  if (!question || _selectedUuids.length === 0) return;

  // Append user turn to display
  appendChatBubble("user", question);

  const body = {
    question,
    uuids: _selectedUuids,
    history: _chatHistory,
  };

  const resp = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json();

  if (data.error) {
    appendChatBubble("assistant", "Error: " + data.error);
    return;
  }

  // Format answer from ranked results
  const answer = data.results
    .map(r => `[${r.rank}] ${r.name} (score ${r.relevance_score}/5): ${r.comment}`)
    .join("\n");
  appendChatBubble("assistant", answer);

  // Update history for next turn
  _chatHistory.push({ role: "user", content: question });
  _chatHistory.push({ role: "assistant", content: answer });

  document.getElementById("query-input").value = "";
}

function appendChatBubble(role, text) {
  const panel = document.getElementById("chat-panel");
  const div = document.createElement("div");
  div.className = role === "user" ? "text-end mb-2" : "text-start mb-2";
  div.innerHTML = `<span class="badge bg-${role === 'user' ? 'primary' : 'secondary'} text-wrap text-start"
                         style="max-width:80%;white-space:pre-wrap">${text}</span>`;
  panel.appendChild(div);
  panel.scrollTop = panel.scrollHeight;
}

function clearChat() {
  _chatHistory = [];
  document.getElementById("chat-panel").innerHTML = "";
}
</script>

<!-- Chat panel (add below the existing query controls) -->
<div id="chat-panel"
     style="height:300px;overflow-y:auto;border:1px solid #dee2e6;border-radius:4px;padding:8px;background:#f8f9fa"
     class="mb-2"></div>
<div class="input-group">
  <input id="query-input" type="text" class="form-control"
         placeholder="Ask a question about selected datasets…">
  <button class="btn btn-success" onclick="doChat()">Ask</button>
  <button class="btn btn-outline-secondary" onclick="clearChat()">New search</button>
</div>
```

- [ ] **Step 6: Commit**

```bash
git add viewer/app.py viewer/templates/index.html tests/test_chat_endpoint.py
git commit -m "feat: add /chat endpoint and conversational Q&A UI with history"
```

---

## Task 9: requirements.txt + full test suite

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add new dependencies to requirements.txt**

```
openpyxl>=3.1
chromadb>=0.5
sentence-transformers>=3.0
```

- [ ] **Step 2: Run the full test suite**

```bash
python -m pytest tests/ -v
```
Expected: all tests PASS, no errors.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add openpyxl, chromadb, sentence-transformers to requirements"
```

---

## Spec Coverage Checklist

| Requirement | Task |
|---|---|
| New fields from XLS (source_url, xls_dataset_type, databases) | Task 1, 2 |
| Download driven by XLS manifest | Task 2 |
| Skip already-downloaded datasets | Task 2 |
| Viewer shows new fields | Task 3 |
| enrich.py unchanged | ✅ (passthrough — extra JSON keys ignored) |
| ChromaDB index build | Task 4, 5 |
| RAG / similarity search | Task 4, 6 |
| Metadata filter (xls_dataset_type) | Task 4, 6 |
| User question → filtered datasets → LLM answer | Task 6, 7 |
| Follow-up / conversational Q&A | Task 7, 8 |
| New search resets history | Task 8 |

---

## Suggested Execution Order

```
Task 1 → Task 2 → Task 3   (Step A: XLS fields + viewer)
Task 4 → Task 5 → Task 6   (Step B: ChromaDB + search UI)
Task 7 → Task 8             (Step C: Chat endpoint + UI)
Task 9                      (requirements + final test run)
```
