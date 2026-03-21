# Sphera LCA Dataset Compilation — Module 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that downloads Sphera ILCD XML datasets from URLs, parses them into a flat dict, and exports each as raw XML + flat JSON.

**Architecture:** Three focused core modules (downloader, parser, exporter) wired together by a CLI entry point. All file I/O goes through exporter. Parser owns the field constants (MUST_FIELDS, NICE_FIELDS). TDD throughout.

**Tech Stack:** Python 3.10+, requests, lxml, pytest, argparse, pathlib, json (stdlib)

**Spec:** `doc/specs/2026-03-21-sphera-lca-module1-design.md`
**Field table:** `doc/field-mapping-draft.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `requirements.txt` | Create | All dependencies |
| `core/__init__.py` | Create | Empty — marks core as package |
| `core/downloader.py` | Create | HTTP fetch, returns raw XML string |
| `core/parser.py` | Create | ILCD XML → flat dict; owns MUST_FIELDS/NICE_FIELDS |
| `core/exporter.py` | Create | Writes .xml and .json files; overwrite warning |
| `main.py` | Create | CLI entry point (argparse), orchestrates the pipeline |
| `tests/__init__.py` | Create | Empty — marks tests as package |
| `tests/sample_dataset.xml` | Download once | Real Sphera XML used as test fixture (no live HTTP in tests) |
| `tests/test_downloader.py` | Create | Downloader unit tests (mocked HTTP) |
| `tests/test_parser.py` | Create | Parser unit tests (uses sample_dataset.xml) |
| `tests/test_exporter.py` | Create | Exporter unit tests (tmp_path fixture) |
| `dataset/input/` | Create dir | URL list files |
| `dataset/output/` | Create dir | Downloaded datasets + fail reports |

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `core/__init__.py`
- Create: `tests/__init__.py`
- Create dirs: `dataset/input/`, `dataset/output/`

- [ ] **Step 1: Create requirements.txt**

```text
requests>=2.31.0
lxml>=5.0.0
pytest>=8.0.0
```

- [ ] **Step 2: Create empty package init files**

```bash
touch core/__init__.py tests/__init__.py
```

- [ ] **Step 3: Create dataset directories**

```bash
mkdir -p dataset/input dataset/output
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 5: Verify pytest runs**

```bash
pytest --collect-only
```

Expected: `no tests ran` or `0 items` — confirms pytest can find the test package.

- [ ] **Step 6: Commit**

```bash
git init
git add requirements.txt core/__init__.py tests/__init__.py
git commit -m "feat: project scaffold with dependencies"
```

---

## Task 2: Download Test Fixture

**Files:**
- Create: `tests/sample_dataset.xml`

This is done manually once. The file is committed so tests never hit the network.

- [ ] **Step 1: Download a real Sphera XML file**

```bash
curl -o tests/sample_dataset.xml \
  "https://lcadatabase.sphera.com/2026/xml-data/processes/9f2f5c2f-f304-4de0-8988-b0eaccdf7dff.xml"
```

- [ ] **Step 2: Verify the file looks right**

```bash
head -5 tests/sample_dataset.xml
```

Expected: starts with `<?xml` and contains `processDataSet`.

- [ ] **Step 3: Commit**

```bash
git add tests/sample_dataset.xml
git commit -m "test: add real Sphera XML fixture for offline tests"
```

---

## Task 3: Downloader

**Files:**
- Create: `tests/test_downloader.py`
- Create: `core/downloader.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_downloader.py`:

