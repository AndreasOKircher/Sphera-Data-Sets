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
