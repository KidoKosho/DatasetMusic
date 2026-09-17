"""Embedded lyrics provider extracting from audio file ID3 USLT tags or companion files."""

from pathlib import Path
from typing import Optional
from music_dataset.lyrics.base import LyricsProvider, LyricsResult
from music_dataset.metadata.id3_parser import ID3Parser


class EmbeddedLyricsProvider(LyricsProvider):
    def search_lyrics(
        self,
        title: str,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> Optional[LyricsResult]:
        # Embedded provider requires a local file path
        return None

    def extract_from_audio_file(self, audio_file_path: Path) -> Optional[LyricsResult]:
        path = Path(audio_file_path)
        if not path.exists():
            return None

        # 1. Check ID3 USLT
        id3_meta = ID3Parser.parse_file(path)
        if id3_meta.lyrics and id3_meta.lyrics.strip():
            return LyricsResult(
                lyrics=id3_meta.lyrics.strip(),
                source="embedded_id3_uslt",
                source_url=str(path),
            )

        # 2. Check companion .lrc or .txt in same directory
        for ext in (".lrc", ".txt"):
            companion = path.with_suffix(ext)
            if companion.exists() and companion.is_file():
                try:
                    content = companion.read_text(encoding="utf-8", errors="replace").strip()
                    if content:
                        return LyricsResult(
                            lyrics=content,
                            source="companion_file",
                            source_url=str(companion),
                            is_synced=(ext == ".lrc"),
                        )
                except Exception:
                    pass

        return None
