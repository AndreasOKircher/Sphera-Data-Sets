#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys


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
                files.extend(x for x in p.rglob("*") if x.is_file())
            else:
                files.extend(x for x in p.glob("*") if x.is_file())
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Concatenate multiple files into one output file.",
        epilog=r"""Examples:
        python .\scripts\feed_datase_to_file.py -o .\dataset\combined\combined.txt ".\dataset\enriched\*.json"
        python merge_files.py -o .\output\all.txt .\docs -r
        python merge_files.py -o combined.txt .\a\*.txt .\b\*.md
        """,
    formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output file path"
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Input files, directories, or wildcard patterns"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Scan directories recursively and expand simple patterns recursively"
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Text encoding for reading and writing (default: utf-8)"
    )

    args = parser.parse_args()

    files = collect_files(args.inputs, args.recursive)

    if not files:
        print("No matching files found.", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding=args.encoding, newline="\n") as out:
        for i, file_path in enumerate(files, start=1):
            try:
                content = file_path.read_text(encoding=args.encoding)
            except Exception as exc:
                print(f"Skipping {file_path}: {exc}", file=sys.stderr)
                continue

            out.write(f"\n{'=' * 80}\n")
            out.write(f"FILE {i}: {file_path}\n")
            out.write(f"{'=' * 80}\n\n")
            out.write(content)

            if not content.endswith("\n"):
                out.write("\n")

    print(f"Wrote {len(files)} files to {output_path}")


if __name__ == "__main__":
    main()