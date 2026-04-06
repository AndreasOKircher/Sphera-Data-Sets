# Module 5: Synonym Search + LLM Dataset Query — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add synonym/keyword search to the viewer index page and allow users to select datasets and ask a natural-language question, receiving a ranked, tabulated LLM analysis.

**Architecture:** Extended search uses client-side filtering on `data-*` attributes embedded from the dataset JSON (`synonyms` field) and the enriched summary (loaded server-side in `load_all()`). Dataset selection is tracked in a JS `Set`; a sticky bottom panel reveals a question input when ≥1 dataset is selected. The LLM query is a `POST /query` Flask route that delegates to `viewer/query.py`, which builds a structured prompt, calls the Anthropic API, and returns a ranked JSON array.

**Tech Stack:** Flask (existing), Anthropic Python SDK (existing), `python-dotenv` (existing), vanilla JS (no new frontend deps).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `viewer/app.py` | Modify | `load_all()` merges enriched summary; `POST /query` route; load API key at startup |
| `viewer/query.py` | **Create** | `build_prompt()`, `parse_response()`, `run_query()` |
| `viewer/templates/index.html` | Modify | `data-synonyms`/`data-summary` attrs, keyword input, checkboxes, selection panel, results table |
| `tests/test_query.py` | **Create** | Unit tests for pure functions in `viewer/query.py` + Flask route tests for `POST /query` |

---

## Task 1: Extend `load_all()` to merge enriched summaries

**Files:**
- Modify: `viewer/app.py`

### Context
`load_all()` currently returns raw dataset dicts from `dataset/output/*.json`. The enriched sidecars in `dataset/enriched/{uuid}.json` contain a `technology_description_summary` key produced by the LLM. We need this summary available on the index page for keyword search — without embedding the full `technology_description` (which can be thousands of chars). Datasets without a sidecar get an empty string.

- [ ] **Step 1: Add `load_dotenv` and API key config to `app.py`**

At the top of `viewer/app.py`, add after the existing imports:

```python
import os
from dotenv import load_dotenv
load_dotenv()
```

And after `app = Flask(...)`:

```python
app.config["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")
```

- [ ] **Step 2: Modify `load_all()` to attach `_summary`**

Replace the existing `load_all()` function in `viewer/app.py`:

```python
def load_all() -> list[dict]:
    datasets = []
    if not OUTPUT_DIR.exists():
        return datasets
    for f in sorted(OUTPUT_DIR.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            enriched = load_enriched(d.get("uuid", ""))
            d["_summary"] = enriched.get("technology_description_summary", "")
            datasets.append(d)
        except Exception as e:
            print(f"[WARN] skipping {f.name}: {e}", file=sys.stderr)
    return datasets
```

Note: `_summary` is a private key (underscore prefix) so it won't clash with XML-parsed fields.

- [ ] **Step 3: Verify Flask still starts and `/` loads without error**

```bash
python viewer/app.py
```

Open `http://localhost:5000` — cards should display exactly as before (no visible change yet). Stop the server with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add viewer/app.py
git commit -m "feat: merge enriched summary into load_all() for keyword search"
```

---

## Task 2: Keyword/Synonym Search Input

**Files:**
- Modify: `viewer/templates/index.html`

### Context
The `synonyms` field is already extracted from the ILCD XML (it is in `viewer/sections.py` MUST_FIELDS). It may contain comma-separated synonym strings. We embed it in `data-synonyms` on each card/row. We also embed `_summary` as `data-summary`. A second search input filters on these two attributes. Both inputs work as an AND filter: a dataset must match both queries if both are non-empty.

- [ ] **Step 1: Add `data-synonyms` and `data-summary` to card elements in `index.html`**

Find the `<a>` card element (line ~24) that currently has only `data-name`. Change to:

```html
<a href="/dataset/{{ d.uuid }}" style="display:block; text-decoration:none; color:inherit;"
   data-name="{{ (d.name_base or '') | lower }}"
   data-synonyms="{{ (d.synonyms or '') | lower }}"
   data-summary="{{ (d._summary or '') | lower }}">
```

- [ ] **Step 2: Add `data-synonyms` and `data-summary` to list rows**

Find the `<tr>` list element (line ~70) and add the same two attributes:

```html
<tr onclick="window.location='/dataset/{{ d.uuid }}'" ...
    data-name="{{ (d.name_base or '') | lower }}"
    data-synonyms="{{ (d.synonyms or '') | lower }}"
    data-summary="{{ (d._summary or '') | lower }}"
    ...>
```

- [ ] **Step 3: Add keyword search input to the toolbar**

In the toolbar `<div>` (after the existing `<input id="search">`), add:

```html
<input id="search-kw" type="text" placeholder="Keyword / synonym search…" oninput="filterAll()"
  style="padding:6px 12px; border:1px solid #ccc; border-radius:4px; font-size:14px; width:280px;">
```

- [ ] **Step 4: Extend `filterAll()` JS to use the new input**

Replace the existing `filterAll()` function:

```javascript
function filterAll() {
  const q1 = document.getElementById('search').value.toLowerCase();
  const q2 = document.getElementById('search-kw').value.toLowerCase();
  sessionStorage.setItem('search', q1);
  sessionStorage.setItem('search-kw', q2);
  let visible = 0;
  document.querySelectorAll('#view-cards > a').forEach(el => {
    const matchTitle = !q1 || el.dataset.name.includes(q1);
    const matchKw    = !q2 || el.dataset.synonyms.includes(q2) || el.dataset.summary.includes(q2);
    const show = matchTitle && matchKw;
    el.style.display = show ? '' : 'none';
    if (show) visible++;
  });
  document.querySelectorAll('#view-list tbody tr').forEach(el => {
    const matchTitle = !q1 || (el.dataset.name || '').includes(q1);
    const matchKw    = !q2 || (el.dataset.synonyms || '').includes(q2) || (el.dataset.summary || '').includes(q2);
    el.style.display = (matchTitle && matchKw) ? '' : 'none';
  });
  const total = {{ datasets | length }};
  const label = document.getElementById('count-label');
  if (label) {
    const active = q1 || q2;
    label.textContent = active ? `${visible} of ${total} datasets` : `${total} datasets loaded`;
  }
}
```

- [ ] **Step 5: Restore keyword search from sessionStorage on back-navigation**

In the existing restore block at the bottom of the `<script>`, extend to also restore `search-kw`:

```javascript
(function() {
  const saved1 = sessionStorage.getItem('search') || '';
  const saved2 = sessionStorage.getItem('search-kw') || '';
  if (saved1) document.getElementById('search').value = saved1;
  if (saved2) document.getElementById('search-kw').value = saved2;
  if (saved1 || saved2) filterAll();
})();
```

- [ ] **Step 6: Manual test**

Start Flask, open `http://localhost:5000`. Try keyword searches that match classifications or known synonym text. Verify AND behaviour: filling both inputs narrows results further. Verify card view and list view both filter.

