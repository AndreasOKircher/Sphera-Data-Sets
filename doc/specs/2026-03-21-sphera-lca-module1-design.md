# Sphera LCA Dataset Compilation — Module 1 Design Spec

> Version: 1.0
> Date: 2026-03-21
> Status: Awaiting user review

---

## Overview

A Python command-line tool that downloads Sphera LCA (Life Cycle Assessment) datasets from a public web database, parses the ILCD XML format, and exports each dataset as both a raw XML file and a simplified flat JSON file for further processing (LLM pipelines, reporting, analysis).

Datasets are served by Sphera at URLs of the form:
```
https://lcadatabase.sphera.com/2026/xml-data/processes/<uuid>.xml
```

These XML files follow the **ILCD Format 1.1** standard (International Reference Life Cycle Data System), maintained by the Joint Research Centre (JRC) of the European Commission.

---

## Scope

**In scope (Module 1, V1.0):**
- Download datasets from a single URL or a batch file of URLs
- Parse ILCD XML and extract a defined set of fields
- Export raw XML (untouched) and simplified flat JSON per dataset
- Error handling with a fail report for re-runs
- Overwrite warnings

**Out of scope (future modules):**
- LLM beautification and abstraction (Module 2)
- Dataset viewer (Module 3)
- CSV/XLS batch export (V1.1)
- Configurable field selection via config file (future V1.X)
- Image/diagram handling (V1.4)

---

## Project Structure

```
Sphera-Data-Sets/
├── core/
│   ├── downloader.py     # fetch URLs, return raw XML string
│   ├── parser.py         # parse ILCD XML → flat Python dict
│   └── exporter.py       # write .xml and .json output files
├── dataset/
│   ├── input/            # URL list files (.txt), one URL per line
│   └── output/           # downloaded datasets + fail reports
├── tests/
│   ├── sample_dataset.xml  # real Sphera XML used as test fixture
│   ├── test_downloader.py
│   ├── test_parser.py
│   └── test_exporter.py
├── doc/                  # developer notes, field mapping, specs, plans
│   ├── field-mapping-draft.md
│   ├── specs/            # design specs
│   └── plans/            # implementation plans
├── idea/                 # todos and background notes
├── ressources/           # sample URL lists (existing)
├── scripts/              # batch scripts if needed
├── .env                  # API keys (OpenAI, for Module 2)
├── requirements.txt
└── download.py               # CLI entry point
```

---

## CLI Interface

Single entry point: `download.py`

```bash
# Single URL
python download.py --url https://lcadatabase.sphera.com/2026/xml-data/processes/<uuid>.xml

# Batch from file (one URL per line)
python download.py --urls dataset/input/my_urls.txt

# With custom output directory
python download.py --urls dataset/input/my_urls.txt --output dataset/output/
```

**Rules:**
- `--url` and `--urls` are mutually exclusive
- `--output` is optional; defaults to `dataset/output/`
- If output directory does not exist, create it automatically

---

## Data Flow

```
URL(s)
  │
  ▼
downloader.py
  └─ HTTP GET via requests
  └─ Returns raw XML string (no file I/O)
  │
  ▼
parser.py
  └─ Parse with lxml.etree
  └─ Resolve ILCD namespaces internally
  └─ Extract fields → flat Python dict
  └─ Missing fields → None (no crash)
  │
  ▼
exporter.py
  └─ Check for existing files → warn if overwriting
  └─ Write <uuid>.xml (raw bytes, untouched)
  └─ Write <uuid>.json (flat, indent=2)
  │
  ▼
Log result: [OK] or [FAIL]
```

---

## Output Files

**Per dataset, two files written to output directory:**

| File | Content |
|---|---|
| `<uuid>.xml` | Raw XML exactly as downloaded — no reformatting |
| `<uuid>.json` | Flat JSON with extracted fields, `indent=2` |

**Fail report (only written if any failures occurred):**

