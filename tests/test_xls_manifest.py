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
