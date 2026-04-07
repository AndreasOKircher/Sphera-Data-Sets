"""Tests for viewer/query.py pure functions and Flask route."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from viewer.query import build_prompt, parse_response, run_query


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

DATASET_A = {
    "uuid": "aaa-111",
    "name_base": "Steel sheet, hot rolled",
    "classification": "Metal",
    "location": "DE",
    "reference_year": "2022",
    "_summary": "Hot-rolled steel sheet used in automotive applications.",
    "technology_description": "This is the long description.",
}

DATASET_B = {
    "uuid": "bbb-222",
    "name_base": "Aluminium profile",
    "classification": "Metal",
    "location": "EU",
    "reference_year": "2021",
    "_summary": "",
    "technology_description": "Aluminium extrusion for structural use.",
}


def test_build_prompt_contains_question():
    result = build_prompt("Which dataset represents steel sheet?", [DATASET_A])
    assert "Which dataset represents steel sheet?" in result


def test_build_prompt_contains_uuid():
    result = build_prompt("test", [DATASET_A])
    assert "aaa-111" in result


def test_build_prompt_uses_summary_when_available():
    result = build_prompt("test", [DATASET_A])
    assert "Hot-rolled steel sheet" in result
    assert "This is the long description" not in result


def test_build_prompt_falls_back_to_technology_description():
    result = build_prompt("test", [DATASET_B])
    assert "Aluminium extrusion" in result


def test_build_prompt_truncates_fallback_description():
    long_desc = "x" * 1000
    d = {**DATASET_B, "technology_description": long_desc, "_summary": ""}
    result = build_prompt("test", [d])
    desc_line = next(l for l in result.splitlines() if l.startswith("Description:"))
    desc_content = desc_line[len("Description:"):].strip()
    assert desc_content == "x" * 500  # exactly 500 chars, not 1000


def test_build_prompt_multiple_datasets():
    result = build_prompt("test", [DATASET_A, DATASET_B])
    assert "aaa-111" in result
    assert "bbb-222" in result


# ---------------------------------------------------------------------------
# parse_response
# ---------------------------------------------------------------------------

VALID_JSON = json.dumps([
    {"uuid": "aaa-111", "name": "Steel sheet", "rank": 1, "relevance_score": 5, "comment": "Direct match."},
    {"uuid": "bbb-222", "name": "Aluminium profile", "rank": 2, "relevance_score": 2, "comment": "Different material."},
])


def test_parse_response_valid_json():
    result = parse_response(VALID_JSON)
    assert len(result) == 2
    assert result[0]["rank"] == 1
    assert result[1]["uuid"] == "bbb-222"


def test_parse_response_strips_markdown_fences():
    fenced = f"```json\n{VALID_JSON}\n```"
    result = parse_response(fenced)
    assert len(result) == 2


def test_parse_response_strips_plain_fences():
    fenced = f"```\n{VALID_JSON}\n```"
    result = parse_response(fenced)
    assert len(result) == 2


def test_parse_response_strips_whitespace():
    result = parse_response(f"\n  {VALID_JSON}  \n")
    assert len(result) == 2


def test_parse_response_malformed_returns_empty():
    result = parse_response("This is not JSON at all.")
    assert result == []


def test_parse_response_non_list_returns_empty():
    result = parse_response('{"key": "value"}')
    assert result == []


def test_parse_response_empty_array():
    result = parse_response("[]")
    assert result == []


# ---------------------------------------------------------------------------
# run_query (mocked API)
# ---------------------------------------------------------------------------

def _make_mock_llm_client(response_text: str):
    mock_client = MagicMock()
    mock_client.complete.return_value = response_text
    return mock_client


def test_run_query_returns_parsed_results():
    results = run_query("Which is steel?", [DATASET_A, DATASET_B],
                        client=_make_mock_llm_client(VALID_JSON))
    assert len(results) == 2
    assert results[0]["rank"] == 1


def test_run_query_passes_question_in_prompt():
    mock_client = _make_mock_llm_client(VALID_JSON)
    run_query("my unique question xyz", [DATASET_A], client=mock_client)
    call_args = mock_client.complete.call_args
    user_msg = call_args.args[1] if call_args.args else call_args.kwargs["user"]
    assert "my unique question xyz" in user_msg


def test_run_query_malformed_llm_response_returns_empty():
    results = run_query("test", [DATASET_A],
                        client=_make_mock_llm_client("Sorry, I cannot answer."))
    assert results == []


# ---------------------------------------------------------------------------
# /query Flask route
# ---------------------------------------------------------------------------

import pytest

@pytest.fixture
def flask_client(monkeypatch):
    """Flask test client with LLM client configured and run_query mocked."""
    import viewer.app as app_mod
    app_mod.app.config["LLM_CLIENT"] = MagicMock()
    app_mod.app.config["TESTING"] = True

    monkeypatch.setattr(
        "viewer.query.run_query",
        lambda question, datasets, client, fields=None: [
            {"uuid": d["uuid"], "name": d.get("name_base", ""), "rank": i + 1,
             "relevance_score": 5 - i, "comment": "test comment"}
            for i, d in enumerate(datasets)
        ],
    )
    monkeypatch.setattr(
        "viewer.app.load_all",
        lambda: [
            {**DATASET_A, "uuid": "aaa-111"},
            {**DATASET_B, "uuid": "bbb-222"},
        ],
    )
    with app_mod.app.test_client() as c:
        yield c


def test_query_route_missing_question(flask_client):
    resp = flask_client.post("/query",
        json={"uuids": ["aaa-111"]},
        content_type="application/json")
    assert resp.status_code == 400
    assert "question" in resp.get_json()["error"]


def test_query_route_missing_uuids(flask_client):
    resp = flask_client.post("/query",
        json={"question": "Which is better?"},
        content_type="application/json")
    assert resp.status_code == 400
    assert "uuids" in resp.get_json()["error"]


def test_query_route_no_matching_datasets(flask_client):
    resp = flask_client.post("/query",
        json={"question": "test", "uuids": ["unknown-uuid"]},
        content_type="application/json")
    assert resp.status_code == 400
    assert "No matching" in resp.get_json()["error"]


def test_query_route_no_api_key(monkeypatch):
    import viewer.app as app_mod
    app_mod.app.config["LLM_CLIENT"] = None
    app_mod.app.config["TESTING"] = True
    with app_mod.app.test_client() as c:
        resp = c.post("/query",
            json={"question": "test", "uuids": ["aaa-111"]},
            content_type="application/json")
    assert resp.status_code == 503


def test_query_route_success(flask_client):
    resp = flask_client.post("/query",
        json={"question": "Which is steel?", "uuids": ["aaa-111"]},
        content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["uuid"] == "aaa-111"


# ---------------------------------------------------------------------------
# build_prompt with fields parameter
# ---------------------------------------------------------------------------

def test_build_prompt_includes_classification_by_default():
    result = build_prompt("test", [DATASET_A])
    assert "Metal" in result  # classification

def test_build_prompt_includes_location_by_default():
    result = build_prompt("test", [DATASET_A])
    assert "DE" in result  # location

def test_build_prompt_excludes_classification_when_not_in_fields():
    result = build_prompt("test", [DATASET_A], fields=["location", "year", "description"])
    assert "Metal" not in result
    assert "DE" in result

def test_build_prompt_excludes_location_when_not_in_fields():
    result = build_prompt("test", [DATASET_A], fields=["classification", "year", "description"])
    assert "DE" not in result
    assert "Metal" in result

def test_build_prompt_includes_synonyms_when_requested():
    d = {**DATASET_A, "synonyms": "flat-rolled steel; HR steel"}
    result = build_prompt("test", [d], fields=["description", "synonyms"])
    assert "flat-rolled steel" in result