- [ ] **Step 7: Commit**

```bash
git add viewer/templates/index.html
git commit -m "feat: add keyword/synonym search input to viewer index"
```

---

## Task 3: `viewer/query.py` — Pure Functions + Tests (TDD)

**Files:**
- Create: `viewer/query.py`
- Create: `tests/test_query.py`

### Context
`viewer/query.py` is a standalone module with three functions:
- `build_prompt(question, datasets)` → `str` — pure, builds the user message sent to the LLM.
- `parse_response(text)` → `list[dict]` — pure, parses the JSON array from the LLM response; tolerates markdown code fences.
- `run_query(question, datasets, api_key, model)` → `list[dict]` — calls the Anthropic API; tested with a mock client.

The LLM is instructed to return **only** a JSON array (no markdown, no prose). We still defensively strip code fences in `parse_response`. Prompt caching is applied to the system prompt (same pattern as `enrich.py`).

- [ ] **Step 1: Write `tests/test_query.py` (all tests, all failing)**

```python
"""Tests for viewer/query.py pure functions."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from viewer.query import build_prompt, parse_response, run_query, DEFAULT_QUERY_MODEL


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

DATASET_A = {
    "uuid": "aaa-111",
    "name_base": "Steel sheet, hot rolled",
    "classification": "Metal",
    "location": "DE",
    "reference_year": "2022",
    "_summary": "Hot-rolled steel sheet used in automotive applications.",
    "technology_description": "This is the long description.",
}

DATASET_B = {
    "uuid": "bbb-222",
    "name_base": "Aluminium profile",
    "classification": "Metal",
    "location": "EU",
    "reference_year": "2021",
    "_summary": "",
    "technology_description": "Aluminium extrusion for structural use.",
}


def test_build_prompt_contains_question():
    result = build_prompt("Which dataset represents steel sheet?", [DATASET_A])
    assert "Which dataset represents steel sheet?" in result


def test_build_prompt_contains_uuid():
    result = build_prompt("test", [DATASET_A])
    assert "aaa-111" in result


def test_build_prompt_uses_summary_when_available():
    result = build_prompt("test", [DATASET_A])
    assert "Hot-rolled steel sheet" in result
    assert "This is the long description" not in result


def test_build_prompt_falls_back_to_technology_description():
    result = build_prompt("test", [DATASET_B])
    assert "Aluminium extrusion" in result


def test_build_prompt_truncates_fallback_description():
    long_desc = "x" * 1000
    d = {**DATASET_B, "technology_description": long_desc, "_summary": ""}
    result = build_prompt("test", [d])
    desc_line = next(l for l in result.splitlines() if l.startswith("Description:"))
    desc_content = desc_line[len("Description:"):].strip()
    assert desc_content == "x" * 500  # exactly 500 chars, not 1000


def test_build_prompt_multiple_datasets():
    result = build_prompt("test", [DATASET_A, DATASET_B])
    assert "aaa-111" in result
    assert "bbb-222" in result


# ---------------------------------------------------------------------------
# parse_response
# ---------------------------------------------------------------------------

VALID_JSON = json.dumps([
    {"uuid": "aaa-111", "name": "Steel sheet", "rank": 1, "relevance_score": 5, "comment": "Direct match."},
    {"uuid": "bbb-222", "name": "Aluminium profile", "rank": 2, "relevance_score": 2, "comment": "Different material."},
])


def test_parse_response_valid_json():
    result = parse_response(VALID_JSON)
    assert len(result) == 2
    assert result[0]["rank"] == 1
    assert result[1]["uuid"] == "bbb-222"


def test_parse_response_strips_markdown_fences():
    fenced = f"```json\n{VALID_JSON}\n```"
    result = parse_response(fenced)
    assert len(result) == 2


def test_parse_response_strips_plain_fences():
    fenced = f"```\n{VALID_JSON}\n```"
    result = parse_response(fenced)
    assert len(result) == 2


def test_parse_response_strips_whitespace():
    result = parse_response(f"\n  {VALID_JSON}  \n")
    assert len(result) == 2


def test_parse_response_malformed_returns_empty():
    result = parse_response("This is not JSON at all.")
    assert result == []


def test_parse_response_non_list_returns_empty():
    result = parse_response('{"key": "value"}')
    assert result == []


def test_parse_response_empty_array():
    result = parse_response("[]")
    assert result == []


# ---------------------------------------------------------------------------
# run_query (mocked API)
# ---------------------------------------------------------------------------

def _make_mock_client(response_text: str):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=response_text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


def test_run_query_returns_parsed_results(monkeypatch):
    import viewer.query as qmod
    mock_client = _make_mock_client(VALID_JSON)
    monkeypatch.setattr(qmod.anthropic, "Anthropic", MagicMock(return_value=mock_client))
    results = run_query("Which is steel?", [DATASET_A, DATASET_B], api_key="fake-key")
    assert len(results) == 2
    assert results[0]["rank"] == 1


def test_run_query_passes_question_in_prompt(monkeypatch):
    import viewer.query as qmod
    mock_client = _make_mock_client(VALID_JSON)
    monkeypatch.setattr(qmod.anthropic, "Anthropic", MagicMock(return_value=mock_client))
    run_query("my unique question xyz", [DATASET_A], api_key="fake-key")
    call_args = mock_client.messages.create.call_args
    messages = call_args.kwargs["messages"]
    assert "my unique question xyz" in messages[0]["content"]


def test_run_query_uses_default_model(monkeypatch):
    import viewer.query as qmod
    mock_client = _make_mock_client(VALID_JSON)
    monkeypatch.setattr(qmod.anthropic, "Anthropic", MagicMock(return_value=mock_client))
    run_query("test", [DATASET_A], api_key="fake-key")
    call_args = mock_client.messages.create.call_args
    assert call_args.kwargs["model"] == DEFAULT_QUERY_MODEL


def test_run_query_uses_custom_model(monkeypatch):
    import viewer.query as qmod
    mock_client = _make_mock_client(VALID_JSON)
    monkeypatch.setattr(qmod.anthropic, "Anthropic", MagicMock(return_value=mock_client))
    run_query("test", [DATASET_A], api_key="fake-key", model="claude-sonnet-4-6")
    call_args = mock_client.messages.create.call_args
    assert call_args.kwargs["model"] == "claude-sonnet-4-6"


def test_run_query_malformed_llm_response_returns_empty(monkeypatch):
    import viewer.query as qmod
    mock_client = _make_mock_client("Sorry, I cannot answer that.")
    monkeypatch.setattr(qmod.anthropic, "Anthropic", MagicMock(return_value=mock_client))
    results = run_query("test", [DATASET_A], api_key="fake-key")
    assert results == []


# ---------------------------------------------------------------------------
# /query Flask route
# ---------------------------------------------------------------------------

import pytest

@pytest.fixture
def flask_client(monkeypatch):
    """Flask test client with API key configured and run_query mocked."""
    import viewer.app as app_mod
    import viewer.query as qmod
    app_mod.app.config["ANTHROPIC_API_KEY"] = "fake-key"
    app_mod.app.config["TESTING"] = True

    # Mock run_query at its definition site (app.py uses a local import inside
    # the function body, so patching "viewer.app.run_query" would have no effect)
    monkeypatch.setattr(
        "viewer.query.run_query",
        lambda question, datasets, api_key, model: [
            {"uuid": d["uuid"], "name": d.get("name_base", ""), "rank": i + 1,
             "relevance_score": 5 - i, "comment": "test comment"}
            for i, d in enumerate(datasets)
        ],
    )
    # Mock load_all to return two known datasets (avoids reading disk)
    monkeypatch.setattr(
        "viewer.app.load_all",
        lambda: [
            {**DATASET_A, "uuid": "aaa-111"},
            {**DATASET_B, "uuid": "bbb-222"},
        ],
    )
    with app_mod.app.test_client() as c:
        yield c


def test_query_route_missing_question(flask_client):
    resp = flask_client.post("/query",
        json={"uuids": ["aaa-111"]},
        content_type="application/json")
    assert resp.status_code == 400
    assert "question" in resp.get_json()["error"]


def test_query_route_missing_uuids(flask_client):
    resp = flask_client.post("/query",
        json={"question": "Which is better?"},
        content_type="application/json")
    assert resp.status_code == 400
    assert "uuids" in resp.get_json()["error"]


def test_query_route_no_matching_datasets(flask_client):
    resp = flask_client.post("/query",
        json={"question": "test", "uuids": ["unknown-uuid"]},
        content_type="application/json")
    assert resp.status_code == 400
    assert "No matching" in resp.get_json()["error"]


def test_query_route_no_api_key(monkeypatch):
    import viewer.app as app_mod
    app_mod.app.config["ANTHROPIC_API_KEY"] = ""
    app_mod.app.config["TESTING"] = True
    with app_mod.app.test_client() as c:
        resp = c.post("/query",
            json={"question": "test", "uuids": ["aaa-111"]},
            content_type="application/json")
    assert resp.status_code == 503
    app_mod.app.config["ANTHROPIC_API_KEY"] = "fake-key"  # restore


def test_query_route_success(flask_client):
    resp = flask_client.post("/query",
        json={"question": "Which is steel?", "uuids": ["aaa-111"]},
        content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["uuid"] == "aaa-111"
```