| File | Content |
|---|---|
| `failed_urls_<YYYY-MM-DD_HHmmss>.txt` | One failed URL per line — same format as input, ready to re-run |

---

## JSON Field Mapping

See full field table with XML field names, JSON keys, and priorities in:
`doc/field-mapping-draft.md`

**Summary:**

- **MUST fields** (`✅`) — always present in JSON; core contract for downstream LLM use
- **NICE TO HAVE fields** (`🔵`) — present in JSON; extended context for human review
- **EXCLUDED fields** (`❌`) — not exported (Completeness, Compliance, Admin info, Flows)

**JSON structure example:**
```json
{
  "uuid": "9f2f5c2f-f304-4de0-8988-b0eaccdf7dff",
  "name_base": "Capacitor Al-capacitor SMD (2.54g) D12.5x13.5",
  "name_treatment_standards_routes": "technology mix",
  "name_mix_and_location_types": "production mix, at plant",
  "name_functional_unit": "(2.54g) D12.5x13.5",
  "synonyms": "electrolytic capacitor, SMD cap",
  "classification": "Electronics / Passive components",
  "general_comment": "This dataset represents a cradle-to-gate...",
  "use_advice": "This dataset should be used for...",
  "reference_flows": "1 piece Al-capacitor SMD 10µF...",
  "reference_year": 2025,
  "valid_until": 2028,
  "time_description": "annual average",
  "location": "GLO",
  "geographical_representativeness_description": "Global dataset; production data primarily from China...",
  "technology_description": "The manufacturing of aluminum capacitors involves...",
  "technological_applicability": "Used in consumer electronics, automotive...",
  "mathematical_relations": "Mass balance applied across all unit processes...",
  "dataset_type": "LCI result",
  "lci_method_principle": "Attributional",
  "lci_method_approaches": ["market value", "calorific value"],
  "deviations_from_lci_method": null,
  "modelling_constants": "GHG emission factors based on IPCC 2021...",
  "data_cutoff_principles": "Coverage of at least 99% of mass and energy...",
  "data_selection_principles": "Primary data collected from industry surveys...",
  "supply_coverage_percent": 99.0,
  "dqi_overall_quality": "good",
  "dqi_technological_representativeness": "very good",
  "dqi_time_representativeness": "good",
  "dqi_geographical_representativeness": "fair",
  "dqi_completeness": "very good",
  "dqi_precision": "good",
  "dqi_methodological_appropriateness": "very good"
}
```

`null` for any field not found in the XML — output structure is always consistent.

**Note on ILCD namespaces:** The XML uses multiple namespace prefixes (`common:`, `ilcd:`, etc.). These are resolved internally by `parser.py` using `lxml` and a namespace map. The JSON output contains no namespace prefixes.

**Note on language:** Fields with `xml:lang` attribute — always prefer `lang="en"`, fall back to first available.

**Note on inputs/outputs:** These XML files are `metaDataOnly="true"` — exchange flow data (inputs/outputs) is not present and therefore not exported.

---

## Error Handling

| Situation | Behaviour |
|---|---|
| Network error / timeout | Log `[FAIL] <url> — connection error`, skip |
| HTTP error (404, 403, etc.) | Log `[FAIL] <url> — HTTP 404`, skip |
| Malformed / invalid XML | Log `[FAIL] <url> — XML parse error`, skip |
| JSON export error | Log `[FAIL] <uuid> — export failed`, skip |
| Output file already exists | Log `[WARN] <uuid>.xml already exists — overwriting`, continue |

**Console output during run:**
```
[OK]   9f2f5c2f — Al-capacitor SMD (2.54g)
[FAIL] bc83b460 — HTTP 404
[OK]   87be22ec — Capacitor ceramic MLCC...

Done. 26 succeeded, 2 failed.
Failed URLs saved to: dataset/output/failed_urls_2026-03-21_143012.txt
```

---

## Libraries

