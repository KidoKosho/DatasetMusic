"""Tests for deterministic ID generation and cross-dataset SHA-256 deduplication."""

from pathlib import Path
from music_dataset.downloader.manager import DownloaderManager
from music_dataset.schema import generate_deterministic_id


def test_deterministic_id_reproducibility():
    id1 = generate_deterministic_id("vietnam_music_genre", source_id="12345", source_relative_path="bolero/12345.mp3")
    id2 = generate_deterministic_id("vietnam_music_genre", source_id="12345", source_relative_path="bolero/12345.mp3")
    id3 = generate_deterministic_id("vietnam_music_genre", source_id="99999", source_relative_path="bolero/99999.mp3")

    assert id1 == id2
    assert id1 != id3


def test_sha256_deduplication_preserves_provenance(tmp_path: Path):
    mgr = DownloaderManager()

    file_a = tmp_path / "song_a.mp3"
    file_b = tmp_path / "song_b.mp3"
    # Same content across two datasets
    audio_content = b"IDENTICAL AUDIO CONTENT IN BOTH FMA AND VIETNAM GENRE"
    file_a.write_bytes(audio_content)
    file_b.write_bytes(audio_content)

    sha_a = mgr.register_existing_file("fma", "track_fma_1", file_a)
    sha_b = mgr.register_existing_file("vietnam_music_genre", "track_vn_1", file_b)

    assert sha_a == sha_b
    dup_entries = mgr.is_duplicate_sha256(sha_a)
    assert dup_entries is not None
    assert len(dup_entries) == 2
    datasets = [entry["dataset"] for entry in dup_entries]
    assert "fma" in datasets
    assert "vietnam_music_genre" in datasets