- [ ] **Step 2: Run tests — confirm all fail**

```bash
python -m pytest tests/test_query.py -v 2>&1 | head -40
```

Expected: `ImportError: cannot import name 'build_prompt' from 'viewer.query'` (module doesn't exist yet).

- [ ] **Step 3: Create `viewer/query.py`**

```python
"""LLM query engine: rank datasets against a user question."""

import json
import anthropic

QUERY_SYSTEM = (
    "You are an LCA (Life Cycle Assessment) data analyst. "
    "The user will ask a question about selecting or comparing datasets. "
    "Analyze each dataset's relevance to the question and return a JSON array, "
    "ranked from most to least relevant. "
    "Each element must have exactly these keys:\n"
    '  "uuid": dataset UUID string\n'
    '  "name": dataset name string\n'
    '  "rank": integer starting at 1\n'
    '  "relevance_score": integer 1-5 (5 = highly relevant, 1 = not relevant)\n'
    '  "comment": 1-2 sentence explanation of relevance to the question\n'
    "Return ONLY the JSON array, no other text, no markdown code fences."
)

DEFAULT_QUERY_MODEL = "claude-haiku-4-5"


def build_prompt(question: str, datasets: list[dict]) -> str:
    """Build the user message for the LLM query.

    Uses enriched summary (_summary key) when available; falls back to the
    first 500 characters of technology_description.
    """
    lines = [f"Question: {question}\n", "Datasets:"]
    for d in datasets:
        desc = d.get("_summary") or (d.get("technology_description") or "")[:500]
        lines.append(
            f"\n---\n"
            f"UUID: {d.get('uuid', '')}\n"
            f"Name: {d.get('name_base', '')}\n"
            f"Classification: {d.get('classification', '')}\n"
            f"Location: {d.get('location', '')}\n"
            f"Year: {d.get('reference_year', '')}\n"
            f"Description: {desc}"
        )
    return "\n".join(lines)


def parse_response(text: str) -> list[dict]:
    """Parse LLM response into a list of ranked dataset dicts.

    Strips optional markdown code fences before parsing.
    Returns empty list on any parse failure.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        inner = lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:]
        stripped = "\n".join(inner)
    try:
        result = json.loads(stripped)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


def run_query(
    question: str,
    datasets: list[dict],
    api_key: str,
    model: str = DEFAULT_QUERY_MODEL,
) -> list[dict]:
    """Call the Claude API and return ranked dataset results.

    Parameters
    ----------
    question:
        The user's natural-language question.
    datasets:
        List of dataset dicts (already filtered to the selected subset).
        Each dict should have uuid, name_base, classification, location,
        reference_year, and optionally _summary / technology_description.
    api_key:
        Anthropic API key.
    model:
        Claude model ID. Default is Haiku; use Sonnet for better ranking quality.

    Returns
    -------
    List of dicts with keys: uuid, name, rank, relevance_score, comment.
    Empty list if LLM response cannot be parsed.
    """
    client = anthropic.Anthropic(api_key=api_key)
    user_message = build_prompt(question, datasets)
    resp = client.messages.create(
        model=model,
        max_tokens=4000,
        system=[{"type": "text", "text": QUERY_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_message}],
    )
    return parse_response(resp.content[0].text)
```

- [ ] **Step 4: Run tests — confirm all pass**

```bash
python -m pytest tests/test_query.py -v
```

Expected: all tests pass. Note: `test_run_query_*` tests use `monkeypatch` to mock `anthropic.Anthropic` — no real API call is made.

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
python -m pytest --tb=short -q
```

Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add viewer/query.py tests/test_query.py
git commit -m "feat: add viewer/query.py with build_prompt, parse_response, run_query + tests"
```

---

## Task 4: Flask `POST /query` Route

**Files:**
- Modify: `viewer/app.py`

### Context
The route receives `{"question": "...", "uuids": ["uuid1", "uuid2", ...]}` as a JSON body. It loads the full dataset list (already enriched by `load_all()`), filters to the requested UUIDs, calls `run_query()`, and returns `{"results": [...]}`. Error responses use standard HTTP status codes.

- [ ] **Step 1: Add `flask.request` to imports**

At the top of `viewer/app.py`, extend the Flask import:

```python
from flask import Flask, render_template, abort, request, jsonify
```

- [ ] **Step 2: Add the `/query` route**

Add after the `/shutdown` route in `viewer/app.py`:

```python
@app.route("/query", methods=["POST"])
def query_datasets():
    api_key = app.config.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured on server"}), 503

    body = request.get_json(force=True, silent=True) or {}
    question = (body.get("question") or "").strip()
    uuids     = body.get("uuids") or []

    if not question:
        return jsonify({"error": "question is required"}), 400
    if not uuids:
        return jsonify({"error": "uuids list is required"}), 400

    uuid_set = set(uuids)
    selected = [d for d in load_all() if d.get("uuid") in uuid_set]

    if not selected:
        return jsonify({"error": "No matching datasets found for provided UUIDs"}), 400

    from viewer.query import run_query, DEFAULT_QUERY_MODEL
    model = request.args.get("model", DEFAULT_QUERY_MODEL)

    try:
        results = run_query(question, selected, api_key, model)
        return jsonify({"results": results})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
```

> **Known limitation:** `load_all()` re-reads all dataset files from disk on every `/query` request. For the current collection size this is fine (milliseconds), but worth noting for future caching work.


- [ ] **Step 3: Manual smoke test of the route**

Start Flask, then in a second terminal:

```bash
curl -s -X POST http://localhost:5000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "test", "uuids": []}' | python -m json.tool
```

Expected: `{"error": "uuids list is required"}` with status 400.

```bash
curl -s -X POST http://localhost:5000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "", "uuids": ["any"]}' | python -m json.tool
```

Expected: `{"error": "question is required"}` with status 400.

- [ ] **Step 4: Commit**

```bash
git add viewer/app.py
git commit -m "feat: add POST /query route to viewer app"
```

---

## Task 5: Dataset Selection UI (Checkboxes + Selection Panel)

**Files:**
- Modify: `viewer/templates/index.html`

### Context
Each card and list row gets a checkbox. A JS `Set` (`selectedUUIDs`) tracks selections. When the set is non-empty, a sticky bottom bar appears showing the count, a "Clear" button, and a question input. Card checkboxes use `stopPropagation` so clicking the checkbox doesn't navigate to the detail page.

Cards that are selected get a blue-border highlight. The list-view header gets a "Select all visible" checkbox.

- [ ] **Step 1: Add checkbox to card elements**

Inside the card `<div>` (the white box with border-radius), add a checkbox in the top-right corner. The outer `<a>` wraps the whole card, so we need `event.stopPropagation()` on the checkbox click:

Replace the card `<a>` block structure to:

```html
<a href="/dataset/{{ d.uuid }}" style="display:block; text-decoration:none; color:inherit;"
   data-name="{{ (d.name_base or '') | lower }}"
   data-synonyms="{{ (d.synonyms or '') | lower }}"
   data-summary="{{ (d._summary or '') | lower }}"
   data-uuid="{{ d.uuid }}">
  <div id="card-{{ d.uuid }}"
       style="background:#fff; border:2px solid #ddd; border-radius:8px; padding:16px; position:relative;
              box-shadow:0 1px 3px rgba(0,0,0,.06); transition: box-shadow .15s, border-color .15s;"
       onmouseover="this.style.boxShadow='0 4px 12px rgba(0,0,0,.12)'"
       onmouseout="this.style.boxShadow='0 1px 3px rgba(0,0,0,.06)'">
    <input type="checkbox" data-uuid="{{ d.uuid }}"
           onclick="event.stopPropagation(); toggleSelect('{{ d.uuid }}', this.checked)"
           style="position:absolute; top:10px; right:10px; width:16px; height:16px; cursor:pointer;">
    <div style="font-weight:bold; font-size:15px; margin-bottom:6px; line-height:1.4; padding-right:24px;">
      {{ d.name_base or "—" }}
    </div>
    ... (rest of card content unchanged) ...
  </div>
</a>
```

- [ ] **Step 2: Add checkbox column to list view**

> **⚠️ Column index shift:** The existing `sortTable(colIdx, ...)` JS function uses `a.cells[colIdx]` to read cell text. Prepending a checkbox column shifts all column indices by 1. After adding the checkbox `<th>`, update all six `onclick="sortTable(N, ...)"` calls on the header `<th>` elements: Name→`0` becomes `1`, Location→`1` becomes `2`, Year→`2` becomes `3`, Type→`3` becomes `4`, DQI→`4` becomes `5`, Supply→`5` becomes `6`.

In the `<thead>` row, prepend:

```html
<th style="padding:10px 12px; border-bottom:1px solid #ddd; width:36px;">
  <input type="checkbox" id="select-all-cb" onclick="toggleSelectAllVisible(this.checked)"
         title="Select all visible" style="cursor:pointer;">
</th>
```

In each `<tbody> <tr>`, prepend:

```html
<td style="padding:8px 12px;" onclick="event.stopPropagation()">
  <input type="checkbox" data-uuid="{{ d.uuid }}"
         onclick="toggleSelect('{{ d.uuid }}', this.checked)"
         style="cursor:pointer;">
</td>
```

Also add `data-uuid="{{ d.uuid }}"` attribute to the `<tr>` itself for easy JS targeting.

- [ ] **Step 3: Add the sticky selection panel HTML**

Just before the closing `{% endblock %}`, add:

```html
<div id="selection-panel" style="
  display:none; position:fixed; bottom:0; left:0; right:0; z-index:100;
  background:#1a1a2e; color:#fff; padding:12px 24px;
  box-shadow:0 -2px 8px rgba(0,0,0,.2);">
  <span id="sel-count" style="font-size:14px; min-width:120px;"></span>
  <button onclick="clearSelection()"
    style="padding:4px 12px; border:1px solid rgba(255,255,255,.3); border-radius:4px;
           background:transparent; color:#fff; cursor:pointer; font-size:13px;">
    Clear
  </button>
  <input id="query-question" type="text" placeholder="Ask a question about the selected datasets…"
    style="flex:1; min-width:240px; padding:6px 12px; border-radius:4px;
           border:1px solid rgba(255,255,255,.3); background:rgba(255,255,255,.1);
           color:#fff; font-size:14px;"
    onkeydown="if(event.key==='Enter') submitQuery()">
  <button onclick="submitQuery()"
    style="padding:6px 16px; border:none; border-radius:4px;
           background:#0057b8; color:#fff; cursor:pointer; font-size:14px; font-weight:bold;">
    Ask LLM
  </button>
</div>
```

The JS `updateSelectionUI()` (Step 4) switches it to `display:flex` when visible.

- [ ] **Step 4: Add JS selection logic**

In the `<script>` block, add after the existing variables:

```javascript
const selectedUUIDs = new Set();

function toggleSelect(uuid, checked) {
  if (checked) {
    selectedUUIDs.add(uuid);
  } else {
    selectedUUIDs.delete(uuid);
  }
  updateSelectionUI();
}

function clearSelection() {
  selectedUUIDs.clear();
  document.querySelectorAll('input[type=checkbox][data-uuid]').forEach(cb => cb.checked = false);
  document.getElementById('select-all-cb') && (document.getElementById('select-all-cb').checked = false);
  updateSelectionUI();
}

function toggleSelectAllVisible(checked) {
  document.querySelectorAll('#view-list tbody tr').forEach(row => {
    if (row.style.display === 'none') return;
    const uuid = row.dataset.uuid;
    if (!uuid) return;
    if (checked) selectedUUIDs.add(uuid); else selectedUUIDs.delete(uuid);
    const cb = row.querySelector('input[type=checkbox]');
    if (cb) cb.checked = checked;
    // sync card checkbox
    const cardCb = document.querySelector(`#view-cards input[data-uuid="${uuid}"]`);
    if (cardCb) cardCb.checked = checked;
  });
  updateSelectionUI();
}

