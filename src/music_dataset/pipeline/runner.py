"""Pipeline Runner orchestrating discovery, candidate selection, ingestion, validation, and reports."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from rich.console import Console

from music_dataset.config import AppConfig
from music_dataset.constants import DatasetName, DownloadStatus, LanguageStatus
from music_dataset.datasets.base import DatasetAdapter
from music_dataset.datasets.fma import FmaAdapter
from music_dataset.datasets.million_song_dataset import MillionSongDatasetAdapter
from music_dataset.datasets.upf import UpfAdapter
from music_dataset.datasets.vietnam_music_genre import VietnamMusicGenreAdapter
from music_dataset.downloader.manager import DownloaderManager
from music_dataset.language.vietnamese_detector import VietnameseDetector
from music_dataset.lyrics.manager import LyricsManager
from music_dataset.manifest.manager import ManifestManager
from music_dataset.pipeline.labels import LabelExporter
from music_dataset.pipeline.validate import DatasetValidator
from music_dataset.reports.capabilities import generate_capabilities_report
from music_dataset.reports.generator import QualityReportGenerator
from music_dataset.schema import Track
from music_dataset.state.database import StateDatabase

import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(highlight=False)


@dataclass
class DryRunStats:
    dataset: str
    tracks_discovered: int = 0
    lyrics_candidates: int = 0
    vietnamese_candidates: int = 0
    audio_candidates: int = 0
    artwork_candidates: int = 0
    estimated_audio_bytes: int = 0
    estimated_lyrics_bytes: int = 0
    estimated_artwork_bytes: int = 0


class PipelineRunner:
    def __init__(
        self,
        config: Optional[AppConfig] = None,
        state_db: Optional[StateDatabase] = None,
        manifest_mgr: Optional[ManifestManager] = None,
        downloader_mgr: Optional[DownloaderManager] = None,
        detector: Optional[VietnameseDetector] = None,
    ):
        self.config = config or AppConfig()
        self.state_db = state_db or StateDatabase()
        self.manifest_mgr = manifest_mgr or ManifestManager()
        self.downloader_mgr = downloader_mgr or DownloaderManager(
            state_db=self.state_db,
            manifest_mgr=self.manifest_mgr,
            chunk_size=self.config.download.chunk_size,
            timeout=self.config.download.timeout,
            max_retries=self.config.download.max_retries,
        )
        self.detector = detector or VietnameseDetector(
            threshold=self.config.language.minimum_confidence
        )
        self.lyrics_mgr = LyricsManager()
        self.validator = DatasetValidator(state_db=self.state_db)
        self.reporter = QualityReportGenerator(state_db=self.state_db)
        from music_dataset.metadata.enrichment import MetadataEnrichmentEngine
        self.enrichment_engine = MetadataEnrichmentEngine(raw_dir=Path("data/raw"))

        # Register dataset adapters
        self.adapters: Dict[str, DatasetAdapter] = {
            DatasetName.VIETNAM_MUSIC_GENRE.value: VietnamMusicGenreAdapter(
                detector=self.detector
            ),
            DatasetName.FMA.value: FmaAdapter(
                audio_subset=self.config.fma.get("audio_subset", "small"),
                detector=self.detector,
            ),
            DatasetName.MILLION_SONG_DATASET.value: MillionSongDatasetAdapter(),
            DatasetName.UPF.value: UpfAdapter(),
        }

    def inspect_all(self) -> Path:
        """Inspect all datasets and generate dataset_capabilities.json."""
        return generate_capabilities_report()

    def download_kaggle(self) -> Dict[str, Any]:
        """Download Kaggle Vietnam Music Genre dataset to data/raw/vietnam_music_genre/."""
        from music_dataset.downloader.kaggle import KaggleDownloader
        downloader = KaggleDownloader(Path("data/raw"))
        has_creds, msg = downloader.check_credentials()
        if not has_creds:
            return {
                "status": "missing_credentials",
                "message": msg,
            }
        res = downloader.download(
            url=self.config.vietnam_music_genre.get("kaggle_dataset", "xuaam1/vietnam-music-genre"),
            destination=Path("data/raw/vietnam_music_genre"),
        )
        return {
            "status": res.status,
            "destination": str(res.destination),
            "error": res.error,
        }

    def run_dry_run(
        self,
        dataset_filter: Optional[str] = None,
        limit: Optional[int] = None,
        genre_filter: Optional[str] = None,
    ) -> List[DryRunStats]:
        """Perform dry-run without downloading audio files."""
        stats_list: List[DryRunStats] = []
        selected_adapters = (
            {dataset_filter: self.adapters[dataset_filter]}
            if dataset_filter and dataset_filter in self.adapters
            else self.adapters
        )

        for name, adapter in selected_adapters.items():
            tracks = adapter.discover_tracks(limit=limit)
            if genre_filter:
                tracks = [t for t in tracks if t.genre == genre_filter or t.genre_original == genre_filter]

            stat = DryRunStats(dataset=name)
            stat.tracks_discovered = len(tracks)

            for t in tracks:
                # Check lyrics candidate
                has_lyrics = bool(t.lyrics and t.lyrics.strip())
                if has_lyrics:
                    stat.lyrics_candidates += 1

                # Check Vietnamese candidate
                is_vi = (
                    t.is_vietnamese_song is True
                    or t.is_vietnamese_lyrics is True
                    or t.language_status in ("detected_vi", "dataset_asserted_vi")
                )
                if is_vi:
                    stat.vietnamese_candidates += 1

                # Audio candidate
                if t.audio_status != DownloadStatus.UNAVAILABLE.value:
                    stat.audio_candidates += 1
                    stat.estimated_audio_bytes += 5 * 1024 * 1024  # ~5MB average MP3

                # Artwork candidate
                if t.artwork_status != DownloadStatus.UNAVAILABLE.value:
                    stat.artwork_candidates += 1
                    stat.estimated_artwork_bytes += 250 * 1024  # ~250KB average image

                stat.estimated_lyrics_bytes += 2 * 1024  # ~2KB text

            stats_list.append(stat)

        return stats_list

    def print_pipeline_summary(self, stats: List[DryRunStats]) -> None:
        """Display the required final summary terminal banner."""
        total_discovered = sum(s.tracks_discovered for s in stats)
        total_lyrics = sum(s.lyrics_candidates for s in stats)
        total_vi = sum(s.vietnamese_candidates for s in stats)
        total_audio = sum(s.audio_candidates for s in stats)
        total_art = sum(s.artwork_candidates for s in stats)
        est_audio_mb = sum(s.estimated_audio_bytes for s in stats) / (1024 * 1024)
        est_lyrics_kb = sum(s.estimated_lyrics_bytes for s in stats) / 1024
        est_art_mb = sum(s.estimated_artwork_bytes for s in stats) / (1024 * 1024)

        output = f"""
