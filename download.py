import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from core.downloader import download_xml, DownloadError
from core.exporter import export_dataset
from core.parser import parse_dataset
from core.xls_manifest import load_manifest, get_uuids_for_databases, ManifestEntry

DEFAULT_OUTPUT = Path("dataset/output")


def process_url(url: str, output_dir: Path, headers: dict | None = None, retry_wait: int = 5) -> bool:
    """Download, parse, and export one URL. Returns True on success."""
    url = url.strip()
    if not url:
        return True
    try:
        xml_bytes = download_xml(url, headers=headers, retry_wait=retry_wait)
        data = parse_dataset(xml_bytes)
        uuid = data.get("uuid", "unknown")
        name = data.get("name_base", "")
        export_dataset(data, xml_bytes, output_dir)
        print(f"[OK]   {uuid} — {name}")
        return True
    except DownloadError as e:
        print(f"[FAIL] {url} — {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[FAIL] {url} — unexpected error: {e}", file=sys.stderr)
        return False


def process_url_from_manifest(
    entry: ManifestEntry,
    output_dir: Path,
    headers: dict | None = None,
    retry_wait: int = 5,
) -> str:
    """Download and export one manifest entry. Returns 'ok', 'skip', or 'fail'."""
    json_path = output_dir / f"{entry.uuid}.json"
    if json_path.exists():
        print(f"[SKIP] {entry.uuid} — already exists")
        return "skip"
    try:
        xml_bytes = download_xml(entry.source_url, headers=headers, retry_wait=retry_wait)
        data = parse_dataset(xml_bytes)
        # Inject manifest-sourced fields into the data model
        data["source_url"] = entry.source_url
        data["process_type"] = entry.process_type
        data["databases"] = entry.databases
        export_dataset(data, xml_bytes, output_dir)
        print(f"[OK]   {entry.uuid} — {data.get('name_base', '')}")
        return "ok"
    except DownloadError as e:
        print(f"[FAIL] {entry.uuid} — {e}", file=sys.stderr)
        return "fail"
    except Exception as e:
        print(f"[FAIL] {entry.uuid} — unexpected error: {e}", file=sys.stderr)
        return "fail"


def main():
    parser = argparse.ArgumentParser(description="Download and export Sphera LCA datasets.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Single dataset URL")
    group.add_argument("--urls", help="Path to file with one URL per line")
    group.add_argument("--xls", help="Path to Sphera XLS manifest file")
    parser.add_argument(
        "--databases",
        nargs="+",
        default=None,
        help='Filter to specific databases (e.g. "Professional database 2026")',
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output directory")
    parser.add_argument("--cookie", help="Cookie header value for authenticated requests")
    parser.add_argument("--cookie-file", help="Path to a text file containing the cookie value")
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to wait between download requests (default: 1.0)",
    )
    parser.add_argument(
        "--retry-wait",
        type=int,
        default=5,
        help="Initial seconds to wait after a 429 before retrying; doubles each attempt (default: 5)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    cookie = args.cookie
    if args.cookie_file:
        cookie = Path(args.cookie_file).read_text(encoding="utf-8").strip()
    headers = None
    if cookie:
        headers = {
            "Cookie": cookie,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
        }

    if args.xls:
        manifest = load_manifest(args.xls)
        if args.databases:
            uuids = get_uuids_for_databases(manifest, args.databases)
            entries = [manifest[u] for u in uuids if u in manifest]
        else:
            entries = list(manifest.values())

        counts = {"ok": 0, "skip": 0, "fail": 0}
        failed_entries = []
        for entry in entries:
            result = process_url_from_manifest(entry, output_dir, headers=headers, retry_wait=args.retry_wait)
            counts[result] += 1
            if result == "fail":
                failed_entries.append(entry)
            if result != "skip" and args.delay > 0:
                time.sleep(args.delay)

        print(f"\nDone. {counts['ok']} ok · {counts['skip']} skipped · {counts['fail']} failed.")
        if failed_entries:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            fail_file = output_dir / f"failed_uuids_{timestamp}.txt"
            fail_file.write_text(
                "\n".join(e.source_url for e in failed_entries), encoding="utf-8"
            )
            print(f"Failed URLs saved to: {fail_file} (retry with --urls)")
            sys.exit(1)
        return

    urls = [args.url] if args.url else Path(args.urls).read_text().splitlines()
    urls = [u.strip() for u in urls if u.strip()]

    failed_urls = []
    for i, url in enumerate(urls):
        if not process_url(url, output_dir, headers=headers, retry_wait=args.retry_wait):
            failed_urls.append(url)
        if i < len(urls) - 1 and args.delay > 0:
            time.sleep(args.delay)

    total = len(urls)
    succeeded = total - len(failed_urls)
    print(f"\nDone. {succeeded}/{total} succeeded, {len(failed_urls)} failed.")

    if failed_urls:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        fail_file = output_dir / f"failed_urls_{timestamp}.txt"
        fail_file.write_text("\n".join(failed_urls), encoding="utf-8")
        print(f"Failed URLs saved to: {fail_file}")


if __name__ == "__main__":
    main()
