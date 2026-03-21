# Sphera LCA Dataset Viewer — Module 3 Design Spec

**Date:** 2026-03-21
**Scope:** Local dataset viewer — terminal CLI + Flask web UI
**Reads from:** `dataset/output/*.json` (produced by Module 1)
**No new dependencies on core/ modules**

---

## Goal

Allow the user to browse and inspect downloaded Sphera LCA datasets without opening raw JSON files. Two interfaces:

1. **Terminal viewer** — quick CLI inspection of one dataset or a list of all
2. **Web UI** — card-based browser with collapsible detail view, runs locally via Flask

---

## Field Sections

All fields from the parsed JSON are grouped into display sections. Fields marked *dropped* are present in the JSON but not shown in the viewer (low value for inspection).

| Section | Fields |
|---|---|
| Identity | uuid, name_base, general_comment, synonyms, classification |
| Time | reference_year, valid_until |
| Location | location, geographical_representativeness_description |
| Technology | technology_description, technological_applicability |
| Modelling | dataset_type |
| Data Sources | data_cutoff_principles, data_selection_principles, supply_coverage_percent |
| DQI | dqi_overall_quality, dqi_technological_representativeness, dqi_time_representativeness, dqi_geographical_representativeness, dqi_completeness, dqi_precision, dqi_methodological_appropriateness |
| Notes | use_advice, reference_flows |
| Other | name_treatment_standards_routes, name_mix_and_location_types, name_functional_unit |
| *(dropped)* | time_description, mathematical_relations, lci_method_principle, lci_method_approaches, deviations_from_lci_method, modelling_constants |

---

## Architecture

```
view.py              — terminal viewer (standalone script)
viewer/
  app.py             — Flask app entry point
  templates/
    index.html       — card list view with search
    dataset.html     — detail view with collapsible sections
```

No changes to `core/`. Both tools read JSON files directly from `dataset/output/`.

---

## Terminal Viewer (`view.py`)

### Commands

```bash
python view.py                  # list all datasets (uuid + name_base)
python view.py <uuid>           # inspect one dataset (truncated long fields)
python view.py <uuid> --full    # inspect one dataset (full text, no truncation)
```

### MUST fields checked in summary header

All 14 fields from `MUST_FIELDS` in `core/parser.py` are checked for null and shown in the header table — even fields that are dropped from the display sections below (e.g. `lci_method_principle`, `lci_method_approaches`). The header is a data quality audit; the sections are a reading interface. These serve different purposes.

Fields checked: `uuid`, `name_base`, `synonyms`, `general_comment`, `location`,
`geographical_representativeness_description`, `reference_year`, `valid_until`,
`technology_description`, `dataset_type`, `lci_method_principle`,
`lci_method_approaches`, `dqi_overall_quality`, `classification`

### Output format for `python view.py <uuid>`

**Part 1 — Summary header (always shown):**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 LED SMD high-efficiency with lens max 0.5A
 UUID: 02d5eba7-3c71-4b93-90c9-fb8758528f57
 GLO · LCI result · 2025–2028
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 MUST FIELDS                          STATUS
 uuid                                 ✓
 name_base                            ✓
 classification                       ✓
 location                             ✓
 reference_year                       ✓
 valid_until                          ✓
 technology_description               ✓
 dataset_type                         ✓
 dqi_overall_quality                  ✓  Good
 ...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Part 2 — Full sections (printed below header, user scrolls terminal):**
- Each section printed with a bold heading
- Each field: `field_name: value`
- Null fields shown as `—`
- Long text fields (>200 chars): truncated with `[... N chars hidden — use --full to show]` (200 chars is intentionally shorter than the web threshold of 300 — terminal width makes long text harder to read)
- With `--full` flag: no truncation, full text printed for all fields
- Sections printed in order: Identity, Time, Location, Technology, Modelling, Data Sources, DQI, Notes, Other

### List mode (`python view.py`)

```
#    UUID                                    Name
1    02d5eba7-...                            LED SMD high-efficiency...
2    0a3e241f-...                            Al-capacitor SMD
...
27 datasets in dataset/output/
```

### Error handling

- Unknown UUID → print error + list available UUIDs
- `dataset/output/` empty or missing → print "No datasets found in dataset/output/"

---

## Web UI (`viewer/app.py`)

### Routes

| Route | Description |
|---|---|
| `GET /` | List view — all dataset cards |
| `GET /dataset/<uuid>` | Detail view — one dataset |

### List View (`index.html`)

- Search bar at top — filters cards client-side by `name_base` (no page reload)
- One card per dataset showing:
  - `name_base` (title)
  - `classification · location · reference_year`
  - Badges: `dataset_type`, `dqi_overall_quality`
- Click card → navigates to detail view
- Footer: total dataset count
- If `dataset/output/` is empty: show "No datasets found" message

### Detail View (`dataset.html`)

- Header: `name_base`, `uuid`
- **Expand all / Collapse all** toggle button
  - On page load: Identity, Time, Location, DQI sections are open; all others collapsed
  - Button label: shows "Collapse all" when all open, "Expand all" when all closed, "Expand all" when mixed
- 9 collapsible sections in order: Identity, Time, Location, Technology, Modelling, Data Sources, DQI, Notes, Other
- Each section:
  - Click section header to toggle open/closed
  - Long text fields (>300 chars): truncated, with a "Show more / Show less" inline toggle
  - Null fields shown as `—` in grey italic
- Back button → returns to list

### Running

```bash
cd viewer
python app.py
# Open http://localhost:5000
```

No external CSS frameworks — plain HTML + inline styles + vanilla JS only (no npm, no build step).

### Error handling

- Malformed or unreadable JSON file: skip the file, print warning to stderr, continue loading others
- Unknown UUID in `/dataset/<uuid>`: return 404 page with link back to list

---

## Testing

No automated tests for the viewer (display tool, not business logic). Verified manually:

- Terminal: `python view.py`, `python view.py <uuid>`, `python view.py <uuid> --full`
- Web: Flask app loads, list shows all datasets, search filters correctly, detail sections expand/collapse, expand all / collapse all works, "Show more" toggles on long text

---

## Out of Scope (V1.0)

- Authentication / multi-user
- Editing datasets
- Export from viewer (covered by Module 2 / CSV export idea)
- Deployment beyond localhost
