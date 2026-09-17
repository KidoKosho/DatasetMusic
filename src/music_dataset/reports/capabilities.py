"""Generates reports/dataset_capabilities.json for all 4 datasets."""

import json
from pathlib import Path
from typing import Any, Dict, List
from music_dataset.datasets.fma import FmaAdapter
from music_dataset.datasets.million_song_dataset import MillionSongDatasetAdapter
from music_dataset.datasets.upf import UpfAdapter
from music_dataset.datasets.vietnam_music_genre import VietnamMusicGenreAdapter


def generate_capabilities_report(
    reports_dir: Path = Path("reports"),
    raw_dir: Path = Path("data/raw"),
) -> Path:
    """Inspect all 4 datasets and write reports/dataset_capabilities.json."""
    rep_dir = Path(reports_dir)
    rep_dir.mkdir(parents=True, exist_ok=True)

    adapters = [
        MillionSongDatasetAdapter(raw_dir=raw_dir),
        FmaAdapter(raw_dir=raw_dir),
        UpfAdapter(raw_dir=raw_dir),
        VietnamMusicGenreAdapter(raw_dir=raw_dir),
    ]

    capabilities: List[Dict[str, Any]] = []
    for adapter in adapters:
        info = adapter.inspect()
        capabilities.append(info)

    out_file = rep_dir / "dataset_capabilities.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(capabilities, f, ensure_ascii=False, indent=2)

    return out_file
