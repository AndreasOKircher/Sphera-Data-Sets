"""CLI for enriching Sphera LCA datasets using the Claude API."""

# Standard library
import argparse
import hashlib
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Third-party
import anthropic
from dotenv import load_dotenv

load_dotenv()  # loads .env before using os.environ

# Local
from core.enricher import FORMAT_SYSTEM, SUMMARY_SYSTEM, count_words, verify_counts

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_DIR   = Path(__file__).parent / "dataset" / "output"
ENRICHED_DIR = Path(__file__).parent / "dataset" / "enriched"
DEDUP_DIR    = Path(__file__).parent / "dataset" / "dedup"
TEXT_CACHE_FILE = DEDUP_DIR / "text_cache.json"

DEFAULT_MODEL   = "claude-haiku-4-5-20251001"
DEFAULT_WORKERS = 4


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


def _text_hash(text: str) -> str:
    """Stable SHA-256 of normalised text (lowercase, collapsed whitespace)."""
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _load_cache() -> dict:
    if TEXT_CACHE_FILE.exists():
        try:
            return json.loads(TEXT_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict, lock: threading.Lock) -> None:
    DEDUP_DIR.mkdir(parents=True, exist_ok=True)
    with lock:
        TEXT_CACHE_FILE.write_text(
            json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------


def process_one(
    uuid: str,
    client: anthropic.Anthropic,
    model: str,
    force: bool,
    threshold: float,
    cache: dict,
    cache_lock: threading.Lock,
    print_lock: threading.Lock,
) -> None:
    def out(*args, **kwargs):
        with print_lock:
            print(*args, **kwargs)

    dataset_path = OUTPUT_DIR / f"{uuid}.json"
    if not dataset_path.exists():
        out(f"[SKIP] {uuid[:8]} — dataset file not found")
        return

    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    name = (data.get("name_base") or "")[:60]
    enriched_path = ENRICHED_DIR / f"{uuid}.json"

    if not force and enriched_path.exists():
        out(f"[SKIP] {uuid[:8]} — already enriched")
        return

    tech = data.get("technology_description") or ""
    if not tech:
        out(f"[SKIP] {uuid[:8]} — no technology_description field")
        return

    word_count = count_words(tech)
    if word_count < 100:
        out(f"[SKIP] {uuid[:8]} — too short ({word_count} words, min 100)")
        return

    # ── Deduplication check ──────────────────────────────────────────────────
    h = _text_hash(tech)
    with cache_lock:
        source_uuid = cache.get(h)

    if source_uuid and source_uuid != uuid:
        source_path = ENRICHED_DIR / f"{source_uuid}.json"
        if source_path.exists():
            try:
                source_enriched = json.loads(source_path.read_text(encoding="utf-8"))
                deduped = {
                    **source_enriched,
                    "uuid": uuid,
                    "enriched_at": datetime.now(tz=timezone.utc).isoformat(),
                    "dedup_source": source_uuid,
                }
                enriched_path.write_text(
                    json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                out(f"[DEDUP] {uuid[:8]} — {name}  (copied from {source_uuid[:8]})")
                return
            except Exception as exc:
                out(f"[WARN]  {uuid[:8]} — dedup copy failed ({exc}), processing normally")

    # ── API calls ────────────────────────────────────────────────────────────
    try:
        def _summary_call():
            return client.messages.create(
                model=model, max_tokens=300, system=SUMMARY_SYSTEM,
                messages=[{"role": "user", "content": tech}],
            )

        def _format_call():
            return client.messages.create(
                model=model, max_tokens=16000, system=FORMAT_SYSTEM,
                messages=[{"role": "user", "content": tech}],
            )

        with ThreadPoolExecutor(max_workers=2) as ex:
            f_summary = ex.submit(_summary_call)
            f_format  = ex.submit(_format_call)
            summary   = f_summary.result().content[0].text
            formatted = f_format.result().content[0].text

        counts = verify_counts(tech, formatted, threshold_pct=threshold)

        w_orig = counts["word_count"]
        w_new  = counts["formatted_word_count"]
        w_diff = counts["word_count_diff"]
        w_pct  = counts["word_count_diff_pct"]
        c_orig = counts["char_count"]
        c_new  = counts["formatted_char_count"]
        c_diff = counts["char_count_diff"]
        c_pct  = counts["char_count_diff_pct"]
        w_sign = "\u2212" if w_diff < 0 else "+"
        c_sign = "\u2212" if c_diff < 0 else "+"

        orig_preview = tech[:300].replace("\n", " ")
        out(f"\n  Original : {orig_preview}{'...' if len(tech) > 300 else ''}")
        out(f"  Summary  : {summary.strip()}")

        if not counts["ok"]:
            w_flag = "\u2705" if w_pct <= threshold else "\u274c"
            c_flag = "\u2705" if c_pct <= threshold else "\u274c"
            fmt_preview = formatted[:300].replace("\n", " ")
            out(f"  Formatted: {fmt_preview}{'...' if len(formatted) > 300 else ''}")
            out(f"[FAIL] {uuid[:8]} — {name}")
            out(f"       Words: {w_orig:,} \u2192 {w_new:,}  ({w_sign}{abs(w_diff)} words, {w_pct:.1f}%) {w_flag}  — not saved")
            out(f"       Chars: {c_orig:,} \u2192 {c_new:,}  ({c_sign}{abs(c_diff)} chars, {c_pct:.1f}%) {c_flag}  — not saved")
            return

        enriched = {
            "uuid": uuid,
            "enriched_at": datetime.now(tz=timezone.utc).isoformat(),
            "technology_description_word_count":           w_orig,
            "technology_description_formatted_word_count": w_new,
            "technology_description_word_count_diff":      w_diff,
            "technology_description_word_count_diff_pct":  w_pct,
            "technology_description_char_count":           c_orig,
            "technology_description_formatted_char_count": c_new,
            "technology_description_char_count_diff":      c_diff,
            "technology_description_char_count_diff_pct":  c_pct,
            "technology_description_summary":   summary,
            "technology_description_formatted": formatted,
        }
        enriched_path.write_text(
            json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Add to dedup cache
        with cache_lock:
            if h not in cache:
                cache[h] = uuid
        _save_cache(cache, cache_lock)

        out(f"[OK]   {uuid[:8]} — {name}")
        out(f"       Words: {w_orig:,} \u2192 {w_new:,}  ({w_sign}{abs(w_diff)} word{'s' if abs(w_diff) != 1 else ''}, {w_pct:.1f}%) \u2705")
        out(f"       Chars: {c_orig:,} \u2192 {c_new:,}  ({c_sign}{abs(c_diff)} char{'s' if abs(c_diff) != 1 else ''}, {c_pct:.1f}%) \u2705")

    except anthropic.APIError as exc:
        out(f"[FAIL] {uuid[:8]} — API error: {exc}")
    except Exception as exc:
        out(f"[FAIL] {uuid[:8]} — unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Pre-scan
# ---------------------------------------------------------------------------


def _prescan(uuids: list[str]) -> dict:
    """Build a {text_hash: uuid} map by scanning all dataset files.

    Already-enriched UUIDs are preferred as the dedup source so that
    subsequent runs can copy from existing sidecars without re-calling
    the API.  For unenriched datasets the first UUID encountered for
    each unique hash becomes the primary.
    """
    cache: dict = {}

    # Pass 1 — already-enriched datasets get priority as sources
    for uuid in uuids:
        if not (ENRICHED_DIR / f"{uuid}.json").exists():
            continue
        path = OUTPUT_DIR / f"{uuid}.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            tech = data.get("technology_description") or ""
            if tech and count_words(tech) >= 100:
                h = _text_hash(tech)
                if h not in cache:
                    cache[h] = uuid
        except Exception:
            pass

    # Pass 2 — unenriched datasets: register first occurrence of each new hash
    for uuid in uuids:
        if (ENRICHED_DIR / f"{uuid}.json").exists():
            continue
        path = OUTPUT_DIR / f"{uuid}.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            tech = data.get("technology_description") or ""
            if tech and count_words(tech) >= 100:
                h = _text_hash(tech)
                if h not in cache:
                    cache[h] = uuid
        except Exception:
            pass

    return cache


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
    parser.add_argument("--force",     action="store_true", help="Re-enrich already enriched datasets")
    parser.add_argument("--model",     default=DEFAULT_MODEL, help=f"Claude model ID (default: {DEFAULT_MODEL})")
    parser.add_argument("--threshold", type=float, default=6.0, help="Max allowed word/char count deviation in %% (default: 6.0)")
    parser.add_argument("--workers",   type=int, default=DEFAULT_WORKERS, help=f"Parallel dataset workers (default: {DEFAULT_WORKERS})")
    args = parser.parse_args()

    key = _check_api_key()
    client = anthropic.Anthropic(api_key=key)
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    DEDUP_DIR.mkdir(parents=True, exist_ok=True)

    cache_lock = threading.Lock()
    print_lock = threading.Lock()

    if args.uuid:
        cache = _load_cache()
        process_one(args.uuid, client, args.model, args.force, args.threshold,
                    cache, cache_lock, print_lock)
        return

    # --all
    if not OUTPUT_DIR.exists():
        print(f"[ERROR] Output directory not found: {OUTPUT_DIR}", file=sys.stderr)
        sys.exit(1)

    uuids = [f.stem for f in sorted(OUTPUT_DIR.glob("*.json"))]
    workers = min(args.workers, len(uuids))

    # Build dedup map: pre-scan all datasets, then merge with persistent cache
    # (persistent cache wins for already-known hashes)
    print(f"Scanning {len(uuids)} datasets for duplicates…")
    scan_cache  = _prescan(uuids)
    saved_cache = _load_cache()
    cache = {**scan_cache, **saved_cache}  # saved_cache takes priority
    _save_cache(cache, cache_lock)

    unique   = len({v for v in cache.values()})
    deduped  = len(uuids) - unique  # rough lower bound
    print(f"Found {unique} unique texts across {len(uuids)} datasets "
          f"(~{deduped} will be copied without an API call)")
    print(f"Starting {workers} workers…")

    if workers == 1:
        for uuid in uuids:
            process_one(uuid, client, args.model, args.force, args.threshold,
                        cache, cache_lock, print_lock)
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(
                    process_one, uuid, client, args.model, args.force,
                    args.threshold, cache, cache_lock, print_lock
                ): uuid
                for uuid in uuids
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    uuid = futures[future]
                    print(f"[FAIL] {uuid[:8]} — worker exception: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
