"""Data quality report generator producing Section 28 compliant reports."""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from music_dataset.schema import Track
from music_dataset.state.database import StateDatabase


class QualityReportGenerator:
    def __init__(
        self,
        state_db: Optional[StateDatabase] = None,
        reports_dir: Path = Path("reports"),
    ):
        self.state_db = state_db or StateDatabase()
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_all_reports(self, dataset: Optional[str] = None) -> Dict[str, Path]:
        tracks = self.state_db.list_tracks(dataset=dataset)
        generated: Dict[str, Path] = {}

        # 1. all_tracks.jsonl
        all_tracks_path = self.reports_dir / "all_tracks.jsonl"
        with open(all_tracks_path, "w", encoding="utf-8") as f:
            for t in tracks:
                f.write(json.dumps(t.to_unified_dict(), ensure_ascii=False) + "\n")
        generated["all_tracks_jsonl"] = all_tracks_path

        # 2. vietnamese_related.jsonl
        vi_rel_path = self.reports_dir / "vietnamese_related.jsonl"
        with open(vi_rel_path, "w", encoding="utf-8") as f:
            for t in tracks:
                status = t.vietnamese_relevance.get("status", "unknown")
                if t.is_vietnamese_song or t.is_vietnamese_lyrics or status in ("confirmed", "likely", "possible"):
                    f.write(json.dumps(t.to_unified_dict(), ensure_ascii=False) + "\n")
        generated["vietnamese_related_jsonl"] = vi_rel_path

        # 3. lyrics_found.jsonl
        lyrics_found_path = self.reports_dir / "lyrics_found.jsonl"
        with open(lyrics_found_path, "w", encoding="utf-8") as f:
            for t in tracks:
                if t.lyrics and t.lyrics.strip():
                    f.write(json.dumps(t.to_unified_dict(), ensure_ascii=False) + "\n")
        generated["lyrics_found_jsonl"] = lyrics_found_path

        # 4. lyrics_vietnamese.jsonl
        lyrics_vi_path = self.reports_dir / "lyrics_vietnamese.jsonl"
        with open(lyrics_vi_path, "w", encoding="utf-8") as f:
            for t in tracks:
                if t.is_vietnamese_lyrics is True or t.language_status == "detected_vi":
                    f.write(json.dumps(t.to_unified_dict(), ensure_ascii=False) + "\n")
        generated["lyrics_vietnamese_jsonl"] = lyrics_vi_path

        # 5. missing_metadata.jsonl & missing_metadata.csv
        missing_jsonl = self.reports_dir / "missing_metadata.jsonl"
        with open(missing_jsonl, "w", encoding="utf-8") as f:
            for t in tracks:
                if not (t.title and t.artist and t.album and t.year and t.genre and t.lyrics and t.artwork_path):
                    f.write(json.dumps(t.to_unified_dict(), ensure_ascii=False) + "\n")
        generated["missing_metadata_jsonl"] = missing_jsonl

        missing_csv = self.reports_dir / "missing_metadata.csv"
        self._write_missing_metadata_csv(missing_csv, tracks)
        generated["missing_metadata_csv"] = missing_csv

        # 6. failed_downloads.jsonl & failed_downloads.csv
        failed_jsonl = self.reports_dir / "failed_downloads.jsonl"
        self._write_failed_downloads_jsonl(failed_jsonl)
        generated["failed_downloads_jsonl"] = failed_jsonl

        failed_csv = self.reports_dir / "failed_downloads.csv"
        self._write_failed_downloads_csv(failed_csv)
        generated["failed_downloads_csv"] = failed_csv

        # 7. summary.json (Exact Section 28 structure)
        summary_data = self._compute_section28_summary(tracks)
        summary_json = self.reports_dir / "summary.json"
        summary_json.write_text(json.dumps(summary_data, ensure_ascii=False, indent=2), encoding="utf-8")
        generated["summary_json"] = summary_json

        # Extra CSV summary & duplicates
        summary_csv = self.reports_dir / "summary.csv"
        self._write_summary_csv(summary_csv, [summary_data])
        generated["summary_csv"] = summary_csv

        dup_csv = self.reports_dir / "duplicates.csv"
        self._write_duplicates_csv(dup_csv, tracks)
        generated["duplicates"] = dup_csv

        return generated

    def _compute_section28_summary(self, tracks: List[Track]) -> Dict[str, Any]:
        """Compute the exact dictionary keys defined in Section 28 of prompt."""
        total_kaggle = sum(1 for t in tracks if t.dataset == "vietnam_music_genre")
        if total_kaggle == 0:
            total_kaggle = len(tracks)

        audio_dl = sum(1 for t in tracks if t.audio_path and Path(t.audio_path).exists())
        title_found = sum(1 for t in tracks if t.title and t.title.strip())
        artist_found = sum(1 for t in tracks if t.artist and t.artist.strip())
        metadata_found = sum(1 for t in tracks if (t.title or t.artist or t.genre))
        lyrics_found = sum(1 for t in tracks if t.lyrics and t.lyrics.strip())
        vi_lyrics = sum(1 for t in tracks if t.is_vietnamese_lyrics is True or t.language_status == "detected_vi")
        vi_related = sum(
            1 for t in tracks
            if (t.is_vietnamese_song is True or t.is_vietnamese_lyrics is True or
                t.vietnamese_relevance.get("status") in ("confirmed", "likely", "possible"))
        )
        artwork_found = sum(1 for t in tracks if t.artwork_path and Path(t.artwork_path).exists())
        missing_meta = sum(1 for t in tracks if not (t.title and t.artist))

        return {
            "total_kaggle_mp3": total_kaggle,
            "audio_downloaded": audio_dl,
            "metadata_found": metadata_found,
            "artist_found": artist_found,
            "title_found": title_found,
            "lyrics_found": lyrics_found,
            "vietnamese_lyrics": vi_lyrics,
            "vietnamese_related_tracks": vi_related,
            "artwork_found": artwork_found,
            "missing_metadata": missing_meta,
        }

    def _write_summary_csv(self, path: Path, summaries: List[Dict[str, Any]]) -> None:
        if not summaries:
            return
        keys = list(summaries[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(summaries)

    def _write_missing_metadata_csv(self, path: Path, tracks: List[Track]) -> None:
        fieldnames = ["track_id", "dataset", "title", "artist", "album", "year", "genre", "lyrics", "artwork"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for t in tracks:
                if not (t.title and t.artist and t.album and t.year and t.genre and t.lyrics and t.artwork_path):
                    writer.writerow({
                        "track_id": t.track_id,
                        "dataset": t.dataset,
                        "title": "PRESENT" if t.title else "MISSING",
                        "artist": "PRESENT" if t.artist else "MISSING",
                        "album": "PRESENT" if t.album else "MISSING",
                        "year": "PRESENT" if t.year else "MISSING",
                        "genre": "PRESENT" if t.genre else "MISSING",
                        "lyrics": "PRESENT" if t.lyrics else "MISSING",
                        "artwork": "PRESENT" if t.artwork_path else "MISSING",
                    })

    def _write_failed_downloads_jsonl(self, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            with self.state_db._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM errors WHERE operation = 'download'")
                for row in cur.fetchall():
                    f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")

    def _write_failed_downloads_csv(self, path: Path) -> None:
        fieldnames = ["id", "track_id", "dataset", "operation", "error_type", "message", "timestamp"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            with self.state_db._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, track_id, dataset, operation, error_type, message, timestamp FROM errors")
                for row in cur.fetchall():
                    writer.writerow(dict(row))

    def _write_duplicates_csv(self, path: Path, tracks: List[Track]) -> None:
        fieldnames = ["sha256", "track_id", "dataset", "title", "artist", "audio_path"]
        by_sha: Dict[str, List[Track]] = {}
        for t in tracks:
            if t.sha256:
                by_sha.setdefault(t.sha256, []).append(t)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for sha, group in by_sha.items():
                if len(group) > 1:
                    for t in group:
                        writer.writerow({
                            "sha256": sha,
                            "track_id": t.track_id,
                            "dataset": t.dataset,
                            "title": t.title or "",
                            "artist": t.artist or "",
                            "audio_path": t.audio_path or "",
                        })
