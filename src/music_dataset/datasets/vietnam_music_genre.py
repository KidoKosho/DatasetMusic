"""Vietnam Music Genre dataset adapter with specialized genre-folder semantics and metadata precedence."""

import shutil
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
from music_dataset.downloader.kaggle import KaggleDownloader
from music_dataset.language.vietnamese_detector import VietnameseDetector
from music_dataset.metadata.id3_parser import ID3Parser
from music_dataset.metadata.normalizer import normalize_genre
from music_dataset.metadata.precedence import MetadataPrecedenceResolver
from music_dataset.schema import Track, generate_deterministic_id


class VietnamMusicGenreAdapter(DatasetAdapter):
    dataset_name = DatasetName.VIETNAM_MUSIC_GENRE.value

    def __init__(
        self,
        raw_dir: Path = Path("data/raw"),
        output_dir: Path = Path("datasets"),
        kaggle_slug: str = "xuaam1/vietnam-music-genre",
        detector: Optional[VietnameseDetector] = None,
    ):
        super().__init__(raw_dir, output_dir)
        self.kaggle_slug = kaggle_slug
        self.detector = detector or VietnameseDetector()
        self.kaggle_downloader = KaggleDownloader(self.raw_dir.parent)

    def inspect(self) -> Dict[str, Any]:
        """Inspect structure and availability of Vietnam Music Genre dataset."""
        has_creds, cred_msg = self.kaggle_downloader.check_credentials()
        raw_files = list(self.raw_dir.rglob("*.mp3"))

        folders = [
            f.name for f in self.raw_dir.iterdir()
            if f.is_dir() and not f.name.startswith(".")
        ]

        return {
            "dataset": self.dataset_name,
            "metadata": True,
            "audio": True,
            "lyrics": "partial_embedded_or_companion",
            "artwork": True,
            "labels": True,
            "download_method": "kaggle_api_or_manual_raw_staging",
            "kaggle_credentials_available": has_creds,
            "raw_staged_audio_count": len(raw_files),
            "detected_genre_folders": folders,
            "notes": [
                "Dataset asserts all tracks are Vietnamese songs (is_vietnamese_song=True).",
                "Folder names indicate genre_original.",
                "Files may lack metadata, title, artist, artwork or lyrics. Audio tracks are 100% preserved.",
                cred_msg,
            ],
        }

    def discover_tracks(self, limit: Optional[int] = None) -> List[Track]:
        """
        Enumerate every MP3 file in raw_dir:
        - folder = genre_original
        - creates Track for EVERY MP3 without dropping
        """
        tracks: List[Track] = []
        if not self.raw_dir.exists():
            return tracks

        # Find all MP3 files recursively
        mp3_files = sorted(list(self.raw_dir.rglob("*.mp3")))

        for mp3_path in mp3_files:
            rel_path = mp3_path.relative_to(self.raw_dir)
            # Folder name indicates genre
            folder_name = mp3_path.parent.name
            if mp3_path.parent == self.raw_dir:
                folder_name = "vietnamese"

            file_sha = None
            try:
                file_sha = compute_file_sha256(mp3_path)
            except Exception:
                pass

            track_id = generate_deterministic_id(
                dataset=self.dataset_name,
                source_id=mp3_path.stem,
                source_relative_path=str(rel_path).replace("\\", "/"),
                file_sha256=file_sha,
            )

            # Build initial track with dataset assertion semantics
            track = Track(
                track_id=track_id,
                dataset=self.dataset_name,
                source_id=mp3_path.stem,
                source_url=f"kaggle://datasets/{self.kaggle_slug}/{rel_path}",
                genre_original=folder_name,
                genre=normalize_genre(folder_name),
                is_vietnamese_song=True,  # Asserted by dataset
                is_vietnamese_lyrics=None,  # Not checked yet until lyrics found
                language_status=LanguageStatus.DATASET_ASSERTED_VI.value,
                language_detection_method=LanguageDetectionMethod.DATASET_ASSERTION.value,
                source_filename=mp3_path.name,
                source_relative_path=str(rel_path).replace("\\", "/"),
                audio_path=str(mp3_path),
                audio_status=DownloadStatus.DOWNLOADED.value,
                sha256=file_sha,
                provenance={
                    "dataset": self.dataset_name,
                    "source_id": mp3_path.stem,
                    "folder_genre": folder_name,
                    "raw_path": str(mp3_path),
                },
            )

            # Enrich with ID3 metadata
            track = self.get_metadata(track)

            # Discover and detect lyrics if any
            self.find_lyrics(track)

            # Extract artwork
            self.get_artwork(track)

            # Organize normalized audio into datasets/vietnam_music_genre/audio/{track_id}.mp3
            self.get_audio(track)

            tracks.append(track)
            if limit and len(tracks) >= limit:
                break

        return tracks

    def get_metadata(self, track: Track) -> Track:
        """Read ID3 tags and apply metadata precedence."""
        if not track.audio_path:
            return track

        audio_p = Path(track.audio_path)
        id3_meta = ID3Parser.parse_file(audio_p)

        structured = {
            "genre_original": track.genre_original,
            "genre": track.genre,
        }

        resolved, prov = MetadataPrecedenceResolver.resolve(
            structured=structured,
            id3=id3_meta,
            filename=track.source_filename,
        )

        track.title = resolved.get("title")
        track.artist = resolved.get("artist")
        track.album = resolved.get("album")
        track.year = resolved.get("year")
        track.genre = resolved.get("genre") or track.genre
        track.genre_original = resolved.get("genre_original") or track.genre_original

        if id3_meta.lyrics:
            track.lyrics = id3_meta.lyrics
            track.lyrics_status = AssetStatus.FOUND.value

        # Update metadata completeness status
        if track.title and track.artist:
            track.metadata_status = MetadataStatus.COMPLETE.value
        elif track.title or track.artist or track.genre:
            track.metadata_status = MetadataStatus.PARTIAL.value
        else:
            track.metadata_status = MetadataStatus.EMPTY.value

        track.provenance.update(prov)
        return track

    def find_lyrics(self, track: Track) -> Optional[str]:
        """Detect lyrics and run NLP detection if lyrics exist."""
        # Check companion file if not in ID3
        if not track.lyrics and track.audio_path:
            audio_p = Path(track.audio_path)
            for ext in (".txt", ".lrc"):
                comp = audio_p.with_suffix(ext)
                if comp.exists() and comp.is_file():
                    try:
                        content = comp.read_text(encoding="utf-8", errors="replace").strip()
                        if content:
                            track.lyrics = content
                            track.lyrics_status = AssetStatus.FOUND.value
                            break
                    except Exception:
                        pass

        if track.lyrics and track.lyrics.strip():
            # Run Vietnamese NLP detector
            result = self.detector.detect(track.lyrics)
            track.language_confidence = result.confidence
            track.language_evidence = result.evidence
            track.language_detection_method = result.method

            if result.status == LanguageStatus.DETECTED_VI.value:
                track.is_vietnamese_lyrics = True
                track.language_status = LanguageStatus.DETECTED_VI.value
            elif result.status == LanguageStatus.DETECTED_NON_VI.value:
                track.is_vietnamese_lyrics = False
                track.language_status = LanguageStatus.DETECTED_NON_VI.value
            else:
                track.is_vietnamese_lyrics = None
                track.language_status = LanguageStatus.UNKNOWN.value

            # Save normalized lyric file
            lyric_out = self.output_dir / "lyric" / f"{track.track_id}.txt"
            lyric_out.write_text(track.lyrics, encoding="utf-8")
        else:
            # If lyrics missing: preserve track, DO NOT pretend NLP checked lyrics!
            track.lyrics_status = AssetStatus.MISSING.value
            track.is_vietnamese_lyrics = None
            track.language_status = LanguageStatus.DATASET_ASSERTED_VI.value
            track.language_detection_method = LanguageDetectionMethod.DATASET_ASSERTION.value

        return track.lyrics

    def get_audio(self, track: Track) -> Optional[Path]:
        """Copy/link raw audio to normalized datasets/{dataset}/audio/{track_id}.mp3."""
        if not track.audio_path:
            return None
        src_path = Path(track.audio_path)
        if not src_path.exists():
            return None

        target = self.output_dir / "audio" / f"{track.track_id}.mp3"
        if not target.exists():
            shutil.copy2(src_path, target)
        return target

    def get_artwork(self, track: Track) -> Optional[Path]:
        """Extract embedded APIC to datasets/{dataset}/avt/{track_id}.jpg."""
        if not track.audio_path:
            return None
        audio_p = Path(track.audio_path)
        id3_meta = ID3Parser.parse_file(audio_p)
        if id3_meta.artwork_bytes:
            ext = ".png" if id3_meta.artwork_mime and "png" in id3_meta.artwork_mime.lower() else ".jpg"
            target = self.output_dir / "avt" / f"{track.track_id}{ext}"
            target.write_bytes(id3_meta.artwork_bytes)
            track.artwork_path = str(target)
            track.artwork_status = AssetStatus.EXTRACTED.value
            return target
        else:
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
            "genre_original": track.genre_original,
            "is_vietnamese_song": track.is_vietnamese_song,
            "is_vietnamese_lyrics": track.is_vietnamese_lyrics,
            "language_status": track.language_status,
            "language_confidence": track.language_confidence,
            "language_detection_method": track.language_detection_method,
            "sha256": track.sha256,
            "provenance": track.provenance,
        }
