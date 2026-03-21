"""CLI for enriching Sphera LCA datasets using the Claude API."""

# Standard library
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Third-party
import anthropic
from dotenv import load_dotenv

load_dotenv()  # loads .env before using os.environ

# Local
from core.enricher import FORMAT_SYSTEM, SUMMARY_SYSTEM, verify_counts

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).parent / "dataset" / "output"
ENRICHED_DIR = Path(__file__).parent / "dataset" / "enriched"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        print(
            "[ERROR] ANTHROPIC_API_KEY is not set. Add it to .env or set it in your environment.",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------


def process_one(uuid: str, client: anthropic.Anthropic, model: str, force: bool) -> None:
    dataset_path = OUTPUT_DIR / f"{uuid}.json"
    if not dataset_path.exists():
        print(f"[SKIP] {uuid[:8]} — dataset file not found")
        return

    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    name = (data.get("name_base") or "")[:60]
    enriched_path = ENRICHED_DIR / f"{uuid}.json"

    if not force and enriched_path.exists():
        print(f"[SKIP] {uuid[:8]} — already enriched (use --force to re-enrich)")
        return

    tech = data.get("technology_description") or ""
    if not tech:
        print(f"[SKIP] {uuid[:8]} — no technology_description field")
        return

    try:
        # Summary call
        resp = client.messages.create(
            model=model,
            max_tokens=300,
            system=SUMMARY_SYSTEM,
            messages=[{"role": "user", "content": tech}],
        )
        summary = resp.content[0].text

        # Format call
        resp = client.messages.create(
            model=model,
            max_tokens=16000,
            system=FORMAT_SYSTEM,
            messages=[{"role": "user", "content": tech}],
        )
        formatted = resp.content[0].text

        counts = verify_counts(tech, formatted)

        # Build display values
        w_orig = counts["word_count"]
        w_new = counts["formatted_word_count"]
        w_diff = counts["word_count_diff"]
        w_pct = counts["word_count_diff_pct"]
        c_orig = counts["char_count"]
        c_new = counts["formatted_char_count"]
        c_diff = counts["char_count_diff"]
        c_pct = counts["char_count_diff_pct"]

        w_sign = "\u2212" if w_diff < 0 else "+"
        c_sign = "\u2212" if c_diff < 0 else "+"

        if not counts["ok"]:
            w_flag = "\u2705" if w_pct <= 2.0 else "\u274c"
            c_flag = "\u2705" if c_pct <= 2.0 else "\u274c"
            print(f"[FAIL] {uuid[:8]} — {name}")
            print(f"       Words: {w_orig:,} \u2192 {w_new:,}  ({w_sign}{abs(w_diff)} words, {w_pct:.1f}%) {w_flag}  — not saved")
            print(f"       Chars: {c_orig:,} \u2192 {c_new:,}  ({c_sign}{abs(c_diff)} chars, {c_pct:.1f}%) {c_flag}  — not saved")
            return

        # Write enriched file
        enriched = {
            "uuid": uuid,
            "enriched_at": datetime.now(tz=timezone.utc).isoformat(),
            "technology_description_word_count": w_orig,
            "technology_description_formatted_word_count": w_new,
            "technology_description_word_count_diff": w_diff,
            "technology_description_word_count_diff_pct": w_pct,
            "technology_description_char_count": c_orig,
            "technology_description_formatted_char_count": c_new,
            "technology_description_char_count_diff": c_diff,
            "technology_description_char_count_diff_pct": c_pct,
            "technology_description_summary": summary,
            "technology_description_formatted": formatted,
        }
        enriched_path.write_text(
            json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(f"[OK]   {uuid[:8]} — {name}")
        print(f"       Words: {w_orig:,} \u2192 {w_new:,}  ({w_sign}{abs(w_diff)} word{'s' if abs(w_diff) != 1 else ''}, {w_pct:.1f}%) \u2705")
        print(f"       Chars: {c_orig:,} \u2192 {c_new:,}  ({c_sign}{abs(c_diff)} char{'s' if abs(c_diff) != 1 else ''}, {c_pct:.1f}%) \u2705")
    except anthropic.APIError as exc:
        print(f"[FAIL] {uuid[:8]} — API error: {exc}", file=sys.stderr)
        return
    except Exception as exc:
        print(f"[FAIL] {uuid[:8]} — unexpected error: {exc}", file=sys.stderr)
        return


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich Sphera LCA datasets using Claude API"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--uuid", help="Enrich a single dataset by UUID")
    group.add_argument("--all", action="store_true", help="Enrich all datasets")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-enrich already enriched datasets",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Claude model ID (default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    key = _check_api_key()
    client = anthropic.Anthropic(api_key=key)
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)

    if args.uuid:
        process_one(args.uuid, client, args.model, args.force)
    else:  # --all
        if not OUTPUT_DIR.exists():
            print(
                f"[ERROR] Output directory not found: {OUTPUT_DIR}",
                file=sys.stderr,
            )
            sys.exit(1)
        uuids = [f.stem for f in sorted(OUTPUT_DIR.glob("*.json"))]
        for uuid in uuids:
            process_one(uuid, client, args.model, args.force)


if __name__ == "__main__":
    main()
