#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys
import json
from tqdm import tqdm


def collect_files(patterns: list[str], recursive: bool) -> list[Path]:
    files: list[Path] = []

    for pattern in patterns:
        p = Path(pattern)

        if any(ch in pattern for ch in "*?[]"):
            if recursive and "**" not in pattern:
                matches = Path(".").glob(f"**/{pattern}")
            else:
                matches = Path(".").glob(pattern)

            files.extend(x for x in matches if x.is_file())
        elif p.is_dir():
            if recursive:
                files.extend(x for x in p.rglob("*.json") if x.is_file())
            else:
                files.extend(x for x in p.glob("*.json") if x.is_file())
        elif p.is_file():
            files.append(p)

    seen = set()
    unique_files = []
    for f in sorted(files):
        resolved = str(f.resolve())
        if resolved not in seen:
            seen.add(resolved)
            unique_files.append(f)

    return unique_files


def normalize_value(value):
    if value is None:
        return None
    if isinstance(value, list):
        return ", ".join(str(v).strip() for v in value if v is not None and str(v).strip())
    return str(value).strip()


def build_text_labeled(fields: dict[str, str]) -> str:
    parts = []

    ordered = [
        ("name_base", "name_base"),
        ("name_treatment_standards_routes", "name_treatment_standards_routes"),
        ("synonyms", "synonyms"),
        ("technology_description", "technology_description"),
        ("general_comment", "general_comment"),
    ]

    for key, label in ordered:
        value = fields.get(key)
        if value:
            parts.append(f"{label}: {value}")

    return "\n\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Batch extract selected fields from JSON files and write them as JSONL "
            "for RAG / vector embedding pipelines."
        ),
        epilog=(
            "Examples:\n"
            "  python .\scrip\fields_to_jsonl.py \n"
            "  python .\scrip\fields_to_jsonl.py  -r\n"
            "  python .\scrip\fields_to_jsonl.py  -i .\\dataset\\output -o .\\dataset\\jsonl\\dataset.jsonl\n"
            "  python .\scrip\fields_to_jsonl.py  -i .\\dataset\\output\\*.json -o .\\dataset\\jsonl\\dataset.jsonl\n\n"
            "Output format per line:\n"
            "  {\"id\": \"<uuid>\", \"text\": \"<combined labeled text>\", \"fields\": {...}}\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-i", "--input",
        default=r".\dataset\output",
        help="Input directory, file, or wildcard pattern (default: .\\dataset\\output)"
    )
    parser.add_argument(
        "-o", "--output",
        default=r".\dataset\jsonl\dataset.jsonl",
        help="Output JSONL file path (default: .\\dataset\\jsonl\\dataset.jsonl)"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Scan input directories recursively for *.json files"
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Text encoding for reading and writing (default: utf-8)"
    )

    args = parser.parse_args()

    p = Path(args.input)
    if p.is_dir():
        input_patterns = [str(p)]
    else:
        input_patterns = [args.input]

    files = collect_files(input_patterns, args.recursive)

    if not files:
        print("No matching JSON files found.", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_files = len(files)
    processed = 0
    skipped = 0
    parse_errors = 0
    missing_uuid = 0
    empty_text = 0

    with output_path.open("w", encoding=args.encoding, newline="\n") as out:
        for file_path in tqdm(files, desc="Processing JSON files", unit="file"):
            try:
                content = file_path.read_text(encoding=args.encoding)
                data = json.loads(content)
            except Exception as exc:
                print(f"Skipping {file_path}: {exc}", file=sys.stderr)
                skipped += 1
                parse_errors += 1
                continue

            uuid = normalize_value(data.get("uuid"))
            if not uuid:
                print(f"Skipping {file_path}: missing 'uuid'", file=sys.stderr)
                skipped += 1
                missing_uuid += 1
                continue

            fields = {
                "name_base": normalize_value(data.get("name_base")),
                "technology_description": normalize_value(data.get("technology_description")),
                "general_comment": normalize_value(data.get("general_comment")),
                "name_treatment_standards_routes": normalize_value(data.get("name_treatment_standards_routes")),
                "synonyms": normalize_value(data.get("synonyms")),
                "uuid": uuid,
            }

            text = build_text_labeled(fields)

            if not text.strip():
                print(f"Skipping {file_path}: no searchable text content", file=sys.stderr)
                skipped += 1
                empty_text += 1
                continue

            record = {
                "id": uuid,
                "text": text,
                "fields": fields,
            }

            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            processed += 1

    print()
    print("Finished.")
    print(f"Input files scanned : {total_files}")
    print(f"Records written     : {processed}")
    print(f"Files skipped       : {skipped}")
    if skipped:
        print(f"  - parse errors    : {parse_errors}")
        print(f"  - missing uuid    : {missing_uuid}")
        print(f"  - empty text      : {empty_text}")
    print(f"Output JSONL        : {output_path}")


if __name__ == "__main__":
    main()