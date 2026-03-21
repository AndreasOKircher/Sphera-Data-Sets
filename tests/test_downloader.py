from unittest.mock import patch, Mock
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
