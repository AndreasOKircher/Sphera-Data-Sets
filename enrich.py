"""CLI for enriching Sphera LCA datasets using the Claude or VIO API ."""

# Standard library
import argparse
import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Third-party
import anthropic
from core.llm import create_llm_client, LLMClient
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

MODEL_FROM_ENV = os.environ.get("LLM_MODEL", DEFAULT_MODEL)



DEFAULT_WORKERS = 4
BATCH_REQUEST_LIMIT = 10_000  # Anthropic max requests per batch (each dataset = 2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    client: LLMClient,
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
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_summary = ex.submit(client.complete, SUMMARY_SYSTEM, tech, 300)
            f_format  = ex.submit(client.complete, FORMAT_SYSTEM,   tech, 16000)
            summary   = f_summary.result()
            formatted = f_format.result()

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

    except Exception as exc:
        out(f"[FAIL] {uuid[:8]} — error: {exc}")


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------


def _collect_batch_items(
    uuids: list[str],
    force: bool,
    cache: dict,
) -> tuple[list[dict], dict, dict]:
    """Scan datasets and split into API items vs dedup copies vs skips.

    Returns
    -------
    items      — list of {uuid, tech, name, h} that need API calls
    dedup_map  — {uuid: source_uuid} to copy after the batch completes
    skip_counts — {"already_enriched", "no_tech", "too_short"} counts
    """
    items: list[dict] = []
    dedup_map: dict[str, str] = {}
    seen_hashes: dict[str, str] = {}  # hash -> primary uuid within this batch run
    skip_counts = {"already_enriched": 0, "no_tech": 0, "too_short": 0}

    for uuid in uuids:
        dataset_path = OUTPUT_DIR / f"{uuid}.json"
        if not dataset_path.exists():
            continue

        enriched_path = ENRICHED_DIR / f"{uuid}.json"
        if not force and enriched_path.exists():
            skip_counts["already_enriched"] += 1
            continue

        try:
            data = json.loads(dataset_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        tech = data.get("technology_description") or ""
        if not tech:
            skip_counts["no_tech"] += 1
            continue

        if count_words(tech) < 100:
            skip_counts["too_short"] += 1
            continue

        h = _text_hash(tech)

        # Already-enriched source in persistent cache → copy later
        source_uuid = cache.get(h)
        if source_uuid and source_uuid != uuid and (ENRICHED_DIR / f"{source_uuid}.json").exists():
            dedup_map[uuid] = source_uuid
            continue

        # Duplicate within this batch run → copy from primary after batch
        if h in seen_hashes and seen_hashes[h] != uuid:
            dedup_map[uuid] = seen_hashes[h]
        else:
            seen_hashes[h] = uuid
            items.append({
                "uuid": uuid,
                "tech": tech,
                "name": (data.get("name_base") or "")[:60],
                "h": h,
            })

    return items, dedup_map, skip_counts


def _apply_dedup_copies(dedup_map: dict[str, str]) -> None:
    """Copy enriched sidecars from source UUIDs to duplicate UUIDs."""
    for uuid, source_uuid in dedup_map.items():
        source_path = ENRICHED_DIR / f"{source_uuid}.json"
        enriched_path = ENRICHED_DIR / f"{uuid}.json"
        if not source_path.exists():
            print(f"[WARN]  {uuid[:8]} — dedup source {source_uuid[:8]} not found, skipping copy")
            continue
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
            print(f"[DEDUP] {uuid[:8]} — copied from {source_uuid[:8]}")
        except Exception as exc:
            print(f"[WARN]  {uuid[:8]} — dedup copy failed: {exc}")


def run_batch(
    uuids: list[str],
    client,
    model: str,
    force: bool,
    threshold: float,
    cache: dict,
    cache_lock: threading.Lock,
) -> None:
    """Submit all pending datasets as Anthropic message batches and process results.

    Each dataset produces 2 batch requests (summary + format). Batches are
    capped at BATCH_REQUEST_LIMIT requests; larger runs are split automatically.
    """
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)

    items, dedup_map, skip_counts = _collect_batch_items(uuids, force, cache)

    print(f"  {skip_counts['already_enriched']} already enriched (skipped)")
    print(f"  {skip_counts['no_tech']} no technology_description (skipped)")
    print(f"  {skip_counts['too_short']} too short (<100 words, skipped)")
    print(f"  {len(dedup_map)} duplicates (will copy after batch)")
    print(f"  {len(items)} datasets → {len(items) * 2} API requests\n")

    if not items:
        _apply_dedup_copies(dedup_map)
        print("Nothing to submit.")
        return

    # Split into chunks: 2 requests per dataset, max BATCH_REQUEST_LIMIT per batch
    max_per_chunk = BATCH_REQUEST_LIMIT // 2
    chunks = [items[i:i + max_per_chunk] for i in range(0, len(items), max_per_chunk)]

    all_results: dict[str, str] = {}  # custom_id -> response text

    for chunk_idx, chunk in enumerate(chunks):
        label = f"batch {chunk_idx + 1}/{len(chunks)} " if len(chunks) > 1 else ""
        print(f"Submitting {label}({len(chunk)} datasets, {len(chunk) * 2} requests)…")

        requests = []
        for item in chunk:
            requests.append({
                "custom_id": f"{item['uuid']}_summary",
                "params": {
                    "model": model,
                    "max_tokens": 300,
                    "system": [{"type": "text", "text": SUMMARY_SYSTEM, "cache_control": {"type": "ephemeral"}}],
                    "messages": [{"role": "user", "content": item["tech"]}],
                },
            })
            requests.append({
                "custom_id": f"{item['uuid']}_format",
                "params": {
                    "model": model,
                    "max_tokens": 16000,
                    "system": [{"type": "text", "text": FORMAT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
                    "messages": [{"role": "user", "content": item["tech"]}],
                },
            })

        batch = client.messages.batches.create(requests=requests)
        batch_id = batch.id
        print(f"Batch ID: {batch_id}")
        print("Polling for completion (Anthropic batch processing may take minutes to hours)…")

        while True:
            batch = client.messages.batches.retrieve(batch_id)
            rc = batch.request_counts
            print(f"  [{batch.processing_status}]  processing={rc.processing}  "
                  f"succeeded={rc.succeeded}  errored={rc.errored}")
            if batch.processing_status == "ended":
                break
            time.sleep(60)

        print("Collecting results…")
        for result in client.messages.batches.results(batch_id):
            if result.result.type == "succeeded":
                all_results[result.custom_id] = result.result.message.content[0].text
            else:
                uid = result.custom_id.split("_")[0]
                print(f"[FAIL] {uid[:8]} — batch request error: {result.result.error}")

    # ── Process results ──────────────────────────────────────────────────────
    print("\nProcessing results…")
    ok_count = fail_count = 0

    for item in items:
        uuid = item["uuid"]
        summary = all_results.get(f"{uuid}_summary")
        formatted = all_results.get(f"{uuid}_format")

        if summary is None or formatted is None:
            print(f"[FAIL] {uuid[:8]} — {item['name']} — missing batch result")
            fail_count += 1
            continue

        tech = item["tech"]
        counts = verify_counts(tech, formatted, threshold_pct=threshold)

        w_orig = counts["word_count"]
        w_new  = counts["formatted_word_count"]
        w_diff = counts["word_count_diff"]
        w_pct  = counts["word_count_diff_pct"]
        c_orig = counts["char_count"]
        c_new  = counts["formatted_char_count"]
        c_diff = counts["char_count_diff"]
        c_pct  = counts["char_count_diff_pct"]

        if not counts["ok"]:
            print(f"[FAIL] {uuid[:8]} — {item['name']} — "
                  f"diff too large (words {w_pct:.1f}%, chars {c_pct:.1f}%)")
            fail_count += 1
            continue

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
        enriched_path = ENRICHED_DIR / f"{uuid}.json"
        enriched_path.write_text(
            json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        with cache_lock:
            if item["h"] not in cache:
                cache[item["h"]] = uuid

        w_sign = "\u2212" if w_diff < 0 else "+"
        c_sign = "\u2212" if c_diff < 0 else "+"
        print(f"[OK]   {uuid[:8]} — {item['name']}")
        print(f"       Words: {w_orig:,} \u2192 {w_new:,}  ({w_sign}{abs(w_diff)}, {w_pct:.1f}%) \u2705")
        print(f"       Chars: {c_orig:,} \u2192 {c_new:,}  ({c_sign}{abs(c_diff)}, {c_pct:.1f}%) \u2705")
        ok_count += 1

    _save_cache(cache, cache_lock)

    if dedup_map:
        print(f"\nCopying {len(dedup_map)} duplicate datasets…")
        _apply_dedup_copies(dedup_map)

    print(f"\n{'─' * 48}")
    print(f"Batch complete: {ok_count} OK · {fail_count} failed · {len(dedup_map)} deduped.")


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
    parser.add_argument("--batch",     action="store_true", help="Use Anthropic batch API (async, ~50%% cheaper, no parallel workers)")
    parser.add_argument("--threshold", type=float, default=6.0, help="Max allowed word/char count deviation in %% (default: 6.0)")
    parser.add_argument("--workers",   type=int, default=DEFAULT_WORKERS, help=f"Parallel dataset workers (default: {DEFAULT_WORKERS})")
    parser.add_argument(    "--model",    default=MODEL_FROM_ENV,    help=f"LLM model ID (default: {MODEL_FROM_ENV})",)
    parser.add_argument("--provider", default="anthropic", choices=["anthropic", "vio"],
                        help="LLM provider (default: anthropic)")
    args = parser.parse_args()

    if args.provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            print("[ERROR] ANTHROPIC_API_KEY not set.", file=sys.stderr)
            sys.exit(1)
        llm_client = create_llm_client("anthropic", api_key=api_key, model=args.model)
    else:
        api_key = os.environ.get("API_TOKEN", "")
        if not api_key:
            print("[ERROR] API_TOKEN not set.", file=sys.stderr)
            sys.exit(1)
        base_url  = os.environ.get("VIO_BASE_URL", "https://vio.automotive-wan.com:446")
        tenant_id = os.environ.get("VIO_TENANT_ID", "default_tenant")
        llm_client = create_llm_client("vio", api_key=api_key, model=args.model,
                                       base_url=base_url, tenant_id=tenant_id)

    if args.batch and args.provider != "anthropic":
        print("[ERROR] --batch is only supported with --provider anthropic.", file=sys.stderr)
        sys.exit(1)

    print(f"[LLM]  provider: {args.provider}  ·  model: {args.model}")

    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    DEDUP_DIR.mkdir(parents=True, exist_ok=True)

    cache_lock = threading.Lock()
    print_lock = threading.Lock()

    if args.uuid:
        cache = _load_cache()
        process_one(args.uuid, llm_client, args.force, args.threshold,
                    cache, cache_lock, print_lock)
        return

    # --all
    if not OUTPUT_DIR.exists():
        print(f"[ERROR] Output directory not found: {OUTPUT_DIR}", file=sys.stderr)
        sys.exit(1)

    uuids = [f.stem for f in sorted(OUTPUT_DIR.glob("*.json"))]

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
          f"(~{deduped} will be copied without an API call)\n")

    if args.batch:
        raw_anthropic = anthropic.Anthropic(api_key=api_key)
        run_batch(uuids, raw_anthropic, args.model, args.force, args.threshold, cache, cache_lock)
        return

    workers = min(args.workers, len(uuids))
    print(f"Starting {workers} workers…")

    if workers == 1:
        for uuid in uuids:
            process_one(uuid, llm_client, args.force, args.threshold,
                        cache, cache_lock, print_lock)
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(
                    process_one, uuid, llm_client, args.force,
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