function updateSelectionUI() {
  const n = selectedUUIDs.size;
  const panel = document.getElementById('selection-panel');
  const countEl = document.getElementById('sel-count');
  if (n === 0) {
    panel.style.display = 'none';
  } else {
    panel.style.display = 'flex';
    panel.style.alignItems = 'center';
    panel.style.gap = '12px';
    panel.style.flexWrap = 'wrap';
    countEl.textContent = `${n} dataset${n === 1 ? '' : 's'} selected`;
  }
  // Highlight selected cards
  document.querySelectorAll('#view-cards [id^="card-"]').forEach(card => {
    const uuid = card.id.replace('card-', '');
    card.style.borderColor = selectedUUIDs.has(uuid) ? '#0057b8' : '#ddd';
  });
}
```

- [ ] **Step 5: Manual test — selection UI**

Start Flask. Click checkboxes on a few cards. Verify:
- Panel appears at bottom with correct count
- Cards get blue border when selected
- "Clear" resets all
- List-view checkboxes also work
- "Select all visible" in list header selects all visible rows

- [ ] **Step 6: Commit**

```bash
git add viewer/templates/index.html
git commit -m "feat: add dataset selection checkboxes and sticky selection panel"
```

---

## Task 6: Query Submission + Results Table

**Files:**
- Modify: `viewer/templates/index.html`

### Context
When the user clicks "Ask LLM", a `fetch()` POST is sent to `/query`. While waiting, the button shows a spinner and is disabled. The results are rendered as a table inserted above the dataset cards/list, showing columns: Rank | Dataset Name | Score | Comment. Clicking a name navigates to the detail page. An error message is shown if the API call fails. Results persist until the user manually dismisses them or starts a new query.

- [ ] **Step 1: Add results panel HTML**

Above `<div id="view-cards"...>` (just after the toolbar div), add:

```html
<div id="results-panel" style="display:none; margin-bottom:20px;">
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
    <h2 style="font-size:16px; font-weight:bold;" id="results-question-label"></h2>
    <button onclick="dismissResults()"
      style="padding:3px 10px; font-size:12px; border:1px solid #ccc; border-radius:4px;
             background:#fff; cursor:pointer;">✕ Dismiss</button>
  </div>
  <div id="results-error" style="color:#c00; font-size:14px; display:none;"></div>
  <table id="results-table" style="width:100%; border-collapse:collapse; background:#fff;
    border:1px solid #ddd; border-radius:8px; overflow:hidden; font-size:13px; display:none;">
    <thead>
      <tr style="background:#f0f4ff; font-weight:bold; text-align:left;">
        <th style="padding:10px 12px; border-bottom:1px solid #ddd; width:50px;">Rank</th>
        <th style="padding:10px 12px; border-bottom:1px solid #ddd;">Dataset</th>
        <th style="padding:10px 12px; border-bottom:1px solid #ddd; width:65px; text-align:center;">Score</th>
        <th style="padding:10px 12px; border-bottom:1px solid #ddd;">Comment</th>
      </tr>
    </thead>
    <tbody id="results-tbody"></tbody>
  </table>
