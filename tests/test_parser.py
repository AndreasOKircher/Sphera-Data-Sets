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
