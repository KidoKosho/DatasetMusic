"""Downloader package."""

from music_dataset.downloader.base import BaseDownloader, DownloadResult
from music_dataset.downloader.checksum import compute_file_sha256, verify_file_checksum
from music_dataset.downloader.http import HttpDownloader
from music_dataset.downloader.kaggle import KaggleDownloader
from music_dataset.downloader.manager import DownloaderManager
from music_dataset.downloader.rate_limiter import RateLimitManager
from music_dataset.downloader.repository import RepositoryDownloader
from music_dataset.downloader.resume import ResumeManager
from music_dataset.downloader.retry import retry_with_backoff

from music_dataset.downloader.remote_zip import RemoteZipExtractor, RemoteZipMember

__all__ = [
    "BaseDownloader",
    "DownloadResult",
    "HttpDownloader",
    "KaggleDownloader",
    "RepositoryDownloader",
    "DownloaderManager",
    "RateLimitManager",
    "ResumeManager",
    "retry_with_backoff",
    "compute_file_sha256",
    "verify_file_checksum",
    "RemoteZipExtractor",
    "RemoteZipMember",
]
