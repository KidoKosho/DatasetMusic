"""Tests for checksum calculation and verification."""

import hashlib
from pathlib import Path
from music_dataset.downloader.checksum import compute_file_sha256, verify_file_checksum


def test_compute_file_sha256(tmp_path: Path):
    test_file = tmp_path / "sample.mp3"
    content = b"TEST AUDIO CONTENT 12345"
    test_file.write_bytes(content)

    expected_hash = hashlib.sha256(content).hexdigest()
    actual_hash = compute_file_sha256(test_file)

    assert actual_hash == expected_hash
    assert verify_file_checksum(test_file, expected_hash) is True
    assert verify_file_checksum(test_file, "wrong_hash") is False
