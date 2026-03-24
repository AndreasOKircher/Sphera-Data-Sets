"""Tests for viewer/query.py pure functions and Flask route."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from viewer.query import build_prompt, parse_response, run_query, DEFAULT_QUERY_MODEL


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

def _make_mock_client(response_text: str):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=response_text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


def test_run_query_returns_parsed_results(monkeypatch):
    import viewer.query as qmod
    mock_client = _make_mock_client(VALID_JSON)
    monkeypatch.setattr(qmod.anthropic, "Anthropic", MagicMock(return_value=mock_client))
    results = run_query("Which is steel?", [DATASET_A, DATASET_B], api_key="fake-key")
    assert len(results) == 2
    assert results[0]["rank"] == 1


def test_run_query_passes_question_in_prompt(monkeypatch):
    import viewer.query as qmod
    mock_client = _make_mock_client(VALID_JSON)
    monkeypatch.setattr(qmod.anthropic, "Anthropic", MagicMock(return_value=mock_client))
    run_query("my unique question xyz", [DATASET_A], api_key="fake-key")
    call_args = mock_client.messages.create.call_args
    messages = call_args.kwargs["messages"]
    assert "my unique question xyz" in messages[0]["content"]


def test_run_query_uses_default_model(monkeypatch):
    import viewer.query as qmod
    mock_client = _make_mock_client(VALID_JSON)
    monkeypatch.setattr(qmod.anthropic, "Anthropic", MagicMock(return_value=mock_client))
    run_query("test", [DATASET_A], api_key="fake-key")
    call_args = mock_client.messages.create.call_args
    assert call_args.kwargs["model"] == DEFAULT_QUERY_MODEL


def test_run_query_uses_custom_model(monkeypatch):
    import viewer.query as qmod
    mock_client = _make_mock_client(VALID_JSON)
    monkeypatch.setattr(qmod.anthropic, "Anthropic", MagicMock(return_value=mock_client))
    run_query("test", [DATASET_A], api_key="fake-key", model="claude-sonnet-4-6")
    call_args = mock_client.messages.create.call_args
    assert call_args.kwargs["model"] == "claude-sonnet-4-6"


def test_run_query_malformed_llm_response_returns_empty(monkeypatch):
    import viewer.query as qmod
    mock_client = _make_mock_client("Sorry, I cannot answer that.")
    monkeypatch.setattr(qmod.anthropic, "Anthropic", MagicMock(return_value=mock_client))
    results = run_query("test", [DATASET_A], api_key="fake-key")
    assert results == []


# ---------------------------------------------------------------------------
# /query Flask route
# ---------------------------------------------------------------------------

import pytest

@pytest.fixture
def flask_client(monkeypatch):
    """Flask test client with API key configured and run_query mocked."""
    import viewer.app as app_mod
    app_mod.app.config["ANTHROPIC_API_KEY"] = "fake-key"
    app_mod.app.config["TESTING"] = True

    # Patch at definition site — app.py uses local import inside function body
    monkeypatch.setattr(
        "viewer.query.run_query",
        lambda question, datasets, api_key, model, fields=None: [
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
    original_key = app_mod.app.config.get("ANTHROPIC_API_KEY", "")
    app_mod.app.config["ANTHROPIC_API_KEY"] = ""
    app_mod.app.config["TESTING"] = True
    try:
        with app_mod.app.test_client() as c:
            resp = c.post("/query",
                json={"question": "test", "uuids": ["aaa-111"]},
                content_type="application/json")
        assert resp.status_code == 503
    finally:
        app_mod.app.config["ANTHROPIC_API_KEY"] = original_key


def test_query_route_success(flask_client):
    resp = flask_client.post("/query",
        json={"question": "Which is steel?", "uuids": ["aaa-111"]},
        content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["uuid"] == "aaa-111"
