"""Tests for DownloadPlanner and download_queue logic."""

import json
from pathlib import Path
import pytest

from music_dataset.pipeline.planner import DownloadPlanner


def test_download_planner_filtering(tmp_path: Path):
    candidates_file = tmp_path / "candidates.jsonl"
    planner = DownloadPlanner(manifests_dir=tmp_path, reports_dir=tmp_path)

    # Prepare candidate sample
    track1 = {
        "track_id": "track-001",
        "dataset": "fma",
        "candidate": True,
        "reasons": ["vietnamese_artist"],
        "title": "Song 1",
        "artist": "VN Artist",
        "audio": {"available": True, "downloaded": False, "rel_path": "000/000001.mp3"},
        "lyrics": {"available": False},
        "artwork": {"available": False},
    }
    track2 = {
        "track_id": "track-002",
        "dataset": "fma",
        "candidate": False,  # Non-candidate!
        "reasons": [],
        "title": "Non VN Song",
        "audio": {"available": True},
    }

    with open(candidates_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(track1) + "\n")
        f.write(json.dumps(track2) + "\n")

    queue = planner.plan_downloads(candidates_path=candidates_file)

    # Verify only candidate is queued
    assert len(queue) == 1
    assert queue[0]["track_id"] == "track-001"
    assert "audio" in queue[0]["assets"]
    # Check default archive policy blocks multi-GB auto download
    assert queue[0]["archive_download_required"] is True


def test_download_planner_empty_assets(tmp_path: Path):
    candidates_file = tmp_path / "candidates.jsonl"
    planner = DownloadPlanner(manifests_dir=tmp_path, reports_dir=tmp_path)

    track_no_assets = {
        "track_id": "track-003",
        "dataset": "other",
        "candidate": True,
        "reasons": ["vietnamese_title"],
        "audio": {"available": False},
        "lyrics": {"available": False},
        "artwork": {"available": False},
    }
    with open(candidates_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(track_no_assets) + "\n")

    queue = planner.plan_downloads(candidates_path=candidates_file)
    assert len(queue) == 1
    assert queue[0]["assets"] == ["metadata"]
