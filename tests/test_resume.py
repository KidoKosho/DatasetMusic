"""Tests for HTTP Range resume handling."""

from pathlib import Path
from music_dataset.downloader.resume import ResumeManager


def test_prepare_resume_new_file(tmp_path: Path):
    dest = tmp_path / "song.mp3"
    part_path, existing_size, headers = ResumeManager.prepare_resume(dest, resume_enabled=True)

    assert part_path == tmp_path / "song.mp3.part"
    assert existing_size == 0
    assert headers == {}


def test_prepare_resume_existing_part_file(tmp_path: Path):
    dest = tmp_path / "song.mp3"
    part_path = tmp_path / "song.mp3.part"
    part_path.write_bytes(b"EXISTING_HALF_DOWNLOAD_")

    p, existing_size, headers = ResumeManager.prepare_resume(dest, resume_enabled=True)

    assert p == part_path
    assert existing_size == len(b"EXISTING_HALF_DOWNLOAD_")
    assert headers == {"Range": f"bytes={existing_size}-"}


def test_handle_server_range_response_206(tmp_path: Path):
    dest = tmp_path / "song.mp3"
    part_path = tmp_path / "song.mp3.part"
    part_path.write_bytes(b"INITIAL_BYTES")

    mode, start_bytes = ResumeManager.handle_server_range_response(part_path, 206, len(b"INITIAL_BYTES"))
    assert mode == "ab"
    assert start_bytes == len(b"INITIAL_BYTES")


def test_handle_server_range_response_200_restarts_cleanly(tmp_path: Path):
    dest = tmp_path / "song.mp3"
    part_path = tmp_path / "song.mp3.part"
    part_path.write_bytes(b"INITIAL_BYTES")

    mode, start_bytes = ResumeManager.handle_server_range_response(part_path, 200, len(b"INITIAL_BYTES"))
    # When server responds with 200, range was not respected; .part must be removed and mode must be 'wb'
    assert mode == "wb"
    assert start_bytes == 0
    assert not part_path.exists()
