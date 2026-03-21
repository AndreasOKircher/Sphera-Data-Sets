import argparse
import sys
from datetime import datetime
from pathlib import Path

from core.downloader import download_xml, DownloadError
from core.exporter import export_dataset
from core.parser import parse_dataset

DEFAULT_OUTPUT = Path("dataset/output")


def process_url(url: str, output_dir: Path, headers: dict | None = None) -> bool:
    """Download, parse, and export one URL. Returns True on success."""
    url = url.strip()
    if not url:
        return True
    try:
        xml_bytes = download_xml(url, headers=headers)
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


def main():
    parser = argparse.ArgumentParser(description="Download and export Sphera LCA datasets.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Single dataset URL")
    group.add_argument("--urls", help="Path to file with one URL per line")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output directory")
    parser.add_argument("--cookie", help="Cookie header value for authenticated requests")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    headers = {"Cookie": args.cookie} if args.cookie else None

    urls = [args.url] if args.url else Path(args.urls).read_text().splitlines()
    urls = [u.strip() for u in urls if u.strip()]

    failed_urls = []
    for url in urls:
        if not process_url(url, output_dir, headers=headers):
            failed_urls.append(url)

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
