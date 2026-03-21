# Sphera LCA Dataset Viewer — Module 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two local viewers for Sphera LCA JSON datasets — a terminal CLI and a Flask web UI — both reading from `dataset/output/*.json`.

**Architecture:** A shared `viewer/sections.py` defines field groupings used by both interfaces. `view.py` is a standalone terminal script. `viewer/app.py` is a minimal Flask app with two routes (list + detail), served via plain HTML templates with vanilla JS — no external CSS frameworks, no build step.

**Tech Stack:** Python 3.10+, Flask, argparse, json (stdlib), pathlib (stdlib)

**Spec:** `doc/specs/2026-03-21-sphera-lca-module3-viewer-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `requirements.txt` | Modify | Add `flask>=3.0.0` |
| `viewer/__init__.py` | Create | Empty — marks viewer as package |
| `viewer/sections.py` | Create | Field section definitions + MUST_FIELDS list shared by terminal and web |
| `view.py` | Create | Terminal viewer CLI (list mode + inspect mode) |
| `viewer/app.py` | Create | Flask routes: `GET /` and `GET /dataset/<uuid>` |
| `viewer/templates/base.html` | Create | Shared HTML shell (nav, styles) |
| `viewer/templates/index.html` | Create | Card list view with search bar |
| `viewer/templates/dataset.html` | Create | Detail view with collapsible sections |

---

## Task 1: Shared Sections Module + Flask Dependency

**Files:**
- Modify: `requirements.txt`
- Create: `viewer/__init__.py`
- Create: `viewer/sections.py`

- [ ] **Step 1: Add Flask to requirements.txt**

```text
requests>=2.31.0
lxml>=5.0.0
pytest>=8.0.0
flask>=3.0.0
```

- [ ] **Step 2: Install Flask**

```bash
pip install flask
```

Expected: `Successfully installed flask-...`

- [ ] **Step 3: Create empty package marker**

Create `viewer/__init__.py` — empty file.

- [ ] **Step 4: Create viewer/sections.py**

```python
# Field groupings for the viewer — shared by terminal and web interfaces.
# Dropped fields (not shown): time_description, mathematical_relations,
# lci_method_principle, lci_method_approaches, deviations_from_lci_method,
# modelling_constants

SECTIONS = [
    ("Identity", [
        "uuid", "name_base", "general_comment", "synonyms", "classification",
    ]),
    ("Time", [
        "reference_year", "valid_until",
    ]),
    ("Location", [
        "location", "geographical_representativeness_description",
    ]),
    ("Technology", [
        "technology_description", "technological_applicability",
    ]),
    ("Modelling", [
        "dataset_type",
    ]),
    ("Data Sources", [
        "data_cutoff_principles", "data_selection_principles",
        "supply_coverage_percent",
    ]),
    ("DQI", [
        "dqi_overall_quality", "dqi_technological_representativeness",
        "dqi_time_representativeness", "dqi_geographical_representativeness",
        "dqi_completeness", "dqi_precision",
        "dqi_methodological_appropriateness",
    ]),
    ("Notes", [
        "use_advice", "reference_flows",
    ]),
    ("Other", [
        "name_treatment_standards_routes", "name_mix_and_location_types",
        "name_functional_unit",
    ]),
]

# MUST fields checked in terminal summary header (null audit).
# Subset of core/parser.py MUST_FIELDS — excludes lci_method_principle
# and lci_method_approaches (dropped from viewer as low value for inspection).
MUST_FIELDS = [
    "uuid", "name_base", "synonyms", "general_comment", "location",
    "geographical_representativeness_description", "reference_year",
    "valid_until", "technology_description", "dataset_type",
    "dqi_overall_quality", "classification",
]

# Sections open by default in web detail view
DEFAULT_OPEN = {"Identity", "Time", "Location", "DQI"}
```

- [ ] **Step 5: Verify import works**

```bash
python -c "from viewer.sections import SECTIONS, MUST_FIELDS, DEFAULT_OPEN; print(f'{len(SECTIONS)} sections, {len(MUST_FIELDS)} must fields')"
```

Expected: `9 sections, 12 must fields`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt viewer/__init__.py viewer/sections.py
git commit -m "feat: viewer package scaffold with field section definitions"
```

---

## Task 2: Terminal Viewer — List Mode + Header

**Files:**
- Create: `view.py`

- [ ] **Step 1: Create view.py with list mode and inspect header**

