# tests/test_xls_manifest.py
import pytest
from unittest.mock import patch, MagicMock
from core.xls_manifest import load_manifest, get_uuids_for_databases, ManifestEntry

# Real column layout (0-based): GUID=1, TYPE=11, DBS=16, URL=28
# Helper builds a sparse 29-element row matching actual XLS structure.
def _row(guid="", url="", dtype="", dbs=""):
    r = [None] * 29
    r[1]  = guid
    r[11] = dtype
    r[16] = dbs
    r[28] = url
    return r


FAKE_ROWS = [
    _row("{AAA-111}", "https://example.com/aaa", "Unit process",    "Professional database 2026"),
    _row("{BBB-222}", "https://example.com/bbb", "Aggregated process", "Extension database XI: electronics 2026"),
    _row("{CCC-333}", "https://example.com/ccc", "Unit process",
         "Professional database 2026\nExtension database XI: electronics 2026"),
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
    assert entry.process_type == "Unit process"
    assert "Professional database 2026" in entry.databases


def test_load_manifest_normalises_guid():
    ws = _make_ws(FAKE_ROWS)
    with patch("core.xls_manifest.openpyxl.load_workbook") as mock_wb:
        mock_wb.return_value.active = ws
        result = load_manifest("fake.xlsx")
    # Braces stripped, lower-cased
    assert "aaa-111" in result
    assert "{AAA-111}" not in result


def test_load_manifest_splits_multi_database_cell():
    ws = _make_ws(FAKE_ROWS)
    with patch("core.xls_manifest.openpyxl.load_workbook") as mock_wb:
        mock_wb.return_value.active = ws
        result = load_manifest("fake.xlsx")
    assert len(result["ccc-333"].databases) == 2


def test_load_manifest_splits_slash_separated_databases():
    rows = [_row("{DDD-444}", "https://example.com/ddd", "Unit process",
                 "Professional database 2026 / Extension database XI: electronics 2026")]
    ws = _make_ws(rows)
    with patch("core.xls_manifest.openpyxl.load_workbook") as mock_wb:
        mock_wb.return_value.active = ws
        result = load_manifest("fake.xlsx")
    assert len(result["ddd-444"].databases) == 2
    assert "Professional database 2026" in result["ddd-444"].databases
    assert "Extension database XI: electronics 2026" in result["ddd-444"].databases


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
    rows = [_row("", "https://x.com", "Unit process", "Professional database 2026")]
    ws = _make_ws(rows)
    with patch("core.xls_manifest.openpyxl.load_workbook") as mock_wb:
        mock_wb.return_value.active = ws
        result = load_manifest("fake.xlsx")
    assert len(result) == 0
