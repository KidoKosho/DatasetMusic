"""Unified Track schema and deterministic ID generation."""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from music_dataset.constants import (
    AssetStatus,
    DownloadStatus,
    LanguageDetectionMethod,
    LanguageStatus,
    MetadataStatus,
)


def generate_deterministic_id(
    dataset: str,
    source_id: Optional[str] = None,
    source_relative_path: Optional[str] = None,
    file_sha256: Optional[str] = None,
) -> str:
    """
    Generate deterministic track_id:
    sha256(dataset + source_relative_path + file_sha256) or sha256(dataset + source_id)
    """
    if file_sha256 and source_relative_path:
        raw_key = f"{dataset}:{source_relative_path}:{file_sha256}"
    elif source_id:
        raw_key = f"{dataset}:{source_id}"
    elif source_relative_path:
        raw_key = f"{dataset}:{source_relative_path}"
    else:
        raw_key = f"{dataset}:unknown"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:24]


class Track(BaseModel):
    track_id: str
    dataset: str
    source_id: str
    source_url: str = ""
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    genre_original: Optional[str] = None
    lyrics: Optional[str] = None
    is_vietnamese_song: Optional[bool] = None
    is_vietnamese_lyrics: Optional[bool] = None
    language_status: str = LanguageStatus.UNKNOWN.value
    language_confidence: Optional[float] = None
    language_detection_method: Optional[str] = LanguageDetectionMethod.NOT_CHECKED.value
    language_evidence: Dict[str, Any] = Field(default_factory=dict)
    audio_path: Optional[str] = None
    artwork_path: Optional[str] = None
    source_filename: Optional[str] = None
    source_relative_path: Optional[str] = None
    metadata_status: str = MetadataStatus.PARTIAL.value
    lyrics_status: str = AssetStatus.MISSING.value
    audio_status: str = DownloadStatus.PENDING.value
    artwork_status: str = AssetStatus.MISSING.value
    sha256: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    enrichment: Dict[str, Any] = Field(
        default_factory=lambda: {"msd": {}, "fma": {}, "upf": {}}
    )
    vietnamese_relevance: Dict[str, Any] = Field(
        default_factory=lambda: {
            "status": "unknown",
            "confidence": 0.0,
            "evidence": [],
        }
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    model_config = {"validate_assignment": True}

    def to_unified_dict(self) -> Dict[str, Any]:
        """Convert Track to the unified nested JSON format specified in Section 21."""
        return {
            "track_id": self.track_id,
            "dataset": self.dataset,
            "source": {
                "primary": "kaggle" if self.dataset == "vietnam_music_genre" else self.dataset,
                "dataset_url": self.source_url,
                "relative_path": self.source_relative_path or "",
            },
            "metadata": {
                "title": self.title,
                "artist": self.artist,
                "album": self.album,
                "year": self.year,
                "genre": self.genre,
                "genre_original": self.genre_original,
            },
            "language": {
                "is_vietnamese_song": self.is_vietnamese_song,
                "is_vietnamese_lyrics": self.is_vietnamese_lyrics,
                "status": self.language_status,
                "confidence": self.language_confidence,
            },
            "lyrics": {
                "status": self.lyrics_status,
                "source": self.provenance.get("lyrics_source"),
                "path": f"datasets/{self.dataset}/lyric/{self.track_id}.txt" if self.lyrics else None,
            },
            "audio": {
                "path": self.audio_path or f"datasets/{self.dataset}/audio/{self.track_id}.mp3",
                "sha256": self.sha256,
                "status": self.audio_status,
            },
            "artwork": {
                "path": self.artwork_path,
                "status": self.artwork_status,
            },
            "enrichment": self.enrichment,
            "vietnamese_relevance": self.vietnamese_relevance,
        }
