# core/chroma_store.py
from __future__ import annotations
import json
import time
from pathlib import Path
import chromadb

COLLECTION_NAME = "sphera_datasets"


def get_client(chroma_path: Path) -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(chroma_path))


def _text_for_embedding(data: dict, enriched: dict) -> str:
    """Build embed text for semantic search.

    Always prepends name_base + classification as anchors.
    Primary body: technology_description_summary (10a, compact LLM output).
    Fallback body: general_comment, then raw technology_description (truncated).
    """
    parts = []
    name = (data.get("name_base") or "").strip()
    classification = (data.get("classification") or "").strip()
    if name:
        parts.append(name)
    if classification:
        parts.append(classification)

    summary = (enriched.get("technology_description_summary") or "").strip()
    if summary:
        parts.append(summary)
    else:
        comment = (data.get("general_comment") or "").strip()
        tech = (data.get("technology_description") or "").strip()
        if comment:
            parts.append(comment)
        if tech:
            parts.append(tech[:3000])

    return "\n\n".join(parts)[:8000]


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

    json_files = sorted(Path(output_dir).glob("*.json"))
    total = len(json_files)
    print(f"[INDEX] Found {total} JSON files — building index...")

    t_start = time.monotonic()

    for i, json_file in enumerate(json_files, 1):
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

        if i % 100 == 0 or i == total:
            elapsed = time.monotonic() - t_start
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else 0
            print(f"  {i:>5}/{total}  {rate:5.1f}/s  ETA {eta:5.0f}s", end="\r", flush=True)

        # Metadata must be flat scalars for ChromaDB
        databases = data.get("databases") or []
        meta = {
            "uuid": uuid,
            "name_base": data.get("name_base") or "",
            "dataset_type": data.get("dataset_type") or "",
            "process_type": data.get("process_type") or "",
            "location": data.get("location") or "",
            "classification": data.get("classification") or "",
            # Store as newline-joined string — ChromaDB doesn't support list metadata
            "databases": "\n".join(databases),
        }

        ids.append(uuid)
        documents.append(text)
        metadatas.append(meta)

    print()  # newline after progress line
    if not ids:
        print("[INDEX] No datasets found to index.")
        return

    batch_size = 5000
    for start in range(0, len(ids), batch_size):
        col.upsert(
            ids=ids[start:start + batch_size],
            documents=documents[start:start + batch_size],
            metadatas=metadatas[start:start + batch_size],
        )

    elapsed = time.monotonic() - t_start
    print(f"[INDEX] Upserted {len(ids)} datasets into ChromaDB at {chroma_path}  ({elapsed:.1f}s)")


def query_similar(
    question: str,
    chroma_path: Path,
    n_results: int = 20,
    where: dict | None = None,
) -> list[dict]:
    """Similarity search. Returns list of metadata dicts with 'uuid' key.

    Parameters
    ----------
    where : ChromaDB metadata filter dict, e.g. {"process_type": "Unit process"}
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
