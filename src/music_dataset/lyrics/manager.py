"""Lyrics Manager coordinating multiple lyrics providers."""

from pathlib import Path
from typing import List, Optional
from music_dataset.constants import AssetStatus
from music_dataset.lyrics.base import LyricsProvider, LyricsResult
from music_dataset.lyrics.embedded_provider import EmbeddedLyricsProvider
from music_dataset.lyrics.lrclib_provider import LrclibLyricsProvider
from music_dataset.schema import Track


class LyricsManager:
    def __init__(
        self,
        output_dir: Path = Path("datasets"),
        enable_external: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.embedded_provider = EmbeddedLyricsProvider()
        self.providers: List[LyricsProvider] = []
        if enable_external:
            self.providers.append(LrclibLyricsProvider())

    def fetch_lyrics_for_track(
        self,
        track: Track,
        audio_file_path: Optional[Path] = None,
    ) -> Optional[LyricsResult]:
        """
        Attempt to fetch lyrics:
        1. From audio file (USLT / companion)
        2. From registered external providers
        """
        # 1. Embedded
        if audio_file_path and Path(audio_file_path).exists():
            embedded = self.embedded_provider.extract_from_audio_file(Path(audio_file_path))
            if embedded:
                return embedded

        # 2. External providers
        if track.title:
            for provider in self.providers:
                res = provider.search_lyrics(
                    title=track.title,
                    artist=track.artist,
                    album=track.album,
                )
                if res:
                    return res

        return None

    def save_lyrics(self, dataset: str, track_id: str, lyrics_text: str) -> Path:
        """Save normalized lyrics to datasets/{dataset}/lyric/{track_id}.txt."""
        target_dir = self.output_dir / dataset / "lyric"
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"{track_id}.txt"
        file_path.write_text(lyrics_text, encoding="utf-8")
        return file_path
