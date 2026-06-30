from unittest.mock import patch, Mock, call
from core.downloader import download_xml, DownloadError
import pytest


def test_valid_url_returns_bytes():
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"<processDataSet>test</processDataSet>"
    mock_response.raise_for_status = Mock()

    with patch("core.downloader.requests.get", return_value=mock_response):
        result = download_xml("https://example.com/test.xml")

    assert result == b"<processDataSet>test</processDataSet>"


def test_http_404_raises_download_error():
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("404 Client Error")

    with patch("core.downloader.requests.get", return_value=mock_response):
        with pytest.raises(DownloadError):
            download_xml("https://example.com/missing.xml")


def test_network_error_raises_download_error():
    with patch("core.downloader.requests.get", side_effect=Exception("Connection refused")):
        with pytest.raises(DownloadError):
            download_xml("https://example.com/test.xml")


def test_headers_passed_to_request():
    mock_response = Mock()
    mock_response.content = b"<processDataSet/>"
    mock_response.raise_for_status = Mock()

    with patch("core.downloader.requests.get", return_value=mock_response) as mock_get:
        download_xml("https://example.com/test.xml", headers={"Cookie": "session=abc"})

    mock_get.assert_called_once_with(
        "https://example.com/test.xml", timeout=30, headers={"Cookie": "session=abc"}
    )


def _make_response(status_code: int, content: bytes = b"", headers: dict | None = None) -> Mock:
    r = Mock()
    r.status_code = status_code
    r.content = content
    r.headers = headers or {}
    if status_code >= 400:
        r.raise_for_status.side_effect = Exception(f"{status_code} Client Error")
    else:
        r.raise_for_status = Mock()
    return r


def test_429_retries_then_succeeds():
    """One 429 followed by a 200 — should succeed after one retry."""
    responses = [
        _make_response(429),
        _make_response(200, b"<processDataSet/>"),
    ]
    with patch("core.downloader.requests.get", side_effect=responses):
        with patch("core.downloader.time.sleep") as mock_sleep:
            result = download_xml("https://example.com/test.xml", retries=3, retry_wait=5)

    assert result == b"<processDataSet/>"
    mock_sleep.assert_called_once_with(5)


def test_429_respects_retry_after_header():
    """Retry-After header value is used as the sleep duration."""
    responses = [
        _make_response(429, headers={"Retry-After": "45"}),
        _make_response(200, b"<processDataSet/>"),
    ]
    with patch("core.downloader.requests.get", side_effect=responses):
        with patch("core.downloader.time.sleep") as mock_sleep:
            download_xml("https://example.com/test.xml", retries=3, retry_wait=5)

    mock_sleep.assert_called_once_with(45)


def test_429_exhausts_retries_raises():
    """Persistent 429 across all retries raises DownloadError."""
    responses = [_make_response(429)] * 4  # retries=3 → 4 total attempts
    with patch("core.downloader.requests.get", side_effect=responses):
        with patch("core.downloader.time.sleep"):
            with pytest.raises(DownloadError, match="429 Too Many Requests after 3 retries"):
                download_xml("https://example.com/test.xml", retries=3, retry_wait=5)


def test_429_backoff_doubles():
    """Wait time doubles on successive 429s when no Retry-After header."""
    # retries=3, retry_wait=5: sleeps are 5, 10, 20 before the final success
    responses = [_make_response(429)] * 3 + [_make_response(200, b"<processDataSet/>")]
    with patch("core.downloader.requests.get", side_effect=responses):
        with patch("core.downloader.time.sleep") as mock_sleep:
            download_xml("https://example.com/test.xml", retries=3, retry_wait=5)

    assert mock_sleep.call_args_list == [call(5), call(10), call(20)]
