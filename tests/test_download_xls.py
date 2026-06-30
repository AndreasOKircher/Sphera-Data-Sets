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
        process_type="Unit process",
        databases=["Professional database 2026"],
    )
}


def test_process_url_from_manifest_merges_fields(tmp_path):
    """process_url_from_manifest injects source_url, process_type, databases into exported JSON."""
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
        assert exported_data["process_type"] == "Unit process"
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


def test_process_url_from_manifest_skips_empty_url(tmp_path):
    """Skips silently when source_url is blank — no download attempt, no failure."""
    entry = ManifestEntry(uuid="bbb-222", source_url="", process_type="Unit process", databases=[])

    with patch("download.download_xml") as mock_dl:
        from download import process_url_from_manifest
        result = process_url_from_manifest(entry, tmp_path)
        mock_dl.assert_not_called()
        assert result == "skip"
