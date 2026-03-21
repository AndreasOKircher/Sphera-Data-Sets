import requests


class DownloadError(Exception):
    pass


def download_xml(url: str, timeout: int = 30, headers: dict | None = None) -> bytes:
    """Fetch XML from URL. Returns raw bytes. Raises DownloadError on any failure."""
    try:
        response = requests.get(url, timeout=timeout, headers=headers or {})
        response.raise_for_status()
        return response.content  # raw bytes — untouched, no encoding round-trip
    except Exception as e:
        raise DownloadError(str(e)) from e
