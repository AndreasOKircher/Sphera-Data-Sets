# tests/test_chat_endpoint.py
import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def client(tmp_path):
    import viewer.app as app_module
    app_module.app.config["TESTING"] = True
    app_module.OUTPUT_DIR = tmp_path
    app_module.ENRICHED_DIR = tmp_path
    # Provide a fake LLM client
    mock_llm = MagicMock()
    mock_llm.complete.return_value = '[{"uuid":"x","name":"X","rank":1,"relevance_score":5,"comment":"good"}]'
    app_module.app.config["LLM_CLIENT"] = mock_llm
    return app_module.app.test_client()


def test_chat_endpoint_accepts_history(client, tmp_path):
    # Write a minimal dataset JSON so load_all finds something
    (tmp_path / "x.json").write_text(json.dumps({
        "uuid": "x", "name_base": "Test", "technology_description": "some text"
    }))
    resp = client.post("/chat", json={
        "question": "follow-up question",
        "uuids": ["x"],
        "history": [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"},
        ],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "results" in data


def test_chat_endpoint_requires_question(client):
    resp = client.post("/chat", json={"uuids": ["x"]})
    assert resp.status_code == 400
