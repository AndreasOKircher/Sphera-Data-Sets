# Sphera LCA Dataset Toolkit

A Python toolkit for downloading, parsing, viewing, and LLM-enriching Sphera LCA datasets in ILCD XML format.

---

## Purpose

Sphera publishes Life Cycle Assessment (LCA) datasets through a web portal. Each dataset describes a product or process — its technology, geography, time period, data quality, and environmental modelling approach. The raw format is ILCD XML, which is verbose and difficult to work with directly.

This toolkit:
1. **Downloads** the XML files from the Sphera portal (requires session authentication)
2. **Parses** the XML into clean flat JSON records
3. **Views** the data — in a terminal or a local web browser
4. **Enriches** the `technology_description` field using the Claude API, producing a structured plain-language summary and a formatted version

The primary dataset used during development is the **Sphera Electronics & Electrics (EE)** database, containing passive electronic components (capacitors, resistors, inductors, transistors, ICs, oscillators, etc.).

---

## The XML Files — ILCD Format

Sphera datasets follow the **ILCD (International Life Cycle Data) Format 1.1**, a standard maintained by the Joint Research Centre (JRC) of the European Commission.

Each XML file represents a single process or product dataset (`processDataSet`). Key structural characteristics:

- The files are `metaDataOnly="true"` — they contain all descriptive and modelling metadata but **no exchange flow data** (inputs/outputs quantities are not available)
- Images (process flow diagrams, product photos) are **not embedded** in the process XML. They are referenced by UUID pointing to separate `sources/` XML files
- Language: most text fields exist in English (`xml:lang="en"`) — the parser selects English where available
- Namespaces: `ilcd:` for process-specific elements, `common:` for shared ILCD elements

### Official References

