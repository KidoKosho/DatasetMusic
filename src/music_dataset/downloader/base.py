"""Base Downloader interface and result container."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from music_dataset.constants import DownloadStatus


@dataclass
class DownloadResult:
    destination: Path
    size: int = 0
    sha256: Optional[str] = None
    status: str = DownloadStatus.PENDING.value
    attempts: int = 0
    error: Optional[str] = None
    resumed: bool = False


class BaseDownloader(ABC):
    @abstractmethod
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
        """Download URL to destination file."""
        pass
