"""Lyrics package."""

from music_dataset.lyrics.base import LyricsProvider, LyricsResult
from music_dataset.lyrics.embedded_provider import EmbeddedLyricsProvider
from music_dataset.lyrics.lrclib_provider import LrclibLyricsProvider
from music_dataset.lyrics.manager import LyricsManager

__all__ = [
    "LyricsProvider",
    "LyricsResult",
    "EmbeddedLyricsProvider",
    "LrclibLyricsProvider",
    "LyricsManager",
]
