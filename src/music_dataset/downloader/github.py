"""GitHub repository and release asset downloader."""

from pathlib import Path
from typing import Optional
from music_dataset.downloader.base import BaseDownloader, DownloadResult
from music_dataset.downloader.http import HttpDownloader


class GitHubDownloader(BaseDownloader):
    def __init__(self, http_downloader: Optional[HttpDownloader] = None):
        self.http_downloader = http_downloader or HttpDownloader()

    def download(
        self,
        url: str,
        destination: Path,
        *,
        expected_size: Optional[int] = None,
        expected_sha256: Optional[str] = None,
        resume: bool = True,
        progress_callback: Optional[any] = None,
    ) -> DownloadResult:
        # Convert GitHub blob URLs to raw.githubusercontent.com if needed
        download_url = url
        if "github.com/" in url and "/blob/" in url:
            download_url = url.replace("github.com/", "raw.githubusercontent.com/").replace("/blob/", "/")

        return self.http_downloader.download(
            download_url,
            destination,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
            resume=resume,
            progress_callback=progress_callback,
        )
