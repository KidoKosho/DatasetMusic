"""Data validation engine verifying Audio, Lyrics, Artwork, and Metadata integrity."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image
from mutagen.mp3 import MP3

from music_dataset.constants import LanguageStatus
from music_dataset.downloader.checksum import compute_file_sha256
from music_dataset.schema import Track
from music_dataset.state.database import StateDatabase


@dataclass
class ValidationIssue:
    track_id: str
    dataset: str
    category: str  # audio, lyrics, artwork, metadata
    severity: str  # ERROR, WARNING
    message: str


@dataclass
class ValidationSummary:
    total_tracks_checked: int = 0
    valid_tracks: int = 0
    issues_count: int = 0
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return not any(i.severity == "ERROR" for i in self.issues)


class DatasetValidator:
    def __init__(self, state_db: Optional[StateDatabase] = None):
        self.state_db = state_db or StateDatabase()

    def validate_all(self, dataset: Optional[str] = None) -> ValidationSummary:
        tracks = self.state_db.list_tracks(dataset=dataset)
        summary = ValidationSummary(total_tracks_checked=len(tracks))
        seen_track_ids = set()

        for track in tracks:
            track_issues: List[ValidationIssue] = []

            # 1. Metadata Validation
            if track.track_id in seen_track_ids:
                track_issues.append(ValidationIssue(
                    track_id=track.track_id,
                    dataset=track.dataset,
                    category="metadata",
                    severity="ERROR",
                    message=f"Duplicate track_id detected: {track.track_id}",
                ))
            seen_track_ids.add(track.track_id)

            if not track.provenance:
                track_issues.append(ValidationIssue(
                    track_id=track.track_id,
                    dataset=track.dataset,
                    category="metadata",
                    severity="WARNING",
                    message="Track provenance is empty.",
                ))

            # 2. Audio Validation (if audio claimed to be present)
            if track.audio_path:
                audio_p = Path(track.audio_path)
                if not audio_p.exists():
                    track_issues.append(ValidationIssue(
                        track_id=track.track_id,
                        dataset=track.dataset,
                        category="audio",
                        severity="ERROR",
                        message=f"Audio file does not exist at {audio_p}",
                    ))
                elif audio_p.stat().st_size == 0:
                    track_issues.append(ValidationIssue(
                        track_id=track.track_id,
                        dataset=track.dataset,
                        category="audio",
                        severity="ERROR",
                        message=f"Audio file is empty (0 bytes): {audio_p}",
                    ))
                else:
                    # Test parsing with Mutagen MP3
                    try:
                        MP3(audio_p)
                    except Exception as e:
                        track_issues.append(ValidationIssue(
                            track_id=track.track_id,
                            dataset=track.dataset,
                            category="audio",
                            severity="WARNING",
                            message=f"Audio file MP3 header parse warning: {e}",
                        ))
                    # Checksum match
                    if track.sha256:
                        actual_sha = compute_file_sha256(audio_p)
                        if actual_sha.lower() != track.sha256.lower():
                            track_issues.append(ValidationIssue(
                                track_id=track.track_id,
                                dataset=track.dataset,
                                category="audio",
                                severity="ERROR",
                                message="Checksum mismatch between DB and audio file.",
                            ))

            # 3. Lyrics Validation
            if track.lyrics:
                if not track.lyrics.strip():
                    track_issues.append(ValidationIssue(
                        track_id=track.track_id,
                        dataset=track.dataset,
                        category="lyrics",
                        severity="WARNING",
                        message="Lyrics string is whitespace only.",
                    ))
                # Validate language status
                valid_statuses = {s.value for s in LanguageStatus}
                if track.language_status not in valid_statuses:
                    track_issues.append(ValidationIssue(
                        track_id=track.track_id,
                        dataset=track.dataset,
                        category="lyrics",
                        severity="ERROR",
                        message=f"Invalid language status: {track.language_status}",
                    ))

            # 4. Artwork Validation
            if track.artwork_path:
                art_p = Path(track.artwork_path)
                if not art_p.exists():
                    track_issues.append(ValidationIssue(
                        track_id=track.track_id,
                        dataset=track.dataset,
                        category="artwork",
                        severity="WARNING",
                        message=f"Artwork path not found: {art_p}",
                    ))
                else:
                    try:
                        with Image.open(art_p) as img:
                            img.verify()
                    except Exception as e:
                        track_issues.append(ValidationIssue(
                            track_id=track.track_id,
                            dataset=track.dataset,
                            category="artwork",
                            severity="ERROR",
                            message=f"Artwork image corrupted: {e}",
                        ))

            if not track_issues:
                summary.valid_tracks += 1
            else:
                summary.issues.extend(track_issues)

        summary.issues_count = len(summary.issues)
        return summary