```python
from unittest.mock import patch, Mock
from core.downloader import download_xml, DownloadError


def test_valid_url_returns_bytes():
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"<processDataSet>test</processDataSet>"
    mock_response.raise_for_status = Mock()

    with patch("core.downloader.requests.get", return_value=mock_response):
        result = download_xml("https://example.com/test.xml")

    assert result == b"<processDataSet>test</processDataSet>"


def test_http_404_raises_download_error():
    import pytest
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("404 Client Error")

    with patch("core.downloader.requests.get", return_value=mock_response):
        with pytest.raises(DownloadError):
            download_xml("https://example.com/missing.xml")


def test_network_error_raises_download_error():
    import pytest
    with patch("core.downloader.requests.get", side_effect=Exception("Connection refused")):
        with pytest.raises(DownloadError):
            download_xml("https://example.com/test.xml")
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_downloader.py -v
```

Expected: `ImportError: cannot import name 'download_xml'`

- [ ] **Step 3: Implement downloader.py**

Create `core/downloader.py`:

```python
import requests


class DownloadError(Exception):
    pass


def download_xml(url: str, timeout: int = 30) -> bytes:
    """Fetch XML from URL. Returns raw bytes. Raises DownloadError on any failure."""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content  # raw bytes — untouched, no encoding round-trip
    except Exception as e:
        raise DownloadError(str(e)) from e
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_downloader.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add core/downloader.py tests/test_downloader.py
git commit -m "feat: downloader module with error handling"
```

---

## Task 4: Parser

**Files:**
- Create: `tests/test_parser.py`
- Create: `core/parser.py`

The parser uses `lxml.etree` with a namespace map. It extracts all fields from the field table into a flat dict. Missing fields return `None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_parser.py`:

```python
from pathlib import Path
from core.parser import parse_dataset, MUST_FIELDS, NICE_FIELDS

SAMPLE_XML = Path("tests/sample_dataset.xml").read_bytes()


def test_parse_returns_dict():
    result = parse_dataset(SAMPLE_XML)
    assert isinstance(result, dict)


def test_all_must_fields_present():
    result = parse_dataset(SAMPLE_XML)
    for field in MUST_FIELDS:
        assert field in result, f"MUST field missing: {field}"


def test_all_nice_fields_present():
    result = parse_dataset(SAMPLE_XML)
    for field in NICE_FIELDS:
        assert field in result, f"NICE field missing: {field}"


def test_uuid_extracted():
    result = parse_dataset(SAMPLE_XML)
    assert result["uuid"] == "9f2f5c2f-f304-4de0-8988-b0eaccdf7dff"


def test_location_extracted():
    result = parse_dataset(SAMPLE_XML)
    assert result["location"] == "GLO"


def test_dqi_overall_quality_extracted():
    result = parse_dataset(SAMPLE_XML)
    assert result["dqi_overall_quality"] is not None


def test_missing_field_returns_none():
    minimal_xml = b"""<?xml version="1.0"?>
    <processDataSet xmlns="http://lca.jrc.it/ILCD/Process"
                    xmlns:common="http://lca.jrc.it/ILCD/Common">
      <processInformation>
        <dataSetInformation>
          <common:UUID>test-uuid-1234</common:UUID>
        </dataSetInformation>
      </processInformation>
    </processDataSet>"""
    result = parse_dataset(minimal_xml)
    assert result["uuid"] == "test-uuid-1234"
    assert result["location"] is None
    assert result["technology_description"] is None


def test_lci_method_approaches_is_list():
    result = parse_dataset(SAMPLE_XML)
    assert isinstance(result["lci_method_approaches"], list)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_parser.py -v
```

Expected: `ImportError: cannot import name 'parse_dataset'`

- [ ] **Step 3: Implement parser.py**

Create `core/parser.py`:

