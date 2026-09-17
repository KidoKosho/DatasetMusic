"""Manifest file manager for tracking dataset records."""

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from music_dataset.constants import DownloadStatus
from music_dataset.schema import Track


class ManifestManager:
    def __init__(self, manifests_dir: Path = Path("data/manifests")):
        self.manifests_dir = Path(manifests_dir)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)

    def get_manifest_path(self, dataset: str) -> Path:
        return self.manifests_dir / f"{dataset}_manifest.jsonl"

    def record_track(
        self,
        track: Track,
        download_status: str = DownloadStatus.PENDING.value,
        download_url: str = "",
        size: int = 0,
        sha256: Optional[str] = None,
        attempts: int = 0,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Convert track to manifest entry and append or update."""
        entry = {
            "track_id": track.track_id,
            "dataset": track.dataset,
            "source_id": track.source_id,
            "source_relative_path": track.source_relative_path or "",
            "source_filename": track.source_filename or "",
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "year": track.year,
            "genre_original": track.genre_original,
            "genre": track.genre,
            "is_vietnamese_song": track.is_vietnamese_song,
            "is_vietnamese_lyrics": track.is_vietnamese_lyrics,
            "language_status": track.language_status,
            "language_confidence": track.language_confidence,
            "download": {
                "url": download_url or track.source_url,
                "status": download_status,
                "attempts": attempts,
                "size": size,
                "sha256": sha256 or track.sha256 or "",
            },
        }
        if extra:
            entry["extra"] = extra
        return entry

    def save_manifest_entries(self, dataset: str, entries: List[Dict[str, Any]]) -> Path:
        manifest_path = self.get_manifest_path(dataset)
        existing_by_id = {}
        if manifest_path.exists():
            for line in manifest_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        item = json.loads(line)
                        existing_by_id[item.get("track_id")] = item
                    except json.JSONDecodeError:
                        continue

        for e in entries:
            existing_by_id[e.get("track_id")] = e

        with open(manifest_path, "w", encoding="utf-8") as f:
            for item in existing_by_id.values():
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        return manifest_path

    def update_download_status(
        self,
        dataset: str,
        track_id: str,
        status: str,
        size: Optional[int] = None,
        sha256: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        manifest_path = self.get_manifest_path(dataset)
        if not manifest_path.exists():
            return

        lines = manifest_path.read_text(encoding="utf-8").splitlines()
        updated = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            if item.get("track_id") == track_id:
                if "download" not in item:
                    item["download"] = {}
                item["download"]["status"] = status
                if size is not None:
                    item["download"]["size"] = size
                if sha256 is not None:
                    item["download"]["sha256"] = sha256
                if error is not None:
                    item["download"]["error"] = error
                item["download"]["attempts"] = item["download"].get("attempts", 0) + 1
            updated.append(item)

        with open(manifest_path, "w", encoding="utf-8") as f:
            for item in updated:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def load_manifest(self, dataset: str) -> List[Dict[str, Any]]:
        manifest_path = self.get_manifest_path(dataset)
        if not manifest_path.exists():
            return []
        items = []
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return items
