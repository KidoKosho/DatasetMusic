"""Phase 4: Download Planner. Builds targeted download_queue.jsonl strictly for candidate tracks."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class DownloadPlanner:
    """Creates a targeted download queue from candidates, ensuring no bulk multi-GB downloads occur blindly."""

    def __init__(
        self,
        manifests_dir: Path = Path("data/manifests"),
        reports_dir: Path = Path("reports"),
    ):
        self.manifests_dir = Path(manifests_dir)
        self.reports_dir = Path(reports_dir)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def plan_downloads(
        self,
        candidates_path: Optional[Path] = None,
        allow_full_archive_download: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Reads candidates.jsonl and produces download_queue.jsonl based on:
        candidate == True and (has_audio or has_lyrics or has_artwork or has_metadata)
        """
        in_path = candidates_path or (self.manifests_dir / "candidates.jsonl")
        if not in_path.exists():
            return []

        queue: List[Dict[str, Any]] = []
        out_queue_path = self.manifests_dir / "download_queue.jsonl"

        with open(in_path, "r", encoding="utf-8") as fin, open(out_queue_path, "w", encoding="utf-8") as fout:
            for line in fin:
                if not line.strip():
                    continue
                cand = json.loads(line)
                if not cand.get("candidate"):
                    continue

                audio_info = cand.get("audio", {})
                lyrics_info = cand.get("lyrics", {})
                artwork_info = cand.get("artwork", {})

                has_audio = audio_info.get("available", False)
                has_lyrics = lyrics_info.get("available", False)
                has_artwork = artwork_info.get("available", False)
                has_metadata = True

                # Download Queue Rule: Candidate must have at least one asset
                if not (has_audio or has_lyrics or has_artwork or has_metadata):
                    continue

                assets_to_download: List[str] = []
                if has_audio and not audio_info.get("downloaded"):
                    assets_to_download.append("audio")
                if has_lyrics:
                    assets_to_download.append("lyrics")
                if has_artwork:
                    assets_to_download.append("artwork")
                if has_metadata:
                    assets_to_download.append("metadata")

                # FMA & large archive check:
                # If audio is needed but only available in full multi-GB archive
                archive_download_req = False
                source = cand.get("dataset")
                if source == "fma" and "audio" in assets_to_download:
                    # Audio requires extracting specific track from FMA audio subsets
                    archive_download_req = not allow_full_archive_download

                queue_item = {
                    "track_id": cand.get("track_id"),
                    "source": source,
                    "reasons": cand.get("reasons", []),
                    "title": cand.get("title"),
                    "artist": cand.get("artist"),
                    "assets": assets_to_download,
                    "audio_target": audio_info.get("rel_path") or audio_info.get("path"),
                    "archive_download_required": archive_download_req,
                    "status": "pending",
                }

                queue.append(queue_item)
                fout.write(json.dumps(queue_item, ensure_ascii=False) + "\n")

        # Generate reports/download_queue.json
        self._write_queue_report(queue)

        return queue

    def _write_queue_report(self, queue: List[Dict[str, Any]]) -> None:
        report_data = {
            "total_items_in_queue": len(queue),
            "by_dataset": {},
            "by_asset": {"audio": 0, "lyrics": 0, "artwork": 0, "metadata": 0},
            "archive_download_required_count": 0,
            "items": queue[:100],
        }

        for item in queue:
            ds = item.get("source", "unknown")
            report_data["by_dataset"][ds] = report_data["by_dataset"].get(ds, 0) + 1
            for a in item.get("assets", []):
                if a in report_data["by_asset"]:
                    report_data["by_asset"][a] += 1
            if item.get("archive_download_required"):
                report_data["archive_download_required_count"] += 1

        (self.reports_dir / "download_queue.json").write_text(
            json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
