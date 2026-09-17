"""Tests for Vietnamese Relevance and Candidate Decision Logic."""

import pytest
from music_dataset.language.artist_detector import ArtistDetector
from music_dataset.language.genre_tag_detector import GenreTagDetector
from music_dataset.language.title_detector import TitleDetector
from music_dataset.language.relevance_detector import RelevanceDetector


def test_single_reason_candidate():
    """Verify Section 16 rule: only ONE matching reason is needed for candidate = True."""
    detector = RelevanceDetector()

    # Case 1: ONLY artist is Vietnamese
    res_artist_only = detector.evaluate_track({
        "artist_name": "Đan Trường",
        "title": "Forever Love",
        "genre": "Pop",
        "dataset": "fma",
    })
    assert res_artist_only["candidate"] is True
    assert "vietnamese_artist" in res_artist_only["reasons"]
    # Crucial test: is_vietnamese_artist does NOT set is_vietnamese_lyrics
    assert res_artist_only["is_vietnamese_lyrics"] is None

    # Case 2: ONLY title is Vietnamese
    res_title_only = detector.evaluate_track({
        "artist_name": "John Doe",
        "title": "Bài Ca Hy Vọng",
        "genre": "Pop",
        "dataset": "fma",
    })
    assert res_title_only["candidate"] is True
    assert "vietnamese_title" in res_title_only["reasons"]
    # Title does NOT imply artist is Vietnamese
    assert res_title_only["is_vietnamese_artist"] is False

    # Case 3: ONLY genre is Vietnamese
    res_genre_only = detector.evaluate_track({
        "artist_name": "Unknown Singer",
        "title": "Track 01",
        "genre": "Bolero",
        "dataset": "fma",
    })
    assert res_genre_only["candidate"] is True
    assert "vietnamese_genre" in res_genre_only["reasons"]

    # Case 4: No Vietnamese evidence
    res_none = detector.evaluate_track({
        "artist_name": "The Beatles",
        "title": "Yesterday",
        "genre": "Rock",
        "dataset": "fma",
    })
    assert res_none["candidate"] is False
    assert len(res_none["reasons"]) == 0


def test_artist_country_evidence():
    detector = ArtistDetector()
    res = detector.detect({"artist_country": "Vietnam", "artist": "Alice"})
    assert res["is_vietnamese_artist"] is True
    assert res["evidence"]["reason"] == "country_is_vietnam"


def test_title_detector_diacritics():
    detector = TitleDetector()
    res = detector.detect("Nỗi Nhớ Mùa Đông")
    assert res["is_vietnamese_title"] is True
    assert "vietnamese_diacritics" in res["evidence"]["reason"]


def test_genre_tag_detector():
    detector = GenreTagDetector()
    res = detector.detect(genre="nhac_vang", tags=["vietnamese folk"])
    assert res["has_vietnamese_genre"] is True