</div>
```

- [ ] **Step 2: Add `submitQuery()` JS function**

```javascript
async function submitQuery() {
  const question = document.getElementById('query-question').value.trim();
  if (!question) { alert('Enter a question first.'); return; }
  if (selectedUUIDs.size === 0) { alert('Select at least one dataset.'); return; }

  const btn = document.querySelector('#selection-panel button:last-child');
  btn.textContent = '⏳ Asking…';
  btn.disabled = true;

  const panel = document.getElementById('results-panel');
  const errorEl = document.getElementById('results-error');
  const tableEl = document.getElementById('results-table');
  const tbody = document.getElementById('results-tbody');
  const label = document.getElementById('results-question-label');

  label.textContent = `Q: ${question}`;
  errorEl.style.display = 'none';
  tableEl.style.display = 'none';
  tbody.innerHTML = '';
  panel.style.display = 'block';
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });

  try {
    const resp = await fetch('/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, uuids: [...selectedUUIDs] }),
    });
    const data = await resp.json();
    if (!resp.ok || data.error) {
      errorEl.textContent = data.error || `Server error ${resp.status}`;
      errorEl.style.display = '';
    } else if (!data.results || data.results.length === 0) {
      errorEl.textContent = 'The LLM returned no ranked results. Try rephrasing the question.';
      errorEl.style.display = '';
    } else {
      data.results.forEach(r => {
        const score = Number(r.relevance_score) || 0;
        const scoreColor = score >= 4 ? '#065f46' : score >= 2 ? '#92400e' : '#6b7280';
        const scoreBg   = score >= 4 ? '#d1fae5' : score >= 2 ? '#fef3c7' : '#e5e7eb';
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid #f0f0f0';
        tr.innerHTML = `
          <td style="padding:8px 12px; text-align:center; font-weight:bold;">${r.rank ?? '—'}</td>
          <td style="padding:8px 12px;">
            <a href="/dataset/${r.uuid}" style="color:#0057b8; font-weight:bold;">${r.name || r.uuid}</a>
          </td>
          <td style="padding:8px 12px; text-align:center;">
            <span style="display:inline-block; padding:2px 8px; border-radius:4px;
                         background:${scoreBg}; color:${scoreColor}; font-weight:bold; font-size:12px;">
              ${score}/5
            </span>
          </td>
          <td style="padding:8px 12px; color:#444;">${r.comment || ''}</td>`;
        tbody.appendChild(tr);
      });
      tableEl.style.display = '';
    }
  } catch (err) {
    errorEl.textContent = `Request failed: ${err.message}`;
    errorEl.style.display = '';
  } finally {
    btn.textContent = 'Ask LLM';
    btn.disabled = false;
  }
}

