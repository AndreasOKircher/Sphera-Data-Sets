# index.py
"""CLI to build or update the ChromaDB vector index from dataset/output JSON files."""

import argparse
from pathlib import Path
from core.chroma_store import build_index

DEFAULT_OUTPUT   = Path("dataset/output")
DEFAULT_ENRICHED = Path("dataset/enriched")
DEFAULT_CHROMA   = Path("dataset/chroma")


def main():
    parser = argparse.ArgumentParser(
        description="Build or update ChromaDB index from Sphera LCA datasets."
    )
    parser.add_argument("--output",   default=str(DEFAULT_OUTPUT),   help="dataset/output directory")
    parser.add_argument("--enriched", default=str(DEFAULT_ENRICHED), help="dataset/enriched directory")
    parser.add_argument("--db",       default=str(DEFAULT_CHROMA),   help="ChromaDB persistence directory")
    args = parser.parse_args()

    output_dir   = Path(args.output)
    enriched_dir = Path(args.enriched) if Path(args.enriched).exists() else None
    chroma_path  = Path(args.db)

    if not output_dir.exists():
        print(f"[ERROR] Output directory not found: {output_dir}")
        raise SystemExit(1)

    build_index(output_dir, enriched_dir, chroma_path)


if __name__ == "__main__":
    main()
