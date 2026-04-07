"""Re-parse saved XML files and regenerate JSON without re-downloading."""

import argparse
import json
import sys
from pathlib import Path

from core.parser import parse_dataset

OUTPUT_DIR = Path(__file__).parent / "dataset" / "output"


# Fields sourced from the XLS manifest (not present in ILCD XML).
# Preserved from existing JSON when re-parsing so they are not lost.
_XLS_FIELDS = ("source_url", "process_type", "databases")


def _preserve_xls_fields(data: dict, json_path: Path) -> None:
    """Copy XLS-sourced fields from existing JSON into data if present."""
    if not json_path.exists():
        return
    try:
        existing = json.loads(json_path.read_text(encoding="utf-8"))
        for field in _XLS_FIELDS:
            if field in existing:
                data[field] = existing[field]
    except Exception:
        pass


def reparse_one(uuid: str, force: bool) -> None:
    xml_path  = OUTPUT_DIR / f"{uuid}.xml"
    json_path = OUTPUT_DIR / f"{uuid}.json"

    if not xml_path.exists():
        print(f"[SKIP] {uuid[:8]} — no XML file found")
        return

    if not force and json_path.exists():
        print(f"[SKIP] {uuid[:8]} — JSON already exists (use --force to overwrite)")
        return

    try:
        data = parse_dataset(xml_path.read_bytes())
        _preserve_xls_fields(data, json_path)
        name = (data.get("name_base") or "")[:60]
        json_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[OK]   {uuid[:8]} — {name}")
    except Exception as exc:
        print(f"[FAIL] {uuid[:8]} — {exc}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-parse saved XML files to regenerate JSON output."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--uuid", help="Re-parse a single dataset by UUID")
    group.add_argument("--all",  action="store_true", help="Re-parse all saved XML files")
    parser.add_argument("--force", action="store_true", help="Overwrite existing JSON files")
    args = parser.parse_args()

    if not OUTPUT_DIR.exists():
        print(f"[ERROR] Output directory not found: {OUTPUT_DIR}", file=sys.stderr)
        sys.exit(1)

    if args.uuid:
        reparse_one(args.uuid, args.force)
        return

    uuids = [f.stem for f in sorted(OUTPUT_DIR.glob("*.xml"))]
    if not uuids:
        print("No XML files found in dataset/output/")
        return

    ok = fail = skip = 0
    for uuid in uuids:
        json_path = OUTPUT_DIR / f"{uuid}.json"
        if not args.force and json_path.exists():
            skip += 1
            continue
        try:
            data = parse_dataset((OUTPUT_DIR / f"{uuid}.xml").read_bytes())
            _preserve_xls_fields(data, json_path)
            name = (data.get("name_base") or "")[:60]
            json_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"[OK]   {uuid[:8]} — {name}")
            ok += 1
        except Exception as exc:
            print(f"[FAIL] {uuid[:8]} — {exc}", file=sys.stderr)
            fail += 1

    print(f"\nDone. {ok} reparsed, {skip} skipped (already exist), {fail} failed.")


if __name__ == "__main__":
    main()
