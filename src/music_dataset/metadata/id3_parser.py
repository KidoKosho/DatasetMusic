"""ID3 tag parser using mutagen with fallback safety."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import mutagen
from mutagen.id3 import ID3, APIC, TALB, TCON, TDRC, TIT2, TPE1, TYER, USLT
from mutagen.mp3 import MP3


@dataclass
class ParsedID3Metadata:
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    lyrics: Optional[str] = None
    artwork_bytes: Optional[bytes] = None
    artwork_mime: Optional[str] = None
    raw_tags: Dict[str, Any] = field(default_factory=dict)
    has_id3: bool = False


class ID3Parser:
    """Safely extracts TIT2, TPE1, TALB, TDRC/TYER, TCON, APIC, USLT from MP3."""

    @staticmethod
    def parse_file(file_path: Path) -> ParsedID3Metadata:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return ParsedID3Metadata(has_id3=False)

        result = ParsedID3Metadata()
        try:
            audio = MP3(path, ID3=ID3)
            if not audio.tags:
                return result
            tags = audio.tags
            result.has_id3 = True

            # TIT2 -> Title
            if "TIT2" in tags and tags["TIT2"].text:
                result.title = str(tags["TIT2"].text[0]).strip()

            # TPE1 -> Artist
            if "TPE1" in tags and tags["TPE1"].text:
                result.artist = str(tags["TPE1"].text[0]).strip()

            # TALB -> Album
            if "TALB" in tags and tags["TALB"].text:
                result.album = str(tags["TALB"].text[0]).strip()

            # TCON -> Genre
            if "TCON" in tags and tags["TCON"].text:
                result.genre = str(tags["TCON"].text[0]).strip()

            # TDRC / TYER -> Year
            year_val = None
            if "TDRC" in tags and tags["TDRC"].text:
                year_text = str(tags["TDRC"].text[0])
                # Year can be "2021-05-12" or "2021"
                try:
                    year_val = int(year_text[:4])
                except (ValueError, TypeError):
                    pass
            elif "TYER" in tags and tags["TYER"].text:
                try:
                    year_val = int(str(tags["TYER"].text[0])[:4])
                except (ValueError, TypeError):
                    pass
            result.year = year_val

            # USLT -> Lyrics
            for key in tags.keys():
                if key.startswith("USLT"):
                    uslt = tags[key]
                    if hasattr(uslt, "text") and uslt.text:
                        result.lyrics = str(uslt.text).strip()
                        break

            # APIC -> Artwork
            for tag_name, tag in tags.items():
                if isinstance(tag, APIC):
                    result.artwork_bytes = tag.data
                    result.artwork_mime = tag.mime or "image/jpeg"
                    break

        except Exception as e:
            # Corrupted ID3 tags should never crash the ingestion
            result.has_id3 = False
            result.raw_tags["error"] = str(e)

        return result