```python
import argparse
import json
import sys
from pathlib import Path

from viewer.sections import MUST_FIELDS, SECTIONS

OUTPUT_DIR = Path("dataset/output")
SEP = "━" * 50
FIELD_W = 28   # field name column width
VALUE_W = 20   # value column width


def _clip(text: str, width: int) -> str:
    """Clip text to width, appending '..' if truncated."""
    if text is None:
        return "-"
    s = str(text)
    if len(s) <= width:
        return s
    return s[: width - 2] + ".."


def load_all() -> list[dict]:
    """Load all JSON files from OUTPUT_DIR. Skips malformed files."""
    datasets = []
    if not OUTPUT_DIR.exists():
        return datasets
    for f in sorted(OUTPUT_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            datasets.append(data)
        except Exception as e:
            print(f"[WARN] skipping {f.name}: {e}", file=sys.stderr)
    return datasets


def load_one(uuid: str) -> dict | None:
    """Load a single dataset by UUID. Returns None if not found."""
    path = OUTPUT_DIR / f"{uuid}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] could not read {path.name}: {e}", file=sys.stderr)
        return None


def list_datasets() -> None:
    """Print a numbered list of all datasets."""
    datasets = load_all()
    if not datasets:
        print("No datasets found in dataset/output/")
        return
    print(f"{'#':<4} {'UUID':<38} Name")
    print("─" * 80)
    for i, d in enumerate(datasets, 1):
        uuid = _clip(d.get("uuid", "—"), 36)
        name = _clip(d.get("name_base") or "—", 38)
        print(f"{i:<4} {uuid:<38} {name}")
    print(f"\n{len(datasets)} datasets in {OUTPUT_DIR}/")


def print_header(data: dict) -> None:
    """Print the summary header block."""
    name = data.get("name_base") or "—"
    uuid = data.get("uuid") or "—"
    location = data.get("location") or "—"
    ref_year = data.get("reference_year")
    valid_until = data.get("valid_until")
    dataset_type = data.get("dataset_type") or "—"

    year_range = f"{ref_year}–{valid_until}" if ref_year and valid_until else (str(ref_year or valid_until or "—"))

    print(SEP)
    print(f" {name}")
    print(f" UUID: {uuid}")
    print(f" {location} · {year_range}")
    print(f" {dataset_type}")
    print(SEP)
    print(f" {'MUST FIELDS':<{FIELD_W}} VALUE")
    for field in MUST_FIELDS:
        raw = data.get(field)
        field_label = _clip(field, FIELD_W)
        value_label = _clip(str(raw) if raw is not None else None, VALUE_W)
        print(f" {field_label:<{FIELD_W}} {value_label}")
    print(SEP)
```

- [ ] **Step 2: Verify list mode runs**

```bash
python view.py
```

Expected: numbered list of all datasets in `dataset/output/`.

- [ ] **Step 3: Verify header prints for a known UUID**

Pick any UUID from the list above and run:
```bash
python view.py 02d5eba7-3c71-4b93-90c9-fb8758528f57
```

Expected: the header block prints — name, UUID, location/years, dataset_type, then the MUST FIELDS table with values clipped to 20 chars and `-` for any nulls.

- [ ] **Step 4: Commit**

```bash
git add view.py
git commit -m "feat: terminal viewer list mode and summary header"
```

---

## Task 3: Terminal Viewer — Detail Sections

**Files:**
- Modify: `view.py`

- [ ] **Step 1: Add section printing and CLI entry point to view.py**

Append to `view.py`:

```python
def print_sections(data: dict, full: bool = False) -> None:
    """Print all field sections below the header."""
    TRUNC = 200
    for section_name, fields in SECTIONS:
        print(f"\n {'[ ' + section_name + ' ]':─<48}")
        for field in fields:
            raw = data.get(field)
            if raw is None:
                print(f"  {field}: —")
            else:
                text = str(raw)
                if not full and len(text) > TRUNC:
                    hidden = len(text) - TRUNC
                    text = text[:TRUNC] + f" [... {hidden} chars hidden — use --full to show]"
                print(f"  {field}: {text}")


def inspect_dataset(uuid: str, full: bool = False) -> None:
    """Inspect a single dataset by UUID."""
    data = load_one(uuid)
    if data is None:
        print(f"[ERROR] UUID not found: {uuid}")
        print()
        list_datasets()
        return
    print_header(data)
    print_sections(data, full=full)


def main() -> None:
    parser = argparse.ArgumentParser(description="View Sphera LCA datasets.")
    parser.add_argument("uuid", nargs="?", help="Dataset UUID to inspect")
    parser.add_argument("--full", action="store_true", help="Show full text without truncation")
    args = parser.parse_args()

    if args.uuid:
        inspect_dataset(args.uuid, full=args.full)
    else:
        list_datasets()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify sections print for a known UUID**

```bash
python view.py 02d5eba7-3c71-4b93-90c9-fb8758528f57
```

Expected: header block followed by 9 sections. Long text fields show truncation notice.

- [ ] **Step 3: Verify --full shows untruncated text**

```bash
python view.py 02d5eba7-3c71-4b93-90c9-fb8758528f57 --full
```

Expected: same output but technology_description and other long fields printed in full.

- [ ] **Step 4: Verify unknown UUID shows error + list**

```bash
python view.py 00000000-0000-0000-0000-000000000000
```

Expected: `[ERROR] UUID not found: ...` followed by the dataset list.

- [ ] **Step 5: Commit**

```bash
git add view.py
git commit -m "feat: terminal viewer detail sections with --full flag"
```

---

## Task 4: Flask App + List View

**Files:**
- Create: `viewer/app.py`
- Create: `viewer/templates/base.html`
- Create: `viewer/templates/index.html`

- [ ] **Step 1: Create viewer/app.py**

```python
import json
import sys
from pathlib import Path

