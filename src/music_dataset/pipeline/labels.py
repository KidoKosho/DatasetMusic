"""Label exporter producing tracks.jsonl, tracks.csv, genres.json, dataset_summary.json."""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List
from music_dataset.schema import Track


class LabelExporter:
    @staticmethod
    def export_labels(
        dataset: str,
        tracks: List[Track],
        output_dir: Path = Path("datasets"),
    ) -> Dict[str, Path]:
        label_dir = Path(output_dir) / dataset / "label"
        label_dir.mkdir(parents=True, exist_ok=True)
        paths: Dict[str, Path] = {}

        # 1. tracks.jsonl
        jsonl_path = label_dir / "tracks.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for t in tracks:
                f.write(json.dumps(t.to_unified_dict(), ensure_ascii=False) + "\n")
        paths["jsonl"] = jsonl_path

        # 2. tracks.csv
        csv_path = label_dir / "tracks.csv"
        if tracks:
            fieldnames = [
                "track_id", "dataset", "source_id", "title", "artist", "album",
                "year", "genre", "genre_original", "is_vietnamese_song",
                "is_vietnamese_lyrics", "language_status", "language_confidence",
                "sha256", "audio_path", "artwork_path"
            ]
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for t in tracks:
                    writer.writerow(t.model_dump())
        else:
            csv_path.write_text("track_id,dataset,source_id,title,artist,album,year,genre,genre_original,is_vietnamese_song,is_vietnamese_lyrics,language_status,language_confidence,sha256,audio_path,artwork_path\n", encoding="utf-8")
        paths["csv"] = csv_path

        # 3. genres.json
        genre_counts: Dict[str, int] = {}
        for t in tracks:
            g = t.genre or "unknown"
            genre_counts[g] = genre_counts.get(g, 0) + 1
        genres_path = label_dir / "genres.json"
        genres_path.write_text(json.dumps(genre_counts, ensure_ascii=False, indent=2), encoding="utf-8")
        paths["genres"] = genres_path

        # 4. dataset_summary.json
        summary_path = label_dir / "dataset_summary.json"
        summary_data = {
            "dataset": dataset,
            "total_tracks": len(tracks),
            "vietnamese_songs": sum(1 for t in tracks if t.is_vietnamese_song is True),
            "vietnamese_lyrics": sum(1 for t in tracks if t.is_vietnamese_lyrics is True),
            "with_audio": sum(1 for t in tracks if t.audio_path),
            "with_lyrics": sum(1 for t in tracks if t.lyrics),
            "with_artwork": sum(1 for t in tracks if t.artwork_path),
        }
        summary_path.write_text(json.dumps(summary_data, ensure_ascii=False, indent=2), encoding="utf-8")
        paths["summary"] = summary_path

        return paths
