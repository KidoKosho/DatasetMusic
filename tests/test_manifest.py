"""Tests for Manifest manager tracking and status transitions."""

from pathlib import Path
from music_dataset.constants import DownloadStatus
from music_dataset.manifest.manager import ManifestManager
from music_dataset.schema import Track


def test_manifest_lifecycle(tmp_path: Path):
    manifest_mgr = ManifestManager(manifests_dir=tmp_path)
    track = Track(
        track_id="t101",
        dataset="vietnam_music_genre",
        source_id="101",
        title="Nỗi Buồn Gác Trọ",
        artist="Phương Dung",
        genre_original="Bolero",
        genre="bolero",
    )

    # 1. Record pending entry
    entry = manifest_mgr.record_track(track, download_status=DownloadStatus.PENDING.value)
    manifest_mgr.save_manifest_entries("vietnam_music_genre", [entry])

    items = manifest_mgr.load_manifest("vietnam_music_genre")
    assert len(items) == 1
    assert items[0]["track_id"] == "t101"
    assert items[0]["download"]["status"] == DownloadStatus.PENDING.value

    # 2. Update to downloaded
    manifest_mgr.update_download_status(
        dataset="vietnam_music_genre",
        track_id="t101",
        status=DownloadStatus.DOWNLOADED.value,
        size=4500123,
        sha256="abc123sha",
    )

    items_after = manifest_mgr.load_manifest("vietnam_music_genre")
    assert len(items_after) == 1
    assert items_after[0]["download"]["status"] == DownloadStatus.DOWNLOADED.value
    assert items_after[0]["download"]["size"] == 4500123
    assert items_after[0]["download"]["sha256"] == "abc123sha"
    assert items_after[0]["download"]["attempts"] == 1
