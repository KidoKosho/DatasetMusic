"""Kaggle dataset downloader with credential detection and safe staging download."""

import os
from pathlib import Path
from typing import Optional, Tuple
from music_dataset.constants import DownloadStatus
from music_dataset.downloader.base import BaseDownloader, DownloadResult


class KaggleDownloader(BaseDownloader):
    def __init__(self, raw_staging_dir: Path = Path("data/raw")):
        self.raw_staging_dir = Path(raw_staging_dir)

    @staticmethod
    def check_credentials() -> Tuple[bool, str]:
        """
        Check if Kaggle credentials exist either via environment variables or ~/.kaggle/kaggle.json.
        Never logs or exposes the credentials in plain text.
        """
        user_env = os.environ.get("KAGGLE_USERNAME")
        key_env = os.environ.get("KAGGLE_KEY")
        if user_env and key_env:
            return True, "Credentials found in environment variables (KAGGLE_USERNAME, KAGGLE_KEY)"

        kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
        if kaggle_json.exists() and kaggle_json.is_file():
            return True, f"Credentials found at {kaggle_json}"

        return False, (
            "Kaggle credentials missing. Please set KAGGLE_USERNAME and KAGGLE_KEY "
            "environment variables, or place kaggle.json in ~/.kaggle/ directory."
        )

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
        """
        Download dataset from Kaggle (e.g. dataset 'xuaam1/vietnam-music-genre').
        URL or dataset identifier can be passed.
        """
        has_creds, msg = self.check_credentials()
        dest = Path(destination)
        if not has_creds:
            return DownloadResult(
                destination=dest,
                status=DownloadStatus.FAILED.value,
                attempts=1,
                error=msg,
            )

        # Extract dataset slug, e.g. "xuaam1/vietnam-music-genre"
        slug = url
        if "kaggle.com/datasets/" in url:
            slug = url.split("kaggle.com/datasets/")[-1].strip("/")

        dest.mkdir(parents=True, exist_ok=True)
        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
            api = KaggleApi()
            api.authenticate()
            api.dataset_download_files(slug, path=str(dest), unzip=True, quiet=False)
            return DownloadResult(
                destination=dest,
                status=DownloadStatus.DOWNLOADED.value,
                attempts=1,
            )
        except Exception as e:
            return DownloadResult(
                destination=dest,
                status=DownloadStatus.FAILED.value,
                attempts=1,
                error=f"Kaggle download failed for {slug}: {e}",
            )
