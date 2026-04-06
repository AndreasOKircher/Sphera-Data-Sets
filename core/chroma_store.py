# core/chroma_store.py
from __future__ import annotations
import json
from pathlib import Path
import chromadb

COLLECTION_NAME = "sphera_datasets"


def get_client(chroma_path: Path) -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(chroma_path))


def _text_for_embedding(data: dict, enriched: dict) -> str:
    """Prefer enriched formatted description; fall back to raw technology_description."""
    text = enriched.get("technology_description_formatted") or \
           data.get("technology_description") or \
           data.get("name_base") or ""
    return text[:8000]  # ChromaDB default model has a token limit


def build_index(
    output_dir: Path,
    enriched_dir: Path | None,
    chroma_path: Path,
) -> None:
    """Build or update ChromaDB index from dataset/output JSON files.

    Uses upsert so re-running is safe (idempotent by uuid).
    """
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = get_client(chroma_path)

    try:
        col = client.get_collection(COLLECTION_NAME)
    except Exception:
        col = client.create_collection(
            COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    ids, documents, metadatas = [], [], []

    for json_file in sorted(Path(output_dir).glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        uuid = data.get("uuid")
        if not uuid:
            continue

        enriched: dict = {}
        if enriched_dir:
            ep = Path(enriched_dir) / f"{uuid}.json"
            if ep.exists():
                try:
                    enriched = json.loads(ep.read_text(encoding="utf-8"))
                except Exception:
                    pass

        text = _text_for_embedding(data, enriched)
        if not text:
            continue

        # Metadata must be flat scalars for ChromaDB
        databases = data.get("databases") or []
        meta = {
            "uuid": uuid,
            "name_base": data.get("name_base") or "",
            "xls_dataset_type": data.get("xls_dataset_type") or "",
            "location": data.get("location") or "",
            "classification": data.get("classification") or "",
            # Store as newline-joined string — ChromaDB doesn't support list metadata
            "databases": "\n".join(databases),
        }

        ids.append(uuid)
        documents.append(text)
        metadatas.append(meta)

    if ids:
        col.upsert(ids=ids, documents=documents, metadatas=metadatas)
        print(f"[INDEX] Upserted {len(ids)} datasets into ChromaDB at {chroma_path}")
    else:
        print("[INDEX] No datasets found to index.")


def query_similar(
    question: str,
    chroma_path: Path,
    n_results: int = 20,
    where: dict | None = None,
) -> list[dict]:
    """Similarity search. Returns list of metadata dicts with 'uuid' key.

    Parameters
    ----------
    where : ChromaDB metadata filter dict, e.g. {"xls_dataset_type": "Unit process"}
    """
    client = get_client(chroma_path)
    try:
        col = client.get_collection(COLLECTION_NAME)
    except Exception:
        return []

    kwargs: dict = {"query_texts": [question], "n_results": min(n_results, col.count())}
    if where:
        kwargs["where"] = where

    results = col.query(**kwargs)
    metadatas = results.get("metadatas", [[]])[0]

    # Restore databases list from newline-joined string
    for m in metadatas:
        raw = m.get("databases", "")
        m["databases"] = [db for db in raw.splitlines() if db]

    return metadatas