from flask import Flask, render_template, abort

from viewer.sections import SECTIONS, DEFAULT_OPEN

OUTPUT_DIR = Path(__file__).parent.parent / "dataset/output"

app = Flask(__name__)


def load_all() -> list[dict]:
    datasets = []
    if not OUTPUT_DIR.exists():
        return datasets
    for f in sorted(OUTPUT_DIR.glob("*.json")):
        try:
            datasets.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"[WARN] skipping {f.name}: {e}", file=sys.stderr)
    return datasets


def load_one(uuid: str) -> dict | None:
    path = OUTPUT_DIR / f"{uuid}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] could not read {path.name}: {e}", file=sys.stderr)
        return None


@app.route("/")
def index():
    datasets = load_all()
    return render_template("index.html", datasets=datasets)


@app.route("/dataset/<uuid>")
def dataset_detail(uuid):
    data = load_one(uuid)
    if data is None:
        abort(404)
    return render_template(
        "dataset.html",
        data=data,
        sections=SECTIONS,
        default_open=DEFAULT_OPEN,
    )


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

- [ ] **Step 2: Create viewer/templates/base.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Sphera LCA Viewer{% endblock %}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, sans-serif; background: #f5f5f5; color: #222; }
    a { color: #0057b8; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .nav { background: #1a1a2e; color: #fff; padding: 12px 24px; display: flex; align-items: center; gap: 16px; }
    .nav a { color: #a8dadc; font-weight: bold; }
    .container { max-width: 1100px; margin: 0 auto; padding: 24px; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .badge-type { background: #dbeafe; color: #1d4ed8; }
    .badge-dqi-good { background: #d1fae5; color: #065f46; }
    .badge-dqi-very-good { background: #a7f3d0; color: #064e3b; }
    .badge-dqi-other { background: #fef3c7; color: #92400e; }
    .null { color: #999; font-style: italic; }
  </style>
</head>
<body>
  <nav class="nav">
    <a href="/">Sphera LCA Viewer</a>
  </nav>
  <div class="container">
    {% block content %}{% endblock %}
  </div>
</body>
</html>
```

- [ ] **Step 3: Create viewer/templates/index.html**

```html
{% extends "base.html" %}
{% block title %}Datasets — Sphera LCA Viewer{% endblock %}
{% block content %}
<div style="margin-bottom:16px; display:flex; align-items:center; gap:16px;">
  <h1 style="font-size:22px;">Datasets</h1>
  <input id="search" type="text" placeholder="Search by name..." oninput="filterCards()"
    style="padding:6px 12px; border:1px solid #ccc; border-radius:4px; font-size:14px; width:300px;">
</div>

{% if not datasets %}
  <p style="color:#666;">No datasets found in <code>dataset/output/</code>. Run the downloader first.</p>
{% else %}
  <div id="cards" style="display:grid; grid-template-columns: repeat(auto-fill, minmax(340px,1fr)); gap:16px;">
    {% for d in datasets %}
    <a href="/dataset/{{ d.uuid }}" style="display:block; text-decoration:none; color:inherit;"
       data-name="{{ (d.name_base or '') | lower }}">
      <div style="background:#fff; border:1px solid #ddd; border-radius:8px; padding:16px;
                  box-shadow:0 1px 3px rgba(0,0,0,.06); transition: box-shadow .15s;"
           onmouseover="this.style.boxShadow='0 4px 12px rgba(0,0,0,.12)'"
           onmouseout="this.style.boxShadow='0 1px 3px rgba(0,0,0,.06)'">
        <div style="font-weight:bold; font-size:15px; margin-bottom:6px; line-height:1.4;">
          {{ d.name_base or "—" }}
        </div>
        <div style="font-size:12px; color:#666; margin-bottom:10px;">
          {{ d.classification or "" }}{% if d.classification and d.location %} · {% endif %}
          {{ d.location or "" }}{% if d.reference_year %} · {{ d.reference_year }}{% endif %}
        </div>
        <div style="display:flex; gap:6px; flex-wrap:wrap;">
          {% if d.dataset_type %}
            <span class="badge badge-type">{{ d.dataset_type }}</span>
          {% endif %}
          {% if d.dqi_overall_quality %}
            {% set dqi_class = "badge-dqi-very-good" if "very" in (d.dqi_overall_quality | lower) else "badge-dqi-good" if "good" in (d.dqi_overall_quality | lower) else "badge-dqi-other" %}
            <span class="badge {{ dqi_class }}">DQI: {{ d.dqi_overall_quality }}</span>
          {% endif %}
        </div>
      </div>
    </a>
    {% endfor %}
  </div>
  <p style="margin-top:20px; color:#666; font-size:13px;">{{ datasets | length }} datasets loaded</p>
{% endif %}

<script>
function filterCards() {
  const q = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('#cards > a').forEach(card => {
    card.style.display = card.dataset.name.includes(q) ? '' : 'none';
  });
}
</script>
{% endblock %}
```

- [ ] **Step 4: Create viewer/templates/404.html**

```html
{% extends "base.html" %}
{% block title %}Not Found{% endblock %}
{% block content %}
<h2 style="margin-bottom:12px;">Dataset not found</h2>
<a href="/">← Back to list</a>
{% endblock %}
```

- [ ] **Step 5: Run Flask and verify list view**

```bash
python viewer/app.py
```

Open `http://localhost:5000` in browser. Expected: cards for each dataset in `dataset/output/`. Search bar filters by name as you type.

- [ ] **Step 6: Commit**

```bash
git add viewer/app.py viewer/templates/base.html viewer/templates/index.html viewer/templates/404.html
git commit -m "feat: Flask list view with search and dataset cards"
```

---

## Task 5: Flask Detail View

**Files:**
- Create: `viewer/templates/dataset.html`

- [ ] **Step 1: Create viewer/templates/dataset.html**

```html
{% extends "base.html" %}
{% block title %}{{ data.name_base or data.uuid }} — Sphera LCA Viewer{% endblock %}
{% block content %}

<div style="margin-bottom:16px;">
  <a href="/" style="font-size:13px;">← Back to list</a>
</div>

<div style="background:#fff; border:1px solid #ddd; border-radius:8px; padding:20px; margin-bottom:20px;">
  <h1 style="font-size:20px; margin-bottom:6px; line-height:1.4;">{{ data.name_base or "—" }}</h1>
  <p style="font-size:12px; color:#888;">UUID: {{ data.uuid or "—" }}</p>
</div>

<div style="margin-bottom:16px; display:flex; justify-content:flex-end;">
  <button id="toggle-all" onclick="toggleAll()"
    style="padding:6px 16px; border:1px solid #ccc; border-radius:4px;
           background:#fff; cursor:pointer; font-size:13px;">
    Collapse all
  </button>
</div>

{% for section_name, fields in sections %}
{% set is_open = section_name in default_open %}
<div class="section" style="background:#fff; border:1px solid #ddd; border-radius:8px; margin-bottom:10px; overflow:hidden;">
  <div onclick="toggleSection(this)"
       style="padding:12px 16px; cursor:pointer; font-weight:bold; font-size:14px;
              background:{% if is_open %}#f0f4ff{% else %}#fafafa{% endif %};
              display:flex; justify-content:space-between; align-items:center;
              border-bottom:{% if is_open %}1px solid #ddd{% else %}none{% endif %};">
    <span>{{ section_name }}</span>
    <span class="arrow" style="font-size:12px; color:#666;">{% if is_open %}▼{% else %}▶{% endif %}</span>
  </div>
  <div class="section-body" style="display:{% if is_open %}block{% else %}none{% endif %}; padding:12px 16px;">
    <table style="width:100%; border-collapse:collapse; font-size:13px;">
      {% for field in fields %}
      {% set val = data.get(field) %}
      <tr style="border-bottom:1px solid #f0f0f0;">
        <td style="padding:6px 8px 6px 0; color:#555; width:260px; vertical-align:top; white-space:nowrap;">
          {{ field }}
        </td>
        <td style="padding:6px 0; vertical-align:top;">
          {% if val is none or val == "" %}
            <span class="null">—</span>
          {% elif val is iterable and val is not string %}
            <ul style="margin:0; padding-left:18px;">
              {% for item in val %}<li>{{ item }}</li>{% endfor %}
            </ul>
          {% elif val | string | length > 300 %}
            <span class="truncated">{{ val | string | truncate(300, true, '') }}</span>
            <span class="full-text" style="display:none;">{{ val }}</span>
            <a href="#" onclick="toggleText(this); return false;"
               style="font-size:12px; display:block; margin-top:4px;">Show more</a>
          {% else %}
            {{ val }}
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </table>
  </div>
</div>
{% endfor %}

<script>
function toggleSection(header) {
  const body = header.nextElementSibling;
  const arrow = header.querySelector('.arrow');
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : 'block';
  arrow.textContent = open ? '▶' : '▼';
  header.style.background = open ? '#fafafa' : '#f0f4ff';
  header.style.borderBottom = open ? 'none' : '1px solid #ddd';
  updateToggleButton();
}

function toggleAll() {
  const sections = document.querySelectorAll('.section');
  const anyOpen = [...sections].some(s => s.querySelector('.section-body').style.display !== 'none');
  sections.forEach(s => {
    const body = s.querySelector('.section-body');
    const arrow = s.querySelector('.arrow');
    const header = s.querySelector('[onclick="toggleSection(this)"]');
    body.style.display = anyOpen ? 'none' : 'block';
    arrow.textContent = anyOpen ? '▶' : '▼';
    header.style.background = anyOpen ? '#fafafa' : '#f0f4ff';
    header.style.borderBottom = anyOpen ? 'none' : '1px solid #ddd';
  });
  updateToggleButton();
}

function updateToggleButton() {
  const sections = document.querySelectorAll('.section');
  const openCount = [...sections].filter(s => s.querySelector('.section-body').style.display !== 'none').length;
  const btn = document.getElementById('toggle-all');
  btn.textContent = openCount === sections.length ? 'Collapse all' : 'Expand all';
}

function toggleText(link) {
  const td = link.parentElement;
  const trunc = td.querySelector('.truncated');
  const full = td.querySelector('.full-text');
  const showing = full.style.display !== 'none';
  trunc.style.display = showing ? '' : 'none';
  full.style.display = showing ? 'none' : '';
  link.textContent = showing ? 'Show more' : 'Show less';
}
</script>
{% endblock %}
```

- [ ] **Step 2: Verify detail view loads**

With Flask running (`python viewer/app.py`), click any card from the list view.

Expected:
- Name and UUID in header
- 9 collapsible sections; Identity, Time, Location, DQI open by default; others collapsed
- Click a section header → toggles open/closed
- "Expand all" / "Collapse all" button works
- Long fields (e.g. `technology_description`) show truncated text with "Show more" link
- Null fields show `—` in grey italic

- [ ] **Step 3: Verify 404 for unknown UUID**

Navigate to `http://localhost:5000/dataset/00000000-0000-0000-0000-000000000000`.

Expected: "Dataset not found" page with link back to list.

- [ ] **Step 4: Commit**

```bash
git add viewer/templates/dataset.html
git commit -m "feat: Flask detail view with collapsible sections and show more"
```

---

## Task 6: Final Wiring + Manual Verification

- [ ] **Step 1: Run full terminal verification**

```bash
python view.py
python view.py <any-uuid>
python view.py <any-uuid> --full
python view.py 00000000-0000-0000-0000-000000000000
```

Check:
- List shows all datasets with numbers, UUIDs, names
- Header shows name / UUID / location·years / dataset_type on separate lines
- MUST FIELDS table: values clipped to 20 chars, `-` for nulls, `..` on clips
- Sections print in order with long text truncated at 200 chars (default) or full (`--full`)
- Unknown UUID prints error + redirects to list

- [ ] **Step 2: Run full web verification**

Start: `python viewer/app.py` and open `http://localhost:5000`

Check:
- All cards load with name, classification·location·year, badges
- Search filters cards by name as you type
- Click card → detail view opens
- Sections: Identity, Time, Location, DQI open by default
- Click section header → toggles
- "Collapse all" collapses all; "Expand all" expands all; mixed state shows "Expand all"
- Long fields show "Show more" / "Show less" toggle
- Null fields show `—` in grey
- Back link returns to list

- [ ] **Step 3: Add .superpowers to .gitignore**

```bash
echo ".superpowers/" >> .gitignore
git add .gitignore
```

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: Module 3 viewer complete — terminal CLI + Flask web UI"
```
