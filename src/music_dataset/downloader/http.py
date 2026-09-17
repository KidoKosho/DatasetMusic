"""HTTP Downloader with streaming, atomic rename, checksum verification, and resume support."""

import hashlib
import os
import shutil
from pathlib import Path
from typing import Callable, Optional
import requests

from music_dataset.constants import DownloadStatus
from music_dataset.downloader.base import BaseDownloader, DownloadResult
from music_dataset.downloader.checksum import compute_file_sha256, verify_file_checksum
from music_dataset.downloader.rate_limiter import RateLimitManager
from music_dataset.downloader.resume import ResumeManager
from music_dataset.downloader.retry import retry_with_backoff


class HttpDownloader(BaseDownloader):
    def __init__(
        self,
        chunk_size: int = 1048576,  # 1MB
        timeout: int = 60,
        max_retries: int = 5,
        rate_limiter: Optional[RateLimitManager] = None,
    ):
        self.chunk_size = chunk_size
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limiter = rate_limiter or RateLimitManager()

    def download(
        self,
        url: str,
        destination: Path,
        *,
        expected_size: Optional[int] = None,
        expected_sha256: Optional[str] = None,
        resume: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> DownloadResult:
        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)

        # 1. Check if destination already exists and is valid
        if dest.exists() and dest.stat().st_size > 0:
            if expected_sha256:
                if verify_file_checksum(dest, expected_sha256):
                    actual_sha = expected_sha256
                    return DownloadResult(
                        destination=dest,
                        size=dest.stat().st_size,
                        sha256=actual_sha,
                        status=DownloadStatus.DOWNLOADED.value,
                        attempts=0,
                    )
            elif expected_size is not None and dest.stat().st_size == expected_size:
                return DownloadResult(
                    destination=dest,
                    size=dest.stat().st_size,
                    sha256=compute_file_sha256(dest),
                    status=DownloadStatus.DOWNLOADED.value,
                    attempts=0,
                )
            elif expected_size is None and not expected_sha256:
                return DownloadResult(
                    destination=dest,
                    size=dest.stat().st_size,
                    sha256=compute_file_sha256(dest),
                    status=DownloadStatus.DOWNLOADED.value,
                    attempts=0,
                )

        limiter = self.rate_limiter.get_limiter_for_url(url)
        attempts = 0

        def _do_download() -> DownloadResult:
            nonlocal attempts
            attempts += 1
            limiter.acquire()
            try:
                part_path, existing_size, headers = ResumeManager.prepare_resume(
                    dest, resume_enabled=resume
                )

                response = requests.get(
                    url,
                    headers=headers,
                    stream=True,
                    timeout=self.timeout,
                )

                if response.status_code not in (200, 206):
                    response.raise_for_status()

                mode, start_bytes = ResumeManager.handle_server_range_response(
                    part_path, response.status_code, existing_size
                )

                total_content_length = response.headers.get("Content-Length")
                total_expected = (
                    int(total_content_length) + start_bytes
                    if total_content_length
                    else expected_size
                )

                bytes_downloaded = start_bytes
                with open(part_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        if chunk:
                            f.write(chunk)
                            bytes_downloaded += len(chunk)
                            if progress_callback and total_expected:
                                progress_callback(bytes_downloaded, total_expected)

                # Validate size if specified
                if expected_size and part_path.stat().st_size != expected_size:
                    raise ValueError(
                        f"Size mismatch: expected {expected_size}, got {part_path.stat().st_size}"
                    )

                # Validate SHA-256 if specified
                actual_sha = compute_file_sha256(part_path)
                if expected_sha256 and actual_sha.lower() != expected_sha256.lower().strip():
                    raise ValueError(
                        f"Checksum mismatch: expected {expected_sha256}, got {actual_sha}"
                    )

                # Atomic rename
                if dest.exists():
                    dest.unlink()
                shutil.move(str(part_path), str(dest))

                return DownloadResult(
                    destination=dest,
                    size=dest.stat().st_size,
                    sha256=actual_sha,
                    status=DownloadStatus.DOWNLOADED.value,
                    attempts=attempts,
                    resumed=(start_bytes > 0),
                )
            finally:
                limiter.release()

        try:
            return retry_with_backoff(_do_download, max_retries=self.max_retries)
        except Exception as e:
            return DownloadResult(
                destination=dest,
                status=DownloadStatus.FAILED.value,
                attempts=attempts,
                error=str(e),
            )
