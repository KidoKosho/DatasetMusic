"""Artwork downloader for remote cover art URLs."""

from pathlib import Path
from typing import Optional
from music_dataset.constants import DownloadStatus
from music_dataset.downloader.http import HttpDownloader


class ArtworkDownloader:
    def __init__(self, http_downloader: Optional[HttpDownloader] = None):
        self.http_downloader = http_downloader or HttpDownloader()

    def download_artwork(
        self,
        url: str,
        output_dir: Path,
        track_id: str,
    ) -> Optional[Path]:
        """Download remote artwork image to output_dir / {track_id}.jpg."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / f"{track_id}.jpg"

        res = self.http_downloader.download(url, dest)
        if res.status == DownloadStatus.DOWNLOADED.value:
            return dest
        return None
