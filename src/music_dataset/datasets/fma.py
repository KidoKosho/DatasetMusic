"""Free Music Archive (FMA) dataset adapter with subset configuration and candidate selection."""

import csv
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from music_dataset.constants import (
    AssetStatus,
    DatasetName,
    DownloadStatus,
    LanguageDetectionMethod,
    LanguageStatus,
    MetadataStatus,
)
from music_dataset.datasets.base import DatasetAdapter
from music_dataset.downloader.checksum import compute_file_sha256
from music_dataset.language.vietnamese_detector import VietnameseDetector
from music_dataset.metadata.normalizer import normalize_genre
from music_dataset.schema import Track, generate_deterministic_id


class FmaAdapter(DatasetAdapter):
    dataset_name = DatasetName.FMA.value

    METADATA_URL = "https://os.unil.cloud.switch.ch/fma/fma_metadata.zip"
    AUDIO_SUBSET_URLS = {
        "small": "https://os.unil.cloud.switch.ch/fma/fma_small.zip",
        "medium": "https://os.unil.cloud.switch.ch/fma/fma_medium.zip",
        "large": "https://os.unil.cloud.switch.ch/fma/fma_large.zip",
        "full": "https://os.unil.cloud.switch.ch/fma/fma_full.zip",
    }

    def __init__(
        self,
        raw_dir: Path = Path("data/raw"),
        output_dir: Path = Path("datasets"),
        audio_subset: str = "small",
        detector: Optional[VietnameseDetector] = None,
    ):
        super().__init__(raw_dir, output_dir)
        self.audio_subset = audio_subset
        self.detector = detector or VietnameseDetector()

    def inspect(self) -> Dict[str, Any]:
        """Inspect structure and availability of FMA dataset."""
        tracks_csv = self.raw_dir / "fma_metadata" / "tracks.csv"
        if not tracks_csv.exists():
            tracks_csv = self.raw_dir / "tracks.csv"

        raw_audio_count = len(list(self.raw_dir.rglob("*.mp3")))

        return {
            "dataset": self.dataset_name,
            "metadata": True,
            "audio": True,
            "lyrics": "not_bundled_internally",
            "artwork": "not_bundled_internally",
            "labels": True,
            "download_method": "http_archive_zip",
            "metadata_url": self.METADATA_URL,
            "configured_audio_subset": self.audio_subset,
            "audio_subset_url": self.AUDIO_SUBSET_URLS.get(self.audio_subset, ""),
            "metadata_csv_present": tracks_csv.exists(),
            "raw_audio_count": raw_audio_count,
            "notes": [
                "Metadata distributed as fma_metadata.zip (tracks.csv, genres.csv).",
                "Audio available in small (8k tracks, 7.2GB), medium (25k), large (106k).",
                "Phase 1 indexes metadata and selects Vietnamese candidates prior to bulk audio download.",
            ],
        }

    def discover_tracks(self, limit: Optional[int] = None) -> List[Track]:
        """
        Inspect tracks.csv and build track objects.
        If tracks.csv is not yet present, inspects any staged files in raw_dir.
        """
        tracks: List[Track] = []
        tracks_csv = self.raw_dir / "fma_metadata" / "tracks.csv"
        if not tracks_csv.exists():
            tracks_csv = self.raw_dir / "tracks.csv"

        if tracks_csv.exists():
            with open(tracks_csv, mode="r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                # FMA tracks.csv has multi-level headers (usually 3 lines)
                header_rows = [next(reader, []) for _ in range(3)]
                for row in reader:
                    if not row or len(row) < 2:
                        continue
                    fma_id = row[0].strip()
                    # Approximate column indexes in tracks.csv
                    # Title is around col 52, artist is col 51 in standard FMA format
                    title = row[52].strip() if len(row) > 52 else None
                    artist = row[51].strip() if len(row) > 51 else None
                    genre_raw = row[40].strip() if len(row) > 40 else None

                    track_id = generate_deterministic_id(self.dataset_name, source_id=fma_id)
                    track = Track(
                        track_id=track_id,
                        dataset=self.dataset_name,
                        source_id=fma_id,
                        source_url=f"https://freemusicarchive.org/track/{fma_id}",
                        title=title,
                        artist=artist,
                        genre_original=genre_raw,
                        genre=normalize_genre(genre_raw),
                        is_vietnamese_song=None,  # Not asserted by FMA
                        is_vietnamese_lyrics=None,
                        language_status=LanguageStatus.UNKNOWN.value,
                        provenance={
                            "dataset": self.dataset_name,
                            "fma_id": fma_id,
                            "source_metadata": "fma_metadata/tracks.csv",
                        },
                    )
                    tracks.append(track)
                    if limit and len(tracks) >= limit:
                        break
        else:
            # Check if any local audio files are staged in raw_dir
            audio_files = sorted(list(self.raw_dir.rglob("*.mp3")))
            for f in audio_files:
                fma_id = f.stem
                track_id = generate_deterministic_id(self.dataset_name, source_id=fma_id)
                track = Track(
                    track_id=track_id,
                    dataset=self.dataset_name,
                    source_id=fma_id,
                    source_url=f"https://freemusicarchive.org/track/{fma_id}",
                    source_filename=f.name,
                    audio_path=str(f),
                    audio_status=DownloadStatus.DOWNLOADED.value,
                    is_vietnamese_song=None,
                    is_vietnamese_lyrics=None,
                    language_status=LanguageStatus.UNKNOWN.value,
                    provenance={"dataset": self.dataset_name, "file": str(f)},
                )
                tracks.append(track)
                if limit and len(tracks) >= limit:
                    break

        return tracks

    def get_metadata(self, track: Track) -> Track:
        return track

    def find_lyrics(self, track: Track) -> Optional[str]:
        # FMA does not bundle lyrics; external provider handles search
        track.lyrics_status = AssetStatus.MISSING.value
        return None

    def get_audio(self, track: Track) -> Optional[Path]:
        if track.audio_path and Path(track.audio_path).exists():
            return Path(track.audio_path)
        return None

    def get_artwork(self, track: Track) -> Optional[Path]:
        track.artwork_status = AssetStatus.MISSING.value
        return None

    def get_labels(self, track: Track) -> Dict[str, Any]:
        return {
            "track_id": track.track_id,
            "dataset": self.dataset_name,
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "year": track.year,
            "genre": track.genre,
            "is_vietnamese_song": track.is_vietnamese_song,
            "is_vietnamese_lyrics": track.is_vietnamese_lyrics,
            "language_status": track.language_status,
            "provenance": track.provenance,
        }
