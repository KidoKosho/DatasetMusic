"""UPF repository adapter inspecting handle endpoint and handling institutional repository access."""

from pathlib import Path
from typing import Any, Dict, List, Optional
from music_dataset.constants import (
    AssetStatus,
    DatasetName,
    DownloadStatus,
    LanguageStatus,
)
from music_dataset.datasets.base import DatasetAdapter
from music_dataset.downloader.repository import RepositoryDownloader
from music_dataset.schema import Track, generate_deterministic_id


class UpfAdapter(DatasetAdapter):
    dataset_name = DatasetName.UPF.value
    HANDLE_URL = "https://repositori.upf.edu/handle/10230/33285"

    def __init__(
        self,
        raw_dir: Path = Path("data/raw"),
        output_dir: Path = Path("datasets"),
        repo_downloader: Optional[RepositoryDownloader] = None,
    ):
        super().__init__(raw_dir, output_dir)
        self.repo_downloader = repo_downloader or RepositoryDownloader(timeout=10)

    def inspect(self) -> Dict[str, Any]:
        """Inspect UPF repository handle connectivity and available assets."""
        conn_info = self.repo_downloader.inspect_repository(self.HANDLE_URL)
        staged_files = list(self.raw_dir.rglob("*.*"))

        # Determine asset availability based on inspection and local staging
        audio_avail = "NOT_AVAILABLE" if not conn_info.get("accessible") else True
        meta_avail = "NOT_AVAILABLE" if not conn_info.get("accessible") else True

        notes = [
            f"Repository URL: {self.HANDLE_URL}",
            f"Endpoint status: {conn_info.get('status')}",
        ]
        if not conn_info.get("accessible"):
            notes.append(
                f"Direct download is NOT_AVAILABLE ({conn_info.get('note') or conn_info.get('error')})."
            )
            notes.append(
                "Local staging mode is supported: place dataset files into data/raw/upf/ for ingestion."
            )

        return {
            "dataset": self.dataset_name,
            "metadata": meta_avail,
            "audio": audio_avail,
            "lyrics": "NOT_AVAILABLE",
            "artwork": "NOT_AVAILABLE",
            "labels": True if staged_files else "NOT_AVAILABLE",
            "download_method": "upf_dspace_handle_or_raw_staging",
            "handle_url": self.HANDLE_URL,
            "connection_status": conn_info,
            "raw_staged_files": len(staged_files),
            "notes": notes,
        }

    def discover_tracks(self, limit: Optional[int] = None) -> List[Track]:
        """Discover tracks from local raw staging directory."""
        tracks: List[Track] = []
        audio_files = sorted(list(self.raw_dir.rglob("*.mp3")) + list(self.raw_dir.rglob("*.wav")))
        for f in audio_files:
            track_id = generate_deterministic_id(self.dataset_name, source_id=f.stem)
            track = Track(
                track_id=track_id,
                dataset=self.dataset_name,
                source_id=f.stem,
                source_url=f"{self.HANDLE_URL}/{f.name}",
                source_filename=f.name,
                audio_path=str(f),
                audio_status=DownloadStatus.DOWNLOADED.value,
                is_vietnamese_song=None,
                is_vietnamese_lyrics=None,
                language_status=LanguageStatus.UNKNOWN.value,
                provenance={"dataset": self.dataset_name, "raw_path": str(f)},
            )
            tracks.append(track)
            if limit and len(tracks) >= limit:
                break
        return tracks

    def get_metadata(self, track: Track) -> Track:
        return track

    def find_lyrics(self, track: Track) -> Optional[str]:
        track.lyrics_status = AssetStatus.UNAVAILABLE.value
        return None

    def get_audio(self, track: Track) -> Optional[Path]:
        if track.audio_path and Path(track.audio_path).exists():
            return Path(track.audio_path)
        track.audio_status = DownloadStatus.UNAVAILABLE.value
        return None

    def get_artwork(self, track: Track) -> Optional[Path]:
        track.artwork_status = AssetStatus.UNAVAILABLE.value
        return None

    def get_labels(self, track: Track) -> Dict[str, Any]:
        return {
            "track_id": track.track_id,
            "dataset": self.dataset_name,
            "title": track.title,
            "is_vietnamese_song": track.is_vietnamese_song,
            "is_vietnamese_lyrics": track.is_vietnamese_lyrics,
            "language_status": track.language_status,
            "provenance": track.provenance,
        }