```python
from lxml import etree

NS = {
    "ilcd": "http://lca.jrc.it/ILCD/Process",
    "common": "http://lca.jrc.it/ILCD/Common",
}

MUST_FIELDS = {
    "uuid", "name_base", "synonyms", "general_comment", "location",
    "geographical_representativeness_description", "reference_year",
    "valid_until", "technology_description", "dataset_type",
    "lci_method_principle", "lci_method_approaches", "dqi_overall_quality",
    "classification",
}

NICE_FIELDS = {
    "name_treatment_standards_routes", "name_mix_and_location_types",
    "name_functional_unit", "use_advice", "reference_flows",
    "time_description", "technological_applicability", "mathematical_relations",
    "deviations_from_lci_method", "modelling_constants", "data_cutoff_principles",
    "data_selection_principles", "supply_coverage_percent",
    "dqi_technological_representativeness", "dqi_time_representativeness",
    "dqi_geographical_representativeness", "dqi_completeness",
    "dqi_precision", "dqi_methodological_appropriateness",
}


def _text(root, xpath: str) -> str | None:
    """Extract text from first matching element, preferring lang=en."""
    elements = root.xpath(xpath, namespaces=NS)
    if not elements:
        return None
    en = [e for e in elements if e.get("{http://www.w3.org/XML/1998/namespace}lang") == "en"]
    el = en[0] if en else elements[0]
    return (el.text or "").strip() or None


def _attr(root, xpath: str, attr: str) -> str | None:
    """Extract attribute value from first matching element."""
    elements = root.xpath(xpath, namespaces=NS)
    return elements[0].get(attr) if elements else None


def parse_dataset(xml_bytes: bytes) -> dict:
    """Parse ILCD XML bytes into a flat dict. Missing fields return None."""
    root = etree.fromstring(xml_bytes)

    # DQI indicators — keyed by name attribute
    dqi = {}
    for el in root.xpath(".//common:dataQualityIndicator", namespaces=NS):
        name = el.get("name")
        value = el.get("value")
        if name:
            dqi[name] = value

    # LCI method approaches — may be multiple elements
    approaches = [
        el.text.strip()
        for el in root.xpath(".//ilcd:LCIMethodApproaches", namespaces=NS)
        if el.text
    ]

    # Classification — concatenate hierarchy levels
    class_parts = [
        el.text.strip()
        for el in root.xpath(".//common:class", namespaces=NS)
        if el.text
    ]
    classification = " / ".join(class_parts) if class_parts else None

    # Reference year and valid until — integers
    ref_year_str = _text(root, ".//common:referenceYear")
    valid_until_str = _text(root, ".//common:dataSetValidUntil")

    return {
        # Key data set info
        "uuid": _text(root, ".//common:UUID"),
        "name_base": _text(root, ".//ilcd:baseName"),
        "name_treatment_standards_routes": _text(root, ".//ilcd:treatmentStandardsRoutes"),
        "name_mix_and_location_types": _text(root, ".//ilcd:mixAndLocationTypes"),
        "name_functional_unit": _text(root, ".//ilcd:functionalUnitFlowProperties"),
        "synonyms": _text(root, ".//common:synonyms"),
        "classification": classification,
        "general_comment": _text(root, ".//common:generalComment"),
        "use_advice": _text(root, ".//ilcd:useAdviceForDataSet"),
        "reference_flows": _text(root, ".//ilcd:referenceToReferenceFlow"),
        # Time
        "reference_year": int(ref_year_str) if ref_year_str else None,
        "valid_until": int(valid_until_str) if valid_until_str else None,
        "time_description": _text(root, ".//common:timeRepresentativenessDescription"),
        # Location
        "location": _attr(root, ".//ilcd:locationOfOperationSupplyOrProduction", "location"),
        "geographical_representativeness_description": _text(root, ".//ilcd:descriptionOfRestrictions"),
        # Technology
        "technology_description": _text(root, ".//ilcd:technologyDescriptionAndIncludedProcesses"),
        "technological_applicability": _text(root, ".//ilcd:technologicalApplicability"),
        "mathematical_relations": _text(root, ".//ilcd:mathematicalRelations"),
        # Modelling
        "dataset_type": _text(root, ".//ilcd:typeOfDataSet"),
        "lci_method_principle": _text(root, ".//ilcd:LCIMethodPrinciple"),
        "lci_method_approaches": approaches if approaches else None,
        "deviations_from_lci_method": _text(root, ".//ilcd:deviationsFromLCIMethodApproaches"),
        "modelling_constants": _text(root, ".//ilcd:modellingConstants"),
        # Data sources
        "data_cutoff_principles": _text(root, ".//ilcd:dataCutOffAndCompletenessPrinciples"),
        "data_selection_principles": _text(root, ".//ilcd:dataSelectionAndCombinationPrinciples"),
        "supply_coverage_percent": _supply_percent(root),
        # Validation — DQI
        "dqi_overall_quality": dqi.get("Overall quality"),
        "dqi_technological_representativeness": dqi.get("Technological representativeness"),
        "dqi_time_representativeness": dqi.get("Time representativeness"),
        "dqi_geographical_representativeness": dqi.get("Geographical representativeness"),
        "dqi_completeness": dqi.get("Completeness"),
        "dqi_precision": dqi.get("Precision"),
        "dqi_methodological_appropriateness": dqi.get("Methodological appropriateness and consistency"),
    }


def _supply_percent(root) -> float | None:
    val = _text(root, ".//ilcd:percentageSupplyOrProductionCovered")
    try:
        return float(val) if val else None
    except ValueError:
        return None


# Note: _supply_percent is defined before parse_dataset intentionally —
# Python resolves function names at call time but defining helpers first
# avoids confusion when reading top-to-bottom.
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_parser.py -v
```

