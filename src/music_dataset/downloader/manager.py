"""Downloader Manager coordinating all downloaders, state persistence, and deduplication."""

from pathlib import Path
from typing import Callable, Dict, List, Optional
from music_dataset.constants import DownloadStatus
from music_dataset.downloader.base import BaseDownloader, DownloadResult
from music_dataset.downloader.checksum import compute_file_sha256
from music_dataset.downloader.github import GitHubDownloader
from music_dataset.downloader.http import HttpDownloader
from music_dataset.downloader.kaggle import KaggleDownloader
from music_dataset.downloader.rate_limiter import RateLimitManager
from music_dataset.downloader.repository import RepositoryDownloader
from music_dataset.manifest.manager import ManifestManager
from music_dataset.state.database import StateDatabase


class DownloaderManager:
    def __init__(
        self,
        state_db: Optional[StateDatabase] = None,
        manifest_mgr: Optional[ManifestManager] = None,
        rate_limiter: Optional[RateLimitManager] = None,
        chunk_size: int = 1048576,
        timeout: int = 60,
        max_retries: int = 5,
    ):
        self.state_db = state_db or StateDatabase()
        self.manifest_mgr = manifest_mgr or ManifestManager()
        self.rate_limiter = rate_limiter or RateLimitManager()
        self.http_downloader = HttpDownloader(
            chunk_size=chunk_size,
            timeout=timeout,
            max_retries=max_retries,
            rate_limiter=self.rate_limiter,
        )
        self.kaggle_downloader = KaggleDownloader()
        self.github_downloader = GitHubDownloader(self.http_downloader)
        self.repo_downloader = RepositoryDownloader(self.http_downloader, timeout=timeout)

        # Track known SHA-256 for cross-dataset deduplication while preserving provenance
        self.sha256_index: Dict[str, List[Dict[str, str]]] = {}

    def register_existing_file(self, dataset: str, track_id: str, file_path: Path) -> Optional[str]:
        """Index an existing file for deduplication."""
        path = Path(file_path)
        if not path.exists() or path.stat().st_size == 0:
            return None
        sha = compute_file_sha256(path)
        if sha not in self.sha256_index:
            self.sha256_index[sha] = []
        self.sha256_index[sha].append({"dataset": dataset, "track_id": track_id, "path": str(path)})
        return sha

    def is_duplicate_sha256(self, sha256: str) -> Optional[List[Dict[str, str]]]:
        return self.sha256_index.get(sha256)

    def download_track_asset(
        self,
        dataset: str,
        track_id: str,
        url: str,
        destination: Path,
        *,
        expected_size: Optional[int] = None,
        expected_sha256: Optional[str] = None,
        resume: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> DownloadResult:
        """Download asset, record state in SQLite and update manifest."""
        dest = Path(destination)
        self.state_db.record_download(
            track_id=track_id,
            url=url,
            destination=str(dest),
            status=DownloadStatus.DOWNLOADING.value,
        )

        downloader: BaseDownloader = self.http_downloader
        if "kaggle.com" in url or (not url.startswith("http") and "/" in url and not url.startswith(".")):
            downloader = self.kaggle_downloader
        elif "github.com" in url:
            downloader = self.github_downloader
        elif "handle/" in url or "repositori" in url:
            downloader = self.repo_downloader

        result = downloader.download(
            url,
            dest,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
            resume=resume,
            progress_callback=progress_callback,
        )

        if result.status == DownloadStatus.DOWNLOADED.value:
            if result.sha256:
                self.register_existing_file(dataset, track_id, dest)
            self.state_db.record_download(
                track_id=track_id,
                url=url,
                destination=str(dest),
                status=DownloadStatus.DOWNLOADED.value,
                attempts=result.attempts,
                bytes_downloaded=result.size,
                total_bytes=result.size,
                sha256=result.sha256,
            )
            self.manifest_mgr.update_download_status(
                dataset=dataset,
                track_id=track_id,
                status=DownloadStatus.DOWNLOADED.value,
                size=result.size,
                sha256=result.sha256,
            )
        else:
            self.state_db.record_download(
                track_id=track_id,
                url=url,
                destination=str(dest),
                status=result.status,
                attempts=result.attempts,
                error=result.error,
            )
            self.state_db.record_error(
                track_id=track_id,
                dataset=dataset,
                operation="download",
                error_type="DownloadError",
                message=result.error or "Unknown error",
                retry_count=result.attempts,
            )
            self.manifest_mgr.update_download_status(
                dataset=dataset,
                track_id=track_id,
                status=result.status,
                error=result.error,
            )

        return result
