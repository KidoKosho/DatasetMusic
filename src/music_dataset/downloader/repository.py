"""Generic repository downloader and inspector for academic repositories (UPF/DSpace)."""

from pathlib import Path
from typing import Dict, Optional, Tuple
import requests

from music_dataset.constants import DownloadStatus
from music_dataset.downloader.base import BaseDownloader, DownloadResult
from music_dataset.downloader.http import HttpDownloader


class RepositoryDownloader(BaseDownloader):
    def __init__(self, http_downloader: Optional[HttpDownloader] = None, timeout: int = 15):
        self.http_downloader = http_downloader or HttpDownloader(timeout=timeout)
        self.timeout = timeout

    def inspect_repository(self, handle_url: str) -> Dict[str, any]:
        """
        Inspect repository handle endpoint to test connectivity and detect available files.
        Never throws unhandled exceptions.
        """
        try:
            resp = requests.head(handle_url, timeout=self.timeout, allow_redirects=True)
            if resp.status_code == 200:
                return {
                    "status": "online",
                    "accessible": True,
                    "status_code": resp.status_code,
                    "content_type": resp.headers.get("Content-Type", ""),
                }
            elif resp.status_code in (401, 403):
                return {
                    "status": "restricted",
                    "accessible": False,
                    "status_code": resp.status_code,
                    "note": "Authentication required",
                }
            else:
                return {
                    "status": "error",
                    "accessible": False,
                    "status_code": resp.status_code,
                }
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            return {
                "status": "unreachable",
                "accessible": False,
                "error": str(e),
                "note": "Server timed out or closed connection forcibly",
            }
        except Exception as e:
            return {
                "status": "error",
                "accessible": False,
                "error": str(e),
            }

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
        inspection = self.inspect_repository(url)
        if not inspection.get("accessible"):
            return DownloadResult(
                destination=Path(destination),
                status=DownloadStatus.UNAVAILABLE.value,
                attempts=1,
                error=f"Repository not accessible: {inspection.get('note') or inspection.get('status')}",
            )

        return self.http_downloader.download(
            url,
            destination,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
            resume=resume,
            progress_callback=progress_callback,
        )