| Library | Purpose |
|---|---|
| `requests` | HTTP download |
| `lxml` | ILCD XML parsing (namespace-aware) |
| `json` (stdlib) | JSON export |
| `argparse` (stdlib) | CLI argument parsing |
| `pathlib` (stdlib) | File path handling |
| `pytest` | Testing |

---

## Testing

Test fixture: `tests/sample_dataset.xml` — a real Sphera XML file downloaded once and committed. No live HTTP calls during tests.

**`tests/test_downloader.py`**
- Valid URL returns non-empty XML string
- Invalid URL raises handled error (no crash)
- HTTP 404 raises handled error

**`tests/test_parser.py`**
- Parse sample XML → all MUST fields present in output dict
- Missing field in XML → returns `None` (no crash)
- DQI indicators extracted correctly by name attribute
- Language fallback works when `lang="en"` absent

**`tests/test_exporter.py`**
- JSON file written with correct keys and `indent=2`
- XML file written untouched (byte-for-byte match)
- Overwrite warning triggered when file already exists

---

## Developer Notes

**DQI field matching:** Match `dataQualityIndicator` elements by their `name` attribute using exact, case-sensitive string matching (e.g. `name="Overall quality"`). Use the names as listed in the field table — no fuzzy or substring matching.

**Language fallback:** For fields with `xml:lang` attribute, prefer `lang="en"`. If English is not present, fall back to the first element in DOM order.

**stdout vs stderr:** `[OK]` progress lines → `stdout`. `[FAIL]` and `[WARN]` messages → `stderr`. Summary line (`Done. X succeeded, Y failed.`) → `stdout`.

**MUST / NICE TO HAVE field sets:** Defined as Python constants at the top of `parser.py`:
```python
MUST_FIELDS = {"uuid", "name_base", "synonyms", "general_comment", "classification",
               "location", "geographical_representativeness_description", "reference_year",
               "valid_until", "technology_description", "dataset_type",
               "lci_method_principle", "lci_method_approaches", "dqi_overall_quality"}

NICE_FIELDS = {"name_treatment_standards_routes", "name_mix_and_location_types",
               "name_functional_unit", "use_advice", "reference_flows",
               "time_description", "technological_applicability", "mathematical_relations",
               "deviations_from_lci_method", "modelling_constants", "data_cutoff_principles",
               "data_selection_principles", "supply_coverage_percent",
               "dqi_technological_representativeness", "dqi_time_representativeness",
               "dqi_geographical_representativeness", "dqi_completeness",
               "dqi_precision", "dqi_methodological_appropriateness"}
```
Both sets are exported in JSON. Module 3 (viewer) imports these constants to switch between short (MUST only) and long (MUST + NICE) display modes.

---

## Official ILCD References

| Resource | URL |
|---|---|
| ILCD ProcessDataSet Format 1.1 | https://eplca.jrc.ec.europa.eu/LCDN/downloads/ILCD_Format_1.1_Documentation/ILCD_ProcessDataSet.html |
| ILCD Developer Data Format | https://eplca.jrc.ec.europa.eu/LCDN/developerILCDDataFormat.html |
| European Platform on LCA (EPLCA) | https://eplca.jrc.ec.europa.eu/ilcd.html |
| ILCD Guidance Document (PDF) | https://eplca.jrc.ec.europa.eu/uploads/QMS_H08_ENSURE_ILCD_GuidanceDocumentationLCADataSets_Version1-1Beta_2011_ISBN_clean.pdf |

---

## Future Versions (not in scope now)

| Version | Description |
|---|---|
| V1.1 | Save all datasets in a single CSV/XLS file |
| Module 2 V1.1 | LLM beautification of `technology_description` field |
| Module 2 V1.2 | LLM-generated abstract |
| Module 3 V1.0 | CLI dataset viewer (short/long mode) |
| Future V1.X | Configurable field include/exclude via config file |
| V1.4 | Handling of embedded images (JPG/PNG) |
