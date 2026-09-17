"""Metadata normalization functions."""

import re
from typing import Optional

GENRE_MAP = {
    "bolero": "bolero",
    "nhac do": "nhac_do",
    "nhacdo": "nhac_do",
    "nhacdo vietnamese": "nhac_do",
    "nhac do vietnamese": "nhac_do",
    "cach mang": "nhac_do",
    "do": "nhac_do",
    "tien chien": "tien_chien",
    "hip hop": "hip_hop",
    "hip-hop": "hip_hop",
    "hiphop": "hip_hop",
    "hiphop vietnamese": "hip_hop",
    "rap": "hip_hop",
    "rap viet": "hip_hop",
    "bolero": "bolero",
    "bolero vietnamese": "bolero",
    "nhac vang": "bolero",
    "tru tinh": "tru_tinh",
    "que huong": "que_huong",
    "dan ca": "dan_ca",
    "ballad": "ballad",
    "ballad vietnamese": "ballad",
    "pop": "pop",
    "v-pop": "pop",
    "vpop": "pop",
    "nhac tre": "pop",
    "thieu nhi": "thieu_nhi",
    "kidsong": "thieu_nhi",
    "kidsong vietnamese": "thieu_nhi",
    "r&b": "rnb",
    "rnb": "rnb",
    "rb": "rnb",
    "rb vietnamese": "rnb",
    "rock": "rock",
    "rock viet": "rock",
    "edm": "electronic",
    "electronic": "electronic",
    "dance": "electronic",
    "indie": "indie",
    "acoustic": "acoustic",
    "trinh": "nhac_trinh",
    "nhac trinh": "nhac_trinh",
}


def normalize_genre(raw_genre: Optional[str]) -> Optional[str]:
    """Normalize raw genre string to canonical format."""
    if not raw_genre:
        return None
    cleaned = raw_genre.lower().strip()
    cleaned = re.sub(r"[_\-\/\\]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned in GENRE_MAP:
        return GENRE_MAP[cleaned]
    # Check without 'vietnamese' suffix
    if cleaned.endswith(" vietnamese"):
        prefix = cleaned[:-11].strip()
        if prefix in GENRE_MAP:
            return GENRE_MAP[prefix]
    return cleaned.replace(" ", "_")


def split_camel_case(s: str) -> str:
    """Split CamelCase words like '100YearsLOVESingle' -> '100 Years LOVE Single'."""
    s = re.sub(r"([0-9]+)([a-zA-Z]+)", r"\1 \2", s)
    s = re.sub(r"([a-zA-Z]+)([0-9]+)", r"\1 \2", s)
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_vietnam_genre_filename(filename: Optional[str], folder_genre: Optional[str] = None) -> dict:
    """
    Parses Vietnamese music dataset filenames.
    Particularly handles:
      1. Zing MP3 / MIR segment naming convention:
         <Title>-<Artist>-<SongID>_<Quality>_segment_<Index>.mp3
      2. NDNM2k3 numbered files:
         <Index>_<Title> - <Artist> [extras].wav or <Index>_<Title>.wav
    """
    if not filename:
        return {}

    # Strip extension
    stem = re.sub(r"\.[a-zA-Z0-9]+$", "", filename)

    # Clean off common Youtube/Zing noise tokens
    clean_stem = re.sub(r"_(?:Official\s*(?:Music\s*Video|MV|Lyric\s*Video|Lyrics\s*Video|Audio)?|MV\s*Full\s*HD|HD|Audio|Official)_?", "", stem, flags=re.IGNORECASE).strip()

    # 1. Check Zing MP3 segment convention: <Title>-<Artist>-<ID>_<Quality>_segment_<Index>
    m_seg = re.match(r"^([^-]+)-([^-]+)-(\d+)(?:_([a-zA-Z0-9]+))?(?:_segment_(\d+))?$", stem)
    if m_seg:
        raw_title, raw_artist, song_id, quality, segment = m_seg.groups()
        title = split_camel_case(raw_title)
        artist = split_camel_case(raw_artist)
        return {
            "title": title,
            "artist": artist,
            "song_id": song_id,
            "quality": quality,
            "segment": int(segment) if segment else None,
            "genre_original": folder_genre,
            "genre": normalize_genre(folder_genre) if folder_genre else None,
            "is_vietnamese_song": True,
            "is_vietnamese_artist": True,
            "is_vietnamese_title": True,
            "naming_convention": "zing_mp3_segment",
        }

    # 2. Check NDNM2k3 numbered index pattern: <Index>_<Rest> with artist separator
    m_ndnm = re.match(r"^(\d+)_(.+)$", clean_stem)
    if m_ndnm:
        track_idx, rest = m_ndnm.groups()
        rest = rest.strip()
        if " - " in rest or " _ " in rest:
            if " - " in rest:
                parts = rest.split(" - ", 1)
            else:
                parts = rest.split(" _ ", 1)
            title, artist = parts[0].strip(), parts[1].strip()
            return {
                "title": title,
                "artist": artist,
                "song_id": track_idx,
                "genre_original": folder_genre,
                "genre": normalize_genre(folder_genre) if folder_genre else None,
                "is_vietnamese_song": True,
                "is_vietnamese_artist": True,
                "is_vietnamese_title": True,
                "naming_convention": "ndnm2k3_numbered",
            }

    # 3. General hyphen separated: <Title> - <Artist> or <Artist> - <Title>
    if "-" in stem:
        parts = [p.strip() for p in stem.split("-") if p.strip()]
        if len(parts) >= 2:
            return {
                "title": split_camel_case(parts[0]),
                "artist": split_camel_case(parts[1]),
                "genre_original": folder_genre,
                "genre": normalize_genre(folder_genre) if folder_genre else None,
                "is_vietnamese_song": True,
                "is_vietnamese_artist": True,
                "is_vietnamese_title": True,
                "naming_convention": "hyphen_separated",
            }

    # 4. Fallback: snake_case / raw stem
    title = stem.replace("_", " ").title()
    return {
        "title": title,
        "artist": None,
        "genre_original": folder_genre,
        "genre": normalize_genre(folder_genre) if folder_genre else None,
        "is_vietnamese_song": True,
        "is_vietnamese_artist": True,
        "is_vietnamese_title": True,
        "naming_convention": "stem_fallback",
    }


def fallback_title_from_filename(filename: Optional[str]) -> Optional[str]:
    """
    Extract title fallback from filename.
    ONLY used when structured metadata, ID3, and providers are missing.
    """
    if not filename:
        return None
    # Strip extension
    name = re.sub(r"\.[a-zA-Z0-9]+$", "", filename)
    # Strip leading track numbers like "01 - ", "01. "
    name = re.sub(r"^\d+[\s\.\-_]+", "", name)
    # Strip trailing resolution, MV tags
    name = re.sub(r"\[.*?\]|\(.*?\)", "", name)
    cleaned = name.strip()
    return cleaned if cleaned else None