function dismissResults() {
  document.getElementById('results-panel').style.display = 'none';
}
```

- [ ] **Step 3: Manual end-to-end test**

Prerequisites: `.env` with valid `ANTHROPIC_API_KEY`, at least 2 enriched datasets.

1. Start Flask: `python viewer/app.py`
2. Open `http://localhost:5000`
3. Select 3–5 datasets using checkboxes
4. Type a question, e.g. "Which dataset is most suitable for a steel sheet component?"
5. Click "Ask LLM"
6. Verify: spinner appears, then results table renders with rank, score badge (colour-coded), and comment
7. Verify: clicking a dataset name in the results navigates to its detail page
8. Verify: "Dismiss" hides the results panel
9. Test error case: temporarily unset the API key in `.env`, restart Flask, try a query → expect error message in the panel (not a crash)

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest --tb=short -q
```

Expected: all tests pass (no regressions from template changes).

- [ ] **Step 5: Commit**

```bash
git add viewer/templates/index.html
git commit -m "feat: add LLM query submission and ranked results table to viewer"
```

---

## Task 7: Search Field Selection + Query Field Selection

**Files:**
- Modify: `viewer/app.py`
- Modify: `viewer/query.py`
- Modify: `viewer/templates/index.html`
- Modify: `tests/test_query.py`

### Context

Two related extensions:

**A — Search field selection:** A small "⚙ Fields" button next to the keyword search input opens a dropdown with checkboxes for extra fields (`classification`, `location`, `dataset_type`, `reference_year`). By default only synonyms + summary are checked (current Task 2 behaviour). Checking additional fields adds them to the client-side AND filter. All extra fields need `data-*` attributes embedded on cards and list rows.

**B — Query field selection:** A "⚙ Fields" button near "Ask LLM" opens a dropdown with checkboxes for which dataset fields get included in the LLM prompt. Default: description/summary, classification, location, year. Optional extras: synonyms, dataset type. This requires `build_prompt()` to accept a `fields` parameter, the `/query` route to accept a `fields` list in the JSON body, and the UI to send it.

Both dropdowns use the same pure-CSS/JS popover pattern (toggle visibility on button click, close on outside click) — no new dependencies.

---

### Task 7A: Search Field Dropdown

- [ ] **Step 1: Embed additional `data-*` attributes on cards and list rows in `index.html`**

In the card `<a>` element (already has `data-name`, `data-synonyms`, `data-summary`), add:

```html
data-classification="{{ (d.classification or '') | lower }}"
data-location="{{ (d.location or '') | lower }}"
data-type="{{ (d.dataset_type or '') | lower }}"
data-year="{{ (d.reference_year or '') | lower }}"
```

In the list `<tr>` element, add the same four attributes.

- [ ] **Step 2: Add the "⚙ Fields" button and dropdown HTML next to the keyword search**

Immediately after `<input id="search-kw" ...>`, add:

```html
<div style="position:relative; display:inline-block;">
  <button id="search-fields-btn" onclick="toggleSearchFields(event)"
    style="padding:6px 10px; border:1px solid #ccc; border-radius:4px;
           background:#fff; cursor:pointer; font-size:13px;" title="Choose fields to search">
    ⚙ Fields
  </button>
  <div id="search-fields-panel" style="display:none; position:absolute; top:36px; left:0;
       background:#fff; border:1px solid #ccc; border-radius:6px; padding:10px 14px;
       box-shadow:0 4px 12px rgba(0,0,0,.12); z-index:50; min-width:180px; font-size:13px;">
    <label style="display:block; margin-bottom:6px;">
      <input type="checkbox" id="sf-synonyms" checked onchange="filterAll()"> Synonyms
    </label>
    <label style="display:block; margin-bottom:6px;">
      <input type="checkbox" id="sf-summary" checked onchange="filterAll()"> Summary
    </label>
    <label style="display:block; margin-bottom:6px;">
      <input type="checkbox" id="sf-classification" onchange="filterAll()"> Classification
    </label>
    <label style="display:block; margin-bottom:6px;">
      <input type="checkbox" id="sf-location" onchange="filterAll()"> Location
    </label>
    <label style="display:block; margin-bottom:6px;">
      <input type="checkbox" id="sf-type" onchange="filterAll()"> Dataset type
    </label>
    <label style="display:block;">
      <input type="checkbox" id="sf-year" onchange="filterAll()"> Reference year
    </label>
  </div>
