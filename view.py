import argparse
import json
import sys
from pathlib import Path

from viewer.sections import MUST_FIELDS, SECTIONS

OUTPUT_DIR = Path("dataset/output")
SEP = "━" * 50
FIELD_W = 28   # field name column width
VALUE_W = 20   # value column width


def _clip(text: str, width: int) -> str:
    """Clip text to width, appending '..' if truncated."""
    if text is None:
        return "-"
    s = str(text)
    if len(s) <= width:
        return s
    return s[: width - 2] + ".."


def load_all() -> list[dict]:
    """Load all JSON files from OUTPUT_DIR. Skips malformed files."""
    datasets = []
    if not OUTPUT_DIR.exists():
        return datasets
    for f in sorted(OUTPUT_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            datasets.append(data)
        except Exception as e:
            print(f"[WARN] skipping {f.name}: {e}", file=sys.stderr)
    return datasets


def load_one(uuid: str) -> dict | None:
    """Load a single dataset by UUID. Returns None if not found."""
    path = OUTPUT_DIR / f"{uuid}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] could not read {path.name}: {e}", file=sys.stderr)
        return None


def list_datasets() -> None:
    """Print a numbered list of all datasets."""
    datasets = load_all()
    if not datasets:
        print("No datasets found in dataset/output/")
        return
    print(f"{'#':<4} {'UUID':<38} Name")
    print("─" * 80)
    for i, d in enumerate(datasets, 1):
        uuid = _clip(d.get("uuid", "—"), 36)
        name = _clip(d.get("name_base") or "—", 38)
        print(f"{i:<4} {uuid:<38} {name}")
    print(f"\n{len(datasets)} datasets in {OUTPUT_DIR}/")


def print_header(data: dict) -> None:
    """Print the summary header block."""
    name = data.get("name_base") or "—"
    uuid = data.get("uuid") or "—"
    location = data.get("location") or "—"
    ref_year = data.get("reference_year")
    valid_until = data.get("valid_until")
    dataset_type = data.get("dataset_type") or "—"

    year_range = f"{ref_year}–{valid_until}" if ref_year and valid_until else (str(ref_year or valid_until or "—"))

    print(SEP)
    print(f" {name}")
    print(f" UUID: {uuid}")
    print(f" {location} · {year_range}")
    print(f" {dataset_type}")
    print(SEP)
    print(f" {'MUST FIELDS':<{FIELD_W}} VALUE")
    for field in MUST_FIELDS:
        raw = data.get(field)
        field_label = _clip(field, FIELD_W)
        value_label = _clip(str(raw) if raw is not None else None, VALUE_W)
        print(f" {field_label:<{FIELD_W}} {value_label}")
    print(SEP)


def print_sections(data: dict, full: bool = False) -> None:
    """Print all field sections below the header."""
    TRUNC = 200
    for section_name, fields in SECTIONS:
        print(f"\n {'[ ' + section_name + ' ]':─<48}")
        for field in fields:
            raw = data.get(field)
            if raw is None:
                print(f"  {field}: —")
            else:
                text = str(raw)
                if not full and len(text) > TRUNC:
                    hidden = len(text) - TRUNC
                    text = text[:TRUNC] + f" [... {hidden} chars hidden — use --full to show]"
                print(f"  {field}: {text}")


def inspect_dataset(uuid: str, full: bool = False) -> None:
    """Inspect a single dataset by UUID."""
    data = load_one(uuid)
    if data is None:
        print(f"[ERROR] UUID not found: {uuid}")
        print()
        list_datasets()
        return
    print_header(data)
    print_sections(data, full=full)


def main() -> None:
    parser = argparse.ArgumentParser(description="View Sphera LCA datasets.")
    parser.add_argument("uuid", nargs="?", help="Dataset UUID to inspect")
    parser.add_argument("--full", action="store_true", help="Show full text without truncation")
    args = parser.parse_args()

    if args.uuid:
        inspect_dataset(args.uuid, full=args.full)
    else:
        list_datasets()


if __name__ == "__main__":
    main()
