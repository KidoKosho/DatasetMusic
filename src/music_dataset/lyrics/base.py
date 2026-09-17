"""Base interface for lyrics providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LyricsResult:
    lyrics: str
    source: str
    source_url: str = ""
    is_synced: bool = False


class LyricsProvider(ABC):
    @abstractmethod
    def search_lyrics(
        self,
        title: str,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> Optional[LyricsResult]:
        """Search and fetch lyrics for a track."""
        pass
