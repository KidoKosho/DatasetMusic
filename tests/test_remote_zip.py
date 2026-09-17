"""Tests for RemoteZipExtractor."""

import io
from pathlib import Path
import pytest
import zipfile

from music_dataset.downloader.remote_zip import RemoteZipExtractor, RemoteZipMember


def test_remote_zip_member_repr():
    m = RemoteZipMember("test.mp3", 8, 100, 200, 1024, 12345)
    assert "test.mp3" in repr(m)
    assert m.uncomp_size == 200
    assert m.comp_size == 100
    assert m.offset == 1024


def test_extract_file_from_local_zip_via_extractor(tmp_path: Path, monkeypatch):
    # Create a small valid ZIP file
    zip_path = tmp_path / "test.zip"
    sample_content = b"ID3v2.3.0---TEST_AUDIO_CONTENT---"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("fma_small/001/001234.mp3", sample_content)

    extractor = RemoteZipExtractor("http://mock.example.com/test.zip")

    # Mock session.get to read from the local file
    class MockResponse:
        def __init__(self, data, status_code=206):
            self.content = data
            self.status_code = status_code

    def mock_get(url, headers=None, timeout=None):
        rng = headers.get("Range", "")
        if rng.startswith("bytes="):
            start_str, end_str = rng[6:].split("-")
            start = int(start_str)
            end = int(end_str) if end_str else zip_path.stat().st_size - 1
            with open(zip_path, "rb") as f:
                f.seek(start)
                chunk = f.read(end - start + 1)
            return MockResponse(chunk, 206)
        with open(zip_path, "rb") as f:
            return MockResponse(f.read(), 200)

    monkeypatch.setattr(extractor.session, "get", mock_get)

    # Test indexing
    with open(zip_path, "rb") as f:
        data = f.read()
    eocd_pos = data.rfind(b"PK\x05\x06")
    cd_size = int.from_bytes(data[eocd_pos + 12:eocd_pos + 16], "little")
    cd_offset = int.from_bytes(data[eocd_pos + 16:eocd_pos + 20], "little")

    extractor.fetch_index(known_cd_offset=cd_offset, known_cd_size=cd_size)
    assert "fma_small/001/001234.mp3" in extractor.entries

    # Test extraction
    out_file = tmp_path / "extracted.mp3"
    ok = extractor.extract_file("fma_small/001/001234.mp3", out_file)
    assert ok is True
    assert out_file.exists()
    assert out_file.read_bytes() == sample_content
