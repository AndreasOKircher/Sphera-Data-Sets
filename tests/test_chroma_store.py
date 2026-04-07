# tests/test_chroma_store.py
import json
import pytest
from pathlib import Path


@pytest.fixture
def sample_datasets(tmp_path):
    """Write two minimal dataset JSON files to tmp_path."""
    d1 = {
        "uuid": "uuid-001",
        "name_base": "Steel sheet",
        "technology_description": "Production of cold-rolled steel sheet using electric arc furnace.",
        "process_type": "Unit process",
        "databases": ["Professional database 2026"],
        "location": "DE",
        "classification": "Metals",
    }
    d2 = {
        "uuid": "uuid-002",
        "name_base": "Aluminium ingot",
        "technology_description": "Production of secondary aluminium ingot from post-consumer scrap.",
        "process_type": "Unit process",
        "databases": ["Extension database XI: electronics 2026"],
        "location": "GLO",
        "classification": "Metals",
    }
    (tmp_path / "uuid-001.json").write_text(json.dumps(d1))
    (tmp_path / "uuid-002.json").write_text(json.dumps(d2))
    return tmp_path


def test_build_index_creates_collection(sample_datasets, tmp_path):
    from core.chroma_store import build_index, get_client
    chroma_path = tmp_path / "chroma"
    build_index(sample_datasets, enriched_dir=None, chroma_path=chroma_path)
    client = get_client(chroma_path)
    col = client.get_collection("sphera_datasets")
    assert col.count() == 2


def test_query_similar_returns_results(sample_datasets, tmp_path):
    from core.chroma_store import build_index, query_similar
    chroma_path = tmp_path / "chroma"
    build_index(sample_datasets, enriched_dir=None, chroma_path=chroma_path)
    results = query_similar("aluminium recycling scrap", chroma_path=chroma_path, n_results=2)
    assert len(results) >= 1
    uuids = [r["uuid"] for r in results]
    assert "uuid-002" in uuids  # aluminium dataset should rank first


def test_query_similar_with_metadata_filter(sample_datasets, tmp_path):
    from core.chroma_store import build_index, query_similar
    chroma_path = tmp_path / "chroma"
    build_index(sample_datasets, enriched_dir=None, chroma_path=chroma_path)
    results = query_similar(
        "metal production",
        chroma_path=chroma_path,
        n_results=5,
        where={"process_type": "Unit process"},
    )
    assert all(r["process_type"] == "Unit process" for r in results)


def test_build_index_is_idempotent(sample_datasets, tmp_path):
    from core.chroma_store import build_index, get_client
    chroma_path = tmp_path / "chroma"
    build_index(sample_datasets, enriched_dir=None, chroma_path=chroma_path)
    build_index(sample_datasets, enriched_dir=None, chroma_path=chroma_path)
    client = get_client(chroma_path)
    col = client.get_collection("sphera_datasets")
    assert col.count() == 2  # no duplicates