Expected: all tests pass. If any XPath fails, check the field name against `tests/sample_dataset.xml` and adjust.

- [ ] **Step 5: Commit**

```bash
git add core/parser.py tests/test_parser.py
git commit -m "feat: ILCD XML parser with all field extractions"
```

---

## Task 5: Exporter

**Files:**
- Create: `tests/test_exporter.py`
- Create: `core/exporter.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_exporter.py`:

```python
import json
import sys
from pathlib import Path
from core.exporter import export_dataset

SAMPLE_XML = Path("tests/sample_dataset.xml").read_bytes()
SAMPLE_DICT = {
    "uuid": "9f2f5c2f-f304-4de0-8988-b0eaccdf7dff",
    "name_base": "Al-capacitor SMD",
    "location": "GLO",
}


def test_json_file_written(tmp_path):
    export_dataset(SAMPLE_DICT, SAMPLE_XML, tmp_path)
    json_file = tmp_path / "9f2f5c2f-f304-4de0-8988-b0eaccdf7dff.json"
    assert json_file.exists()
    data = json.loads(json_file.read_text())
    assert data["uuid"] == "9f2f5c2f-f304-4de0-8988-b0eaccdf7dff"
    assert data["name_base"] == "Al-capacitor SMD"


def test_json_indented(tmp_path):
    export_dataset(SAMPLE_DICT, SAMPLE_XML, tmp_path)
    json_file = tmp_path / "9f2f5c2f-f304-4de0-8988-b0eaccdf7dff.json"
    content = json_file.read_text()
    assert "\n  " in content  # indent=2 produces indented output


def test_xml_file_written_untouched(tmp_path):
    export_dataset(SAMPLE_DICT, SAMPLE_XML, tmp_path)
    xml_file = tmp_path / "9f2f5c2f-f304-4de0-8988-b0eaccdf7dff.xml"
    assert xml_file.exists()
    assert xml_file.read_bytes() == SAMPLE_XML


def test_overwrite_warning_to_stderr(tmp_path, capsys):
    export_dataset(SAMPLE_DICT, SAMPLE_XML, tmp_path)
    export_dataset(SAMPLE_DICT, SAMPLE_XML, tmp_path)  # second write triggers warning
    captured = capsys.readouterr()
    assert "already exists" in captured.err
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_exporter.py -v
```

Expected: `ImportError: cannot import name 'export_dataset'`

- [ ] **Step 3: Implement exporter.py**

Create `core/exporter.py`:

