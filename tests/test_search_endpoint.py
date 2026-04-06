# tests/test_search_endpoint.py
import json
import pytest
from unittest.mock import patch


@pytest.fixture
def client(tmp_path):
    import viewer.app as app_module
    app_module.app.config["TESTING"] = True
    app_module.OUTPUT_DIR = tmp_path
    app_module.ENRICHED_DIR = tmp_path
    return app_module.app.test_client()


def test_search_endpoint_returns_uuids(client):
    fake_results = [{"uuid": "aaa-111", "name_base": "Steel", "xls_dataset_type": "Unit process",
                     "location": "DE", "classification": "Metals", "databases": []}]
    with patch("viewer.app.query_similar", return_value=fake_results):
        resp = client.post("/search", json={"question": "steel production"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "uuids" in data
    assert "aaa-111" in data["uuids"]


def test_search_endpoint_requires_question(client):
    resp = client.post("/search", json={})
    assert resp.status_code == 400


def test_search_endpoint_applies_where_filter(client):
    fake_results = []
    with patch("viewer.app.query_similar", return_value=fake_results) as mock_qs:
        client.post("/search", json={
            "question": "aluminium",
            "filters": {"xls_dataset_type": "Unit process"},
        })
        call_kwargs = mock_qs.call_args[1]
        assert call_kwargs["where"] == {"xls_dataset_type": "Unit process"}