</div>
```

- [ ] **Step 3: Add `toggleSearchFields()` JS and close-on-outside-click handler**

```javascript
function toggleSearchFields(e) {
  e.stopPropagation();
  const p = document.getElementById('search-fields-panel');
  p.style.display = p.style.display === 'none' ? '' : 'none';
}
document.addEventListener('click', () => {
  const p = document.getElementById('search-fields-panel');
  if (p) p.style.display = 'none';
});
```

- [ ] **Step 4: Extend `filterAll()` to respect the field checkboxes**

Replace the keyword match line in `filterAll()`. The new logic reads which field checkboxes are checked and builds a combined string per element:

```javascript
function _kwSearchText(el) {
  const parts = [];
  if (document.getElementById('sf-synonyms')?.checked)      parts.push(el.dataset.synonyms || '');
  if (document.getElementById('sf-summary')?.checked)        parts.push(el.dataset.summary || '');
  if (document.getElementById('sf-classification')?.checked) parts.push(el.dataset.classification || '');
  if (document.getElementById('sf-location')?.checked)       parts.push(el.dataset.location || '');
  if (document.getElementById('sf-type')?.checked)           parts.push(el.dataset.type || '');
  if (document.getElementById('sf-year')?.checked)           parts.push(el.dataset.year || '');
  return parts.join(' ');
}
```

Then in `filterAll()`, replace the two `matchKw` lines:

```javascript
// cards
const matchKw = !q2 || _kwSearchText(el).includes(q2);

// list rows
const matchKw = !q2 || _kwSearchText(el).includes(q2);
```

- [ ] **Step 5: Manual test**

Start Flask. Open the keyword search, click "⚙ Fields". Check "Classification". Search for a known classification term (e.g. "metal") — cards should appear/disappear. Verify the dropdown closes when clicking outside it. Verify default behaviour (synonyms + summary checked) is unchanged from Task 2.

- [ ] **Step 6: Commit**

```bash
git add viewer/templates/index.html
git commit -m "feat: add field-selection dropdown to keyword search"
```

---

### Task 7B: Query Field Selection

- [ ] **Step 1: Update `build_prompt()` to accept a `fields` parameter — write failing tests first**

Add to `tests/test_query.py`:

```python
# ---------------------------------------------------------------------------
# build_prompt with fields parameter
# ---------------------------------------------------------------------------

ALL_FIELDS = ["classification", "location", "year", "description"]

def test_build_prompt_includes_all_fields_by_default():
    result = build_prompt("test", [DATASET_A])
    assert "Metal" in result          # classification
    assert "DE" in result             # location
    assert "2022" in result           # year

def test_build_prompt_excludes_classification_when_not_in_fields():
    result = build_prompt("test", [DATASET_A], fields=["location", "year", "description"])
    assert "Metal" not in result
    assert "DE" in result

def test_build_prompt_excludes_location_when_not_in_fields():
    result = build_prompt("test", [DATASET_A], fields=["classification", "year", "description"])
    assert "DE" not in result
    assert "Metal" in result

def test_build_prompt_includes_synonyms_when_requested():
    d = {**DATASET_A, "synonyms": "flat-rolled steel; HR steel"}
    result = build_prompt("test", [d], fields=["description", "synonyms"])
    assert "flat-rolled steel" in result

def test_build_prompt_empty_fields_list_sends_name_and_uuid_only():
    result = build_prompt("test", [DATASET_A], fields=[])
    assert "aaa-111" in result        # uuid always present
    assert "Steel sheet" in result    # name always present
    assert "Metal" not in result      # classification excluded
    assert "DE" not in result         # location excluded
```

Run: `python -m pytest tests/test_query.py -k "fields" -v` — expect 5 failures.

- [ ] **Step 2: Update `build_prompt()` in `viewer/query.py`**

Valid `fields` values: `"classification"`, `"location"`, `"year"`, `"description"`, `"synonyms"`, `"dataset_type"`. UUID and name are always included regardless of `fields`.

```python
_ALL_FIELDS = ["classification", "location", "year", "description"]