```python
import json
import sys
from pathlib import Path


def export_dataset(data: dict, raw_xml: bytes, output_dir: Path) -> None:
    """Write <uuid>.xml and <uuid>.json to output_dir. Warns to stderr on overwrite."""
    uuid = data["uuid"]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    xml_path = output_dir / f"{uuid}.xml"
    json_path = output_dir / f"{uuid}.json"

    for path in (xml_path, json_path):
        if path.exists():
            print(f"[WARN] {path.name} already exists — overwriting", file=sys.stderr)

    xml_path.write_bytes(raw_xml)
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_exporter.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run all tests**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add core/exporter.py tests/test_exporter.py
git commit -m "feat: exporter writes xml and json, warns on overwrite"
```

---

## Task 6: CLI Entry Point

**Files:**
- Create: `main.py`

No unit tests for main.py — it is thin glue code. Verified by manual run.

- [ ] **Step 1: Implement main.py**

Create `main.py`:

```python
import argparse
import sys
from datetime import datetime
from pathlib import Path

from core.downloader import download_xml, DownloadError
from core.exporter import export_dataset
from core.parser import parse_dataset

DEFAULT_OUTPUT = Path("dataset/output")


def process_url(url: str, output_dir: Path) -> bool:
    """Download, parse, and export one URL. Returns True on success."""
    url = url.strip()
    if not url:
        return True
    try:
        xml_bytes = download_xml(url)
        data = parse_dataset(xml_bytes)
        uuid = data.get("uuid", "unknown")
        name = data.get("name_base", "")
        export_dataset(data, xml_bytes, output_dir)
        print(f"[OK]   {uuid} — {name}")
        return True
    except DownloadError as e:
        print(f"[FAIL] {url} — {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[FAIL] {url} — unexpected error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Download and export Sphera LCA datasets.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Single dataset URL")
    group.add_argument("--urls", help="Path to file with one URL per line")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    urls = [args.url] if args.url else Path(args.urls).read_text().splitlines()
    urls = [u.strip() for u in urls if u.strip()]

    failed_urls = []
    for url in urls:
        if not process_url(url, output_dir):
            failed_urls.append(url)

    total = len(urls)
    succeeded = total - len(failed_urls)
    print(f"\nDone. {succeeded}/{total} succeeded, {len(failed_urls)} failed.")

    if failed_urls:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        fail_file = output_dir / f"failed_urls_{timestamp}.txt"
        fail_file.write_text("\n".join(failed_urls), encoding="utf-8")
        print(f"Failed URLs saved to: {fail_file}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run with a single URL — verify output**

```bash
python main.py --url "https://lcadatabase.sphera.com/2026/xml-data/processes/9f2f5c2f-f304-4de0-8988-b0eaccdf7dff.xml"
```

Expected:
```
[OK]   9f2f5c2f-f304-4de0-8988-b0eaccdf7dff — Capacitor Al-capacitor SMD...
Done. 1/1 succeeded, 0 failed.
```

Check that `dataset/output/9f2f5c2f-....xml` and `.json` both exist.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: CLI entry point wiring downloader, parser, exporter"
```

---

## Task 7: Integration Run

- [ ] **Step 1: Copy URL list to input folder**

```bash
cp ressources/Sphera_EE_Hyperlinks_XML_Test.txt dataset/input/
```

- [ ] **Step 2: Run batch download**

```bash
python main.py --urls dataset/input/Sphera_EE_Hyperlinks_XML_Test.txt
```

Expected: progress lines for each URL, summary at end. Any failures saved to `failed_urls_<timestamp>.txt`.

- [ ] **Step 3: Spot-check a JSON output**

Open any `dataset/output/<uuid>.json` and verify:
- All MUST fields present (not all `null`)
- `dqi_overall_quality` has a value
- `technology_description` has text content
- JSON is human-readable with `indent=2`

- [ ] **Step 4: Run full test suite one final time**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Final commit**

```bash
git add dataset/input/
git commit -m "feat: add sample URL list to dataset/input"
```
