"""Million Song Dataset adapter handling metadata, musiXmatch lyrics mapping, and asset availability."""

from pathlib import Path
from typing import Any, Dict, List, Optional
from music_dataset.constants import (
    AssetStatus,
    DatasetName,
    DownloadStatus,
    LanguageStatus,
)
from music_dataset.datasets.base import DatasetAdapter
from music_dataset.schema import Track, generate_deterministic_id


class MillionSongDatasetAdapter(DatasetAdapter):
    dataset_name = DatasetName.MILLION_SONG_DATASET.value

    SUBSET_URL = "http://static.echonest.com/millionsongsubset_full.tar.gz"
    MXM_LYRICS_URL = "http://millionsongdataset.com/sites/default/files/AdditionalFiles/mxm_dataset_train.txt.zip"

    def inspect(self) -> Dict[str, Any]:
        """Inspect structure and availability of Million Song Dataset."""
        staged_files = list(self.raw_dir.rglob("*.h5")) + list(self.raw_dir.rglob("*.txt"))
        return {
            "dataset": self.dataset_name,
            "metadata": True,
            "audio": "NOT_AVAILABLE",  # Full audio is not bundled with MSD
            "lyrics": "bag_of_words_mapping_available",  # musiXmatch dataset
            "artwork": "NOT_AVAILABLE",
            "labels": True,
            "download_method": "http_tar_gz_or_musiXmatch_zip",
            "metadata_subset_url": self.SUBSET_URL,
            "lyrics_url": self.MXM_LYRICS_URL,
            "raw_staged_files": len(staged_files),
            "notes": [
                "Million Song Dataset does not distribute full audio tracks (only 30s 7digital previews existed historically, now largely deprecated).",
                "Full audio is explicitly marked NOT_AVAILABLE.",
                "Lyrics mapping available via musiXmatch dataset (mxm_dataset_train.txt).",
                "Metadata distributed via 10,000 track HDF5 subset.",
            ],
        }

    def discover_tracks(self, limit: Optional[int] = None) -> List[Track]:
        """Discover tracks from staged HDF5 or text metadata."""
        tracks: List[Track] = []
        # Check if any .h5 files are in raw_dir
        h5_files = list(self.raw_dir.rglob("*.h5"))
        for f in h5_files:
            track_id = generate_deterministic_id(self.dataset_name, source_id=f.stem)
            track = Track(
                track_id=track_id,
                dataset=self.dataset_name,
                source_id=f.stem,
                source_url=f"http://millionsongdataset.com/track/{f.stem}",
                audio_status=DownloadStatus.UNAVAILABLE.value,
                artwork_status=AssetStatus.UNAVAILABLE.value,
                is_vietnamese_song=None,
                is_vietnamese_lyrics=None,
                language_status=LanguageStatus.UNKNOWN.value,
                provenance={"dataset": self.dataset_name, "raw_h5": str(f)},
            )
            tracks.append(track)
            if limit and len(tracks) >= limit:
                break
        return tracks

    def get_metadata(self, track: Track) -> Track:
        return track

    def find_lyrics(self, track: Track) -> Optional[str]:
        track.lyrics_status = AssetStatus.MISSING.value
        return None

    def get_audio(self, track: Track) -> Optional[Path]:
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
            "artist": track.artist,
            "is_vietnamese_song": track.is_vietnamese_song,
            "is_vietnamese_lyrics": track.is_vietnamese_lyrics,
            "language_status": track.language_status,
            "provenance": track.provenance,
        }
