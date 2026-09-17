"""Text normalization for Vietnamese NLP and lyrics processing."""

import re
import unicodedata
from typing import List

# Regular expression to remove lyric tags, chord markings, timestamps
TIMESTAMP_PATTERN = re.compile(r"\[\d{1,2}:\d{2}(?:\.\d{1,3})?\]")
CHORD_TAG_PATTERN = re.compile(r"\[[A-G][b#]?(?:m|maj|min|dim|aug|sus)?(?:\d)?\]", re.IGNORECASE)
SECTION_TAG_PATTERN = re.compile(r"\[(?:verse|chorus|bridge|intro|outro|pre-chorus|hook|solo)[^\]]*\]", re.IGNORECASE)
PUNCTUATION_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_unicode(text: str) -> str:
    """Normalize text to Unicode NFC form."""
    if not text:
        return ""
    return unicodedata.normalize("NFC", text)


def clean_lyrics_noise(text: str) -> str:
    """Remove LRC timestamps, chord markers, and section header tags."""
    if not text:
        return ""
    cleaned = TIMESTAMP_PATTERN.sub(" ", text)
    cleaned = CHORD_TAG_PATTERN.sub(" ", cleaned)
    cleaned = SECTION_TAG_PATTERN.sub(" ", cleaned)
    return cleaned


def tokenize_words(text: str) -> List[str]:
    """Tokenize normalized text into lower-case words/syllables."""
    if not text:
        return []
    normalized = normalize_unicode(text.lower())
    cleaned = clean_lyrics_noise(normalized)
    # Remove punctuation
    stripped = PUNCTUATION_PATTERN.sub(" ", cleaned)
    words = [w.strip() for w in stripped.split() if w.strip()]
    return words
