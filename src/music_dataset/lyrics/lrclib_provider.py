"""LRCLIB open lyrics provider adapter with rate limiting and respectful requests."""

import time
from typing import Optional
import requests
from music_dataset.lyrics.base import LyricsProvider, LyricsResult


class LrclibLyricsProvider(LyricsProvider):
    BASE_URL = "https://lrclib.net/api/get"

    def __init__(self, timeout: int = 10, rate_limit_interval: float = 1.0):
        self.timeout = timeout
        self.rate_limit_interval = rate_limit_interval
        self.last_request = 0.0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MusicDatasetCrawler/0.1.0 (Educational/Research Dataset Pipeline)"
        })

    def search_lyrics(
        self,
        title: str,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> Optional[LyricsResult]:
        if not title:
            return None

        # Respect rate limit
        elapsed = time.time() - self.last_request
        if elapsed < self.rate_limit_interval:
            time.sleep(self.rate_limit_interval - elapsed)
        self.last_request = time.time()

        params = {"track_name": title}
        if artist:
            params["artist_name"] = artist
        if album:
            params["album_name"] = album
        if duration:
            params["duration"] = int(duration)

        try:
            resp = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                plain_lyrics = data.get("plainLyrics") or data.get("syncedLyrics")
                if plain_lyrics and plain_lyrics.strip():
                    return LyricsResult(
                        lyrics=plain_lyrics.strip(),
                        source="lrclib",
                        source_url=f"https://lrclib.net/api/get?track_name={title}",
                        is_synced=bool(data.get("syncedLyrics") and not data.get("plainLyrics")),
                    )
        except Exception:
            # Network or timeout errors
            pass

        return None
