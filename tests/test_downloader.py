"""Tests for HTTP chunk streaming download, atomic rename, and verification."""

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from music_dataset.constants import DownloadStatus
from music_dataset.downloader.http import HttpDownloader


def test_http_download_atomic_rename_success(tmp_path: Path):
    downloader = HttpDownloader(chunk_size=1024)
    dest = tmp_path / "track_001.mp3"
    content = b"AUDIO CHUNK 1" * 50
    expected_sha = hashlib.sha256(content).hexdigest()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Length": str(len(content))}
    mock_resp.iter_content.return_value = [content[:50], content[50:]]

    with patch("requests.get", return_value=mock_resp):
        res = downloader.download(
            url="https://example.com/audio.mp3",
            destination=dest,
            expected_sha256=expected_sha,
            expected_size=len(content),
        )

    assert res.status == DownloadStatus.DOWNLOADED.value
    assert dest.exists()
    assert not (tmp_path / "track_001.mp3.part").exists()  # Atomic rename cleaned .part
    assert dest.stat().st_size == len(content)
    assert res.sha256 == expected_sha


def test_http_download_checksum_mismatch_failure(tmp_path: Path):
    downloader = HttpDownloader(chunk_size=1024)
    dest = tmp_path / "track_002.mp3"
    content = b"CORRUPTED CONTENT"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Length": str(len(content))}
    mock_resp.iter_content.return_value = [content]

    with patch("requests.get", return_value=mock_resp):
        res = downloader.download(
            url="https://example.com/bad.mp3",
            destination=dest,
            expected_sha256="expected_different_sha256",
        )

    assert res.status == DownloadStatus.FAILED.value
    assert "Checksum mismatch" in (res.error or "")
    assert not dest.exists()  # Final file not created on mismatch