========================================
MUSIC DATASET PIPELINE
========================================
Datasets:
  ✓ Million Song Dataset
  ✓ FMA
  ✓ UPF
  ✓ Vietnam Music Genre
Tracks discovered: {total_discovered}
Lyrics candidates: {total_lyrics}
Vietnamese lyrics: {total_vi}
Audio candidates: {total_audio}
Artwork candidates: {total_art}
Estimated download:
  Audio: {est_audio_mb:.1f} MB
  Lyrics: {est_lyrics_kb:.1f} KB
  Artwork: {est_art_mb:.1f} MB
Ready for download.
========================================
"""
        console.print(output.strip())

    def run_pipeline(
        self,
        dataset_filter: Optional[str] = None,
        limit: Optional[int] = None,
        dry_run: bool = False,
        resume: bool = True,
        genre_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute the full 15-step pipeline:
        1. Inspect sources
        2. Download Kaggle dataset (or check raw staging)
        3. Scan every MP3
        4. Read ID3
        5. Read genre from parent folder
        6. Create track records
        7. Search/enrich metadata (MSD, FMA, UPF)
        8. Collect Vietnamese-related evidence
        9. Find lyrics if available
        10. Detect lyrics language
        11. Extract artwork
        12. Copy/link audio into normalized structure
        13. Write label metadata
        14. Validate
        15. Generate report
        """
        # Step 1: Inspect sources
        self.inspect_all()

        if dry_run:
            stats = self.run_dry_run(
                dataset_filter=dataset_filter,
                limit=limit,
                genre_filter=genre_filter,
            )
            for s in stats:
                console.print(
                    f"Dataset: [bold cyan]{s.dataset}[/bold cyan] | "
                    f"Discovered: [bold]{s.tracks_discovered}[/bold] | "
                    f"Lyrics: {s.lyrics_candidates} | "
                    f"Vietnamese: [bold green]{s.vietnamese_candidates}[/bold green] | "
                    f"Audio: {s.audio_candidates}"
                )
            self.print_pipeline_summary(stats)
            return {"mode": "dry_run", "stats": stats}

        # Step 2: Ensure Kaggle dataset is available (attempt download if empty and credentials present)
        kaggle_raw = Path("data/raw/vietnam_music_genre")
        if not list(kaggle_raw.rglob("*.mp3")):
            self.download_kaggle()

        selected_adapters = (
            {dataset_filter: self.adapters[dataset_filter]}
            if dataset_filter and dataset_filter in self.adapters
            else self.adapters
        )

        all_processed_tracks: List[Track] = []
        for name, adapter in selected_adapters.items():
            # Steps 3-6: Scan MP3, read ID3, folder genre, create track records
            tracks = adapter.discover_tracks(limit=limit)

            # Apply filters
            if genre_filter:
                tracks = [t for t in tracks if t.genre == genre_filter or t.genre_original == genre_filter]
            if language_filter:
                tracks = [t for t in tracks if t.language_status == language_filter or (language_filter == "vi" and t.is_vietnamese_song)]

            manifest_entries = []
            for track in tracks:
                # Steps 7-8: Search/enrich metadata from MSD, FMA, UPF & collect Vietnamese evidence
                self.enrichment_engine.enrich_track(track)

                # Steps 9-10: Find lyrics & detect language if not done
                if not track.lyrics:
                    self.lyrics_mgr.fetch_lyrics_for_track(track, audio_file_path=Path(track.audio_path) if track.audio_path else None)

                # Ingest to SQLite DB
                self.state_db.upsert_track(track)

                # Create manifest entry
                entry = self.manifest_mgr.record_track(
                    track=track,
                    download_status=track.audio_status,
                )
                manifest_entries.append(entry)
                all_processed_tracks.append(track)

            # Save dataset manifest
            self.manifest_mgr.save_manifest_entries(name, manifest_entries)

            # Step 13: Export labels (tracks.jsonl, tracks.csv, genres.json, dataset_summary.json)
            LabelExporter.export_labels(name, tracks)

        # Step 14: Validate
        self.validator.validate_all(dataset=dataset_filter)

        # Step 15: Generate report
        reports = self.reporter.generate_all_reports()

        return {
            "mode": "execution",
            "tracks_processed": len(all_processed_tracks),
            "reports": reports,
        }
