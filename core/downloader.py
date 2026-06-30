import time

import requests


class DownloadError(Exception):
    pass


def download_xml(
    url: str,
    timeout: int = 30,
    headers: dict | None = None,
    retries: int = 3,
    retry_wait: int = 5,
) -> bytes:
    """Fetch XML from URL. Returns raw bytes. Raises DownloadError on any failure.

    On HTTP 429 (Too Many Requests), waits and retries up to `retries` times.
    Respects the Retry-After response header when present; otherwise uses
    exponential backoff starting at `retry_wait` seconds (doubles each attempt).
    """
    wait = retry_wait  # initial backoff seconds when no Retry-After header
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, timeout=timeout, headers=headers or {})
        except Exception as e:
            raise DownloadError(str(e)) from e

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "")
            sleep_for = int(retry_after) if retry_after.isdigit() else wait
            if attempt < retries:
                print(
                    f"[429]  Rate limited — waiting {sleep_for}s "
                    f"(retry {attempt + 1}/{retries})...",
                    flush=True,
                )
                time.sleep(sleep_for)
                wait *= 2
                continue
            raise DownloadError(f"429 Too Many Requests after {retries} retries: {url}")

        try:
            response.raise_for_status()
            return response.content
        except Exception as e:
            raise DownloadError(str(e)) from e

    raise DownloadError(f"Failed after {retries} retries: {url}")