| Resource | Description |
|---|---|
| [ILCD ProcessDataSet Format 1.1](https://eplca.jrc.ec.europa.eu/LCDN/downloads/ILCD_Format_1.1_Documentation/ILCD_ProcessDataSet.html) | Full field documentation |
| [ILCD Developer Overview](https://eplca.jrc.ec.europa.eu/LCDN/developerILCDDataFormat.html) | Schema overview for developers |
| [European Platform on LCA](https://eplca.jrc.ec.europa.eu/ilcd.html) | ILCD home, downloads |
| [ILCD Guidance Document PDF](https://eplca.jrc.ec.europa.eu/uploads/QMS_H08_ENSURE_ILCD_GuidanceDocumentationLCADataSets_Version1-1Beta_2011_ISBN_clean.pdf) | Detailed guidance v1.1 beta |

---

## Fields Extracted

Fields are split into two tiers. Both tiers are extracted and saved to JSON.

**MUST fields** — core contract, shown in terminal header and web list view:

| JSON Key | ILCD Source | Description |
|---|---|---|
| `uuid` | `common:UUID` | Unique dataset identifier |
| `name_base` | `baseName` | Primary product/process name |
| `synonyms` | `common:synonyms` | Alternative names |
| `general_comment` | `common:generalComment` | High-level dataset description |
| `location` | `locationOfOperationSupplyOrProduction[@location]` | Country/region code (e.g. `GLO`, `DE`) |
| `geographical_representativeness_description` | `descriptionOfRestrictions` | Scope of geographic coverage |
| `reference_year` | `common:referenceYear` | Data reference year |
| `valid_until` | `common:dataSetValidUntil` | Dataset expiry year |
| `technology_description` | `technologyDescriptionAndIncludedProcesses` | Main process description (often 1,000–1,500 words) |
| `dataset_type` | `typeOfDataSet` | e.g. `LCI result`, `Partly terminated system` |
| `dqi_overall_quality` | `dataQualityIndicator[@name="Overall quality"]` | Overall data quality rating |
| `classification` | `common:class` (all levels joined) | Category hierarchy, e.g. `Electronics / Passive components` |

**NICE-TO-HAVE fields** — additional context, shown in full detail view:

`name_treatment_standards_routes`, `name_mix_and_location_types`, `name_functional_unit`,
`use_advice`, `reference_flows`, `time_description`, `technological_applicability`,
`mathematical_relations`, `lci_method_principle`, `lci_method_approaches`,
`deviations_from_lci_method`, `modelling_constants`, `data_cutoff_principles`,
`data_selection_principles`, `supply_coverage_percent`, and all 6 individual DQI indicators
(`dqi_technological_representativeness`, `dqi_time_representativeness`,
`dqi_geographical_representativeness`, `dqi_completeness`, `dqi_precision`,
`dqi_methodological_appropriateness`).

**Excluded:** exchange flows (not available in metaDataOnly files), completeness section, compliance section, administrative info.

Full field mapping with XPaths and examples: `doc/field-mapping-draft.md`

---

## Workflow

```
1. Download
   download.py --urls urls.txt --cookie-file cookie.txt
        │
        ▼
   dataset/output/{uuid}.xml      ← raw ILCD XML, never modified
   dataset/output/{uuid}.json     ← flat parsed JSON

2. Re-parse (optional, if parser changes)
   reparse.py --all --force
        │
        ▼
   dataset/output/{uuid}.json     ← regenerated from saved XML

3. View
   view.py                        ← terminal list
   view.py <uuid>                 ← terminal detail
   viewer/app.py                  ← web browser at localhost:5000

4. Enrich
   enrich.py --all --workers 4
        │
        ├── SHA-256 dedup scan (no API call for duplicate texts)
        ├── 2 parallel Claude API calls per unique text
        │       Call 1: plain-language summary (max_tokens=300)
        │       Call 2: markdown-formatted version (max_tokens=16000)
        └── word/char count verification
             │
             ▼
   dataset/enriched/{uuid}.json   ← enrichment sidecar, original untouched
   dataset/dedup/text_cache.json  ← hash → uuid dedup cache
```

---

## LLM Enrichment — Calls and Verification

### Two API Calls per Unique Text

Both calls are made in parallel (`ThreadPoolExecutor`) against the `technology_description` field.

**Call 1 — Summary** (`max_tokens=300`)

System prompt:
```
You are a technical writer specializing in Life Cycle Assessment (LCA).
Your task is to summarize the text provided by the user.
Always output ONLY the structured summary below — never add introductory sentences,
meta-comments, caveats, or any text outside the format.
Do not comment on the nature or quality of the input. Just summarize it.

Use exactly this markdown format:

**Process:** One sentence describing what the process, product, or dataset covers.
**Output:** One sentence on what it produces, its function, or what the data represents.
**Key characteristics:**
- Key technical feature, scope, or component type
- Data quality, coverage, or methodology note (only if mentioned)
- Geographic or temporal scope (only if mentioned)
```

**Call 2 — Format** (`max_tokens=16000`)

System prompt:
```
You are a technical editor. Reformat the following text for readability by adding
paragraph breaks, markdown headers (##) for major sections, and bold (**) for key
terms. Do NOT change, add, or remove any words. Return only the reformatted
markdown, nothing else.
```

### Word and Character Count Verification

Before saving any enriched file, the formatted text is verified against the original to ensure the LLM did not add or remove content.

**Normalisation** (`clean_text`): both texts are processed identically before counting —
newlines (`\n`, `\r`) are replaced with a space to preserve word boundaries;
formatting markers (`#`, `*`, `_`, backtick) are stripped entirely.

**Word count**: whitespace-split token count of the cleaned text.
**Char count**: `len()` of the cleaned text.

If either word count deviation **or** char count deviation exceeds the threshold (default **6%**, configurable via `--threshold`), the enriched file is **not saved** and the dataset is reported as `[FAIL]`. The threshold can be raised for models that add structural markdown words.

### Deduplication

Many LCA datasets (especially electronics components from the same manufacturer) share identical `technology_description` text. Before making any API call, `enrich.py --all` pre-scans all datasets and builds a SHA-256 hash map of normalised texts. Datasets sharing a hash are assigned the same enriched content with a single API call. The cache persists in `dataset/dedup/text_cache.json`.

---

## Input / Output

| Item | Path | Description |
|---|---|---|
| Input: URL list | any `.txt` file | One Sphera dataset URL per line |
| Input: Session cookie | `cookie.txt` (gitignored) | Browser session cookie for Sphera portal |
| Input: API key | `.env` → `ANTHROPIC_API_KEY` | Anthropic API key for enrichment |
| Raw XML | `dataset/output/{uuid}.xml` | Downloaded ILCD XML, never modified |
| Parsed JSON | `dataset/output/{uuid}.json` | Flat record, 33 fields |
| Enriched sidecar | `dataset/enriched/{uuid}.json` | 12 enrichment fields, added alongside original |
| Dedup cache | `dataset/dedup/text_cache.json` | SHA-256 hash → UUID mapping |

### Enriched sidecar JSON keys

```json
{
  "uuid": "02d5eba7-...",
  "enriched_at": "2026-03-21T10:30:00+00:00",
  "dedup_source": "...",                          ← only present if copied from duplicate

  "technology_description_word_count": 1250,
  "technology_description_formatted_word_count": 1249,
  "technology_description_word_count_diff": -1,
  "technology_description_word_count_diff_pct": 0.08,

  "technology_description_char_count": 7423,
  "technology_description_formatted_char_count": 7421,
  "technology_description_char_count_diff": -2,
  "technology_description_char_count_diff_pct": 0.03,

  "technology_description_summary": "**Process:** ...",
  "technology_description_formatted": "## Overview\n\n..."
}
```

---

## Tools and Helpers

| Tool | How to run | Purpose |
|---|---|---|
| `download.py` | `python download.py --urls urls.txt --cookie-file cookie.txt` | Download datasets from Sphera portal |
| `reparse.py` | `python reparse.py --all` | Re-parse saved XML files → regenerate JSON without re-downloading |
| `enrich.py` | `python enrich.py --all --workers 4` | Enrich all datasets using Claude API |
| `view.py` | `python view.py` / `python view.py <uuid>` | Terminal viewer: list all datasets or inspect one |
| `viewer/app.py` | `python viewer/app.py` | Web viewer on localhost:5000 |
| `sphera-view.exe` | double-click or run from terminal | Standalone terminal viewer (no Python needed) |
| `sphera-viewer.exe` | double-click | Standalone web viewer — opens browser automatically |
| `build/build_view.bat` | run from project root | Build `sphera-view.exe` using PyInstaller |
| `build/build_viewer.bat` | run from project root | Build `sphera-viewer.exe` using PyInstaller |

### Key CLI flags

**`download.py`**
- `--url <url>` / `--urls <file>` — single URL or file of URLs
- `--cookie <value>` / `--cookie-file <file>` — Sphera session cookie
- `--output <dir>` — output directory (default: `dataset/output/`)

**`reparse.py`**
- `--uuid <uuid>` / `--all` — single or all
- `--force` — overwrite existing JSON

**`enrich.py`**
- `--uuid <uuid>` / `--all` — single or all
- `--force` — re-enrich already enriched datasets
- `--workers N` — parallel dataset workers (default: 4)
- `--model <id>` — Claude model (default: `claude-haiku-4-5-20251001`)
- `--threshold <pct>` — max word/char deviation % before FAIL (default: 6.0)

**`view.py`**
- `<uuid>` — inspect a specific dataset
- `--full` — show full text fields without truncation

---

## File Reference

```
project root
├── download.py                     Download + parse pipeline CLI
├── reparse.py                  Re-parse saved XMLs → regenerate JSON
├── enrich.py                   LLM enrichment CLI
├── view.py                     Terminal viewer
├── requirements.txt            Python dependencies
├── .env.example                API key template (copy to .env)
│
├── core/
│   ├── downloader.py           HTTP fetch with cookie/User-Agent auth
│   ├── parser.py               ILCD XML → flat dict (lxml, XPath)
│   ├── exporter.py             Write .xml + .json to output dir
│   └── enricher.py             clean_text, count_words, count_chars,
│                               verify_counts, enrich_dataset,
│                               SUMMARY_SYSTEM / FORMAT_SYSTEM prompts
│
├── viewer/
│   ├── app.py                  Flask web app (routes, data loading)
│   ├── sections.py             Field groupings: SECTIONS, MUST_FIELDS,
│   │                           DEFAULT_OPEN (shared by terminal + web)
│   └── templates/
│       ├── base.html           Nav bar, shared CSS, layout shell
│       ├── index.html          Dataset list: cards + table view, search
│       ├── dataset.html        Dataset detail: collapsible sections,
│       │                       enrichment summary card, formatted/original
│       │                       toggle, inline markdown renderer
│       └── 404.html            Error page
│
├── tests/
│   ├── test_parser.py          Parser unit tests
│   ├── test_exporter.py        Exporter unit tests
│   └── test_enricher.py        Enricher unit tests (mocked API, 47 tests)
│
├── dataset/
│   ├── output/                 Downloaded XMLs + parsed JSONs
│   ├── enriched/               LLM enrichment sidecars (gitignored)
│   └── dedup/                  SHA-256 text dedup cache
│
├── build/
│   ├── build_view.bat          PyInstaller build script for terminal viewer
│   └── build_viewer.bat        PyInstaller build script for web viewer
│
├── dist/
│   ├── sphera-view.exe         Standalone terminal viewer
│   └── sphera-viewer.exe       Standalone web viewer (opens browser auto)
│
└── doc/
    ├── field-mapping-draft.md  Full ILCD field table with XPaths + priority
    └── specs/ plans/           Design specs and implementation plans
```

---

## Setup

```bash
# Python 3.12 recommended (best PyInstaller support)
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# Add your Anthropic API key
copy .env.example .env
# edit .env: ANTHROPIC_API_KEY=sk-ant-...
```

Run tests:
```bash
.venv\Scripts\pytest tests/ -v
```

---

## Authentication

The Sphera portal uses Cloudflare protection. Downloading requires:
1. Log in to the Sphera portal in your browser
2. Copy the session cookie from browser DevTools (F12 → Network → any request → Cookie header)
3. Save to `cookie.txt` (gitignored)

```bash
python download.py --urls urls.txt --cookie-file cookie.txt
```

---

## Outlook — Configurable Field Extraction

Currently the XML → JSON field mapping is hardcoded in `core/parser.py`. A planned future improvement is to drive field extraction from a **YAML configuration file**, so new fields can be added without modifying Python code:

```yaml
fields:
  uuid:
    xpath: ".//common:UUID"
    type: text
  reference_year:
    xpath: ".//common:referenceYear"
    type: int
```

About 80% of fields are simple `text` or `attr` extractions that fit this pattern directly. The remaining 20% are special cases requiring Python logic (DQI indicator loop, classification hierarchy concatenation, supply coverage float parsing, mathematical_relations fallback XPath) and would be handled as named hooks alongside the config.

This enables different field profiles for different Sphera dataset categories (electronics, metals, plastics, energy) without code changes. A design document will be written before implementation.
