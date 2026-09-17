"""Metadata Precedence Engine ensuring structured > ID3 > provider > filename fallback."""

from typing import Any, Dict, Optional, Tuple
from music_dataset.metadata.id3_parser import ParsedID3Metadata
from music_dataset.metadata.normalizer import (
    fallback_title_from_filename,
    normalize_genre,
    parse_vietnam_genre_filename,
)


class MetadataPrecedenceResolver:
    """
    Applies the strict 5-tier precedence hierarchy:
    1. Structured dataset metadata
    2. Embedded ID3 metadata (TIT2, TPE1, TALB, TDRC/TYER, TCON)
    3. Trusted metadata provider
    4. Filename (fallback only)
    5. None
    """

    @staticmethod
    def resolve(
        structured: Dict[str, Any],
        id3: Optional[ParsedID3Metadata] = None,
        provider: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        provider = provider or {}
        provenance: Dict[str, str] = {}

        parsed_fn = parse_vietnam_genre_filename(filename) if filename else {}

        # 1. Title
        title = None
        if structured.get("title"):
            title = str(structured["title"]).strip()
            provenance["title"] = "structured_dataset"
        elif id3 and id3.title:
            title = id3.title
            provenance["title"] = "embedded_id3"
        elif provider.get("title"):
            title = str(provider["title"]).strip()
            provenance["title"] = "metadata_provider"
        elif parsed_fn.get("title"):
            title = parsed_fn["title"]
            provenance["title"] = "filename_parser"
        elif filename:
            fallback = fallback_title_from_filename(filename)
            if fallback:
                title = fallback
                provenance["title"] = "filename_fallback"

        # 2. Artist
        artist = None
        if structured.get("artist"):
            artist = str(structured["artist"]).strip()
            provenance["artist"] = "structured_dataset"
        elif id3 and id3.artist:
            artist = id3.artist
            provenance["artist"] = "embedded_id3"
        elif provider.get("artist"):
            artist = str(provider["artist"]).strip()
            provenance["artist"] = "metadata_provider"
        elif parsed_fn.get("artist"):
            artist = parsed_fn["artist"]
            provenance["artist"] = "filename_parser"

        if parsed_fn.get("song_id"):
            provenance["source_song_id"] = str(parsed_fn["song_id"])
        if parsed_fn.get("segment") is not None:
            provenance["segment"] = str(parsed_fn["segment"])

        # 3. Album
        album = None
        if structured.get("album"):
            album = str(structured["album"]).strip()
            provenance["album"] = "structured_dataset"
        elif id3 and id3.album:
            album = id3.album
            provenance["album"] = "embedded_id3"
        elif provider.get("album"):
            album = str(provider["album"]).strip()
            provenance["album"] = "metadata_provider"

        # 4. Year
        year = None
        if structured.get("year"):
            try:
                year = int(structured["year"])
                provenance["year"] = "structured_dataset"
            except (ValueError, TypeError):
                pass
        if year is None and id3 and id3.year:
            year = id3.year
            provenance["year"] = "embedded_id3"
        if year is None and provider.get("year"):
            try:
                year = int(provider["year"])
                provenance["year"] = "metadata_provider"
            except (ValueError, TypeError):
                pass

        # 5. Genre
        genre = None
        genre_original = structured.get("genre_original") or structured.get("genre")
        if genre_original:
            genre = normalize_genre(genre_original)
            provenance["genre"] = "structured_dataset"
        elif id3 and id3.genre:
            genre_original = id3.genre
            genre = normalize_genre(id3.genre)
            provenance["genre"] = "embedded_id3"
        elif provider.get("genre"):
            genre_original = provider["genre"]
            genre = normalize_genre(provider["genre"])
            provenance["genre"] = "metadata_provider"

        resolved = {
            "title": title,
            "artist": artist,
            "album": album,
            "year": year,
            "genre": genre,
            "genre_original": genre_original,
        }
        return resolved, provenance
