import json
import sys
from pathlib import Path


def export_dataset(data: dict, raw_xml: bytes, output_dir: Path) -> None:
    """Write <uuid>.xml and <uuid>.json to output_dir. Warns to stderr on overwrite."""
    uuid = data["uuid"]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    xml_path = output_dir / f"{uuid}.xml"
    json_path = output_dir / f"{uuid}.json"

    for path in (xml_path, json_path):
        if path.exists():
            print(f"[WARN] {path.name} already exists — overwriting", file=sys.stderr)

    xml_path.write_bytes(raw_xml)
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