def build_prompt(
    question: str,
    datasets: list[dict],
    fields: list[str] | None = None,
) -> str:
    """Build the user message for the LLM query.

    Parameters
    ----------
    fields:
        Which dataset fields to include per entry. Defaults to
        ["classification", "location", "year", "description"].
        UUID and name are always included regardless of this setting.
        Valid values: "classification", "location", "year",
                      "description", "synonyms", "dataset_type".
    """
    if fields is None:
        fields = list(_ALL_FIELDS)
    field_set = set(fields)

    lines = [f"Question: {question}\n", "Datasets:"]
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

- [ ] **Step 3: Run the new field tests — confirm all pass**

```bash
python -m pytest tests/test_query.py -k "fields" -v
```

Expected: all 5 pass.

- [ ] **Step 4: Update `/query` route in `app.py` to accept `fields` from request body**

In the `query_datasets()` route, after extracting `uuids`, add:

```python
fields = body.get("fields") or None  # None → build_prompt uses its default
```

And pass it to `run_query()` (see Step 5).

- [ ] **Step 5: Update `run_query()` in `viewer/query.py` to pass `fields` to `build_prompt()`**

```python
def run_query(
    question: str,
    datasets: list[dict],
    api_key: str,
    model: str = DEFAULT_QUERY_MODEL,
    fields: list[str] | None = None,
) -> list[dict]:
    ...
    user_message = build_prompt(question, datasets, fields=fields)
    ...
```

And update the route call:

```python
results = run_query(question, selected, api_key, model, fields=fields)
```

- [ ] **Step 6: Run full test suite — confirm no regressions**

```bash
python -m pytest --tb=short -q
```

Expected: all tests pass. The existing `run_query` tests don't pass `fields` so they exercise the default path.

- [ ] **Step 7: Add "⚙ Fields" button next to "Ask LLM" in the selection panel**

In the selection panel HTML (inside `<div id="selection-panel">`), add after the question input and before "Ask LLM":

```html
<div style="position:relative; display:inline-block;">
  <button id="query-fields-btn" onclick="toggleQueryFields(event)"
    style="padding:6px 10px; border:1px solid rgba(255,255,255,.3); border-radius:4px;
           background:rgba(255,255,255,.1); color:#fff; cursor:pointer; font-size:13px;"
    title="Choose dataset fields to include in the query">
    ⚙ Fields
  </button>
  <div id="query-fields-panel" style="display:none; position:absolute; bottom:40px; right:0;
       background:#fff; color:#222; border:1px solid #ccc; border-radius:6px; padding:10px 14px;
       box-shadow:0 -4px 12px rgba(0,0,0,.15); z-index:150; min-width:200px; font-size:13px;">
    <div style="font-weight:bold; margin-bottom:8px; font-size:12px; color:#666;">
      Include in LLM prompt:
    </div>
    <label style="display:block; margin-bottom:6px;">
      <input type="checkbox" id="qf-description" checked> Description / summary
    </label>
    <label style="display:block; margin-bottom:6px;">
      <input type="checkbox" id="qf-classification" checked> Classification
    </label>
    <label style="display:block; margin-bottom:6px;">
      <input type="checkbox" id="qf-location" checked> Location
    </label>
    <label style="display:block; margin-bottom:6px;">
      <input type="checkbox" id="qf-year" checked> Reference year
    </label>
    <label style="display:block; margin-bottom:6px;">
      <input type="checkbox" id="qf-synonyms"> Synonyms
    </label>
    <label style="display:block;">
      <input type="checkbox" id="qf-type"> Dataset type
    </label>
  </div>
</div>
```

- [ ] **Step 8: Add `toggleQueryFields()` JS and update `submitQuery()` to collect checked fields**

```javascript
function toggleQueryFields(e) {
  e.stopPropagation();
  const p = document.getElementById('query-fields-panel');
  p.style.display = p.style.display === 'none' ? '' : 'none';
}

function _selectedQueryFields() {
  const map = {
    'qf-description':    'description',
    'qf-classification': 'classification',
    'qf-location':       'location',
    'qf-year':           'year',
    'qf-synonyms':       'synonyms',
    'qf-type':           'dataset_type',
  };
  return Object.entries(map)
    .filter(([id]) => document.getElementById(id)?.checked)
    .map(([, val]) => val);
}
```

In `submitQuery()`, update the `fetch` body:

```javascript
body: JSON.stringify({
  question,
  uuids: [...selectedUUIDs],
  fields: _selectedQueryFields(),
}),
```

- [ ] **Step 9: Manual end-to-end test**

1. Select 3 datasets, click "⚙ Fields" (query fields). Uncheck "Classification" and "Location".
2. Ask: "Which dataset is most relevant for a steel sheet component?"
3. Verify the results appear — open browser DevTools Network tab, check the POST body has `"fields": ["description", "year"]` (or whichever remain checked).
4. Re-check all fields and repeat — verify the LLM response changes (more context → different/richer comments).

- [ ] **Step 10: Run full test suite**

```bash
python -m pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 11: Commit**

```bash
git add viewer/app.py viewer/query.py viewer/templates/index.html tests/test_query.py
git commit -m "feat: add field-selection dropdowns for search and LLM query"
```

---

## Summary of Deliverables

| Deliverable | Where to find |
|-------------|---------------|
| Title search | Existing input in toolbar on `/` |
| Keyword/synonym search | Second input in toolbar, `data-synonyms` + `data-summary` attrs |
| Search field selector | "⚙ Fields" dropdown next to keyword input |
| Dataset selection | Checkboxes on cards and list rows, sticky panel |
| LLM query | `POST /query` Flask route |
| Query engine | `viewer/query.py` (`build_prompt`, `parse_response`, `run_query`) |
| Query field selector | "⚙ Fields" dropdown in selection panel, `fields` param in prompt |
| Tests | `tests/test_query.py` (~27 unit + route tests) |
| Results table | Inline panel on `/` page, colour-coded relevance scores |

## Upgrade Note — Model Quality

The default model is `claude-haiku-4-5` (cheap, fast). For better semantic ranking of LCA datasets, pass `?model=claude-sonnet-4-6` as a query parameter to `/query`, or change `DEFAULT_QUERY_MODEL` in `viewer/query.py`. Sonnet understands materials science and LCA terminology significantly better than Haiku.
