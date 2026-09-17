"""Tests for multi-source metadata enrichment and Vietnamese evidence modeling."""

from pathlib import Path
from music_dataset.constants import EvidenceType, RelevanceStatus
from music_dataset.metadata.enrichment import MetadataEnrichmentEngine
from music_dataset.schema import Track


def test_enrichment_gathers_vietnamese_evidence(tmp_path: Path):
    engine = MetadataEnrichmentEngine(raw_dir=tmp_path)
    track = Track(
        track_id="vn_test_001",
        dataset="vietnam_music_genre",
        source_id="duyen_phan",
        title="Duyên Phận",
        artist="Như Quỳnh",
        genre_original="Bolero",
        genre="bolero",
        is_vietnamese_song=True,
        is_vietnamese_lyrics=True,
        language_status="detected_vi",
        language_confidence=0.98,
    )

    enriched = engine.enrich_track(track)

    assert enriched.vietnamese_relevance["status"] == RelevanceStatus.CONFIRMED.value
    assert enriched.vietnamese_relevance["confidence"] >= 0.95

    evidence_types = {e["evidence_type"] for e in enriched.vietnamese_relevance["evidence"]}
    assert EvidenceType.VIETNAMESE_DATASET_ASSERTION.value in evidence_types
    assert EvidenceType.VIETNAMESE_GENRE.value in evidence_types
    assert EvidenceType.VIETNAMESE_TITLE.value in evidence_types
    assert EvidenceType.VIETNAMESE_ARTIST.value in evidence_types
    assert EvidenceType.VIETNAMESE_LYRICS.value in evidence_types


def test_unified_dict_structure():
    track = Track(
        track_id="t999",
        dataset="vietnam_music_genre",
        source_id="track_999",
        source_url="kaggle://datasets/xuaam1/vietnam-music-genre/Bolero/999.mp3",
        title="Nỗi Buồn Gác Trọ",
        artist="Phương Dung",
        genre="bolero",
        genre_original="Bolero",
        is_vietnamese_song=True,
        is_vietnamese_lyrics=None,
        language_status="dataset_asserted_vi",
    )
    d = track.to_unified_dict()

    assert d["track_id"] == "t999"
    assert d["dataset"] == "vietnam_music_genre"
    assert "source" in d and d["source"]["primary"] == "kaggle"
    assert "metadata" in d and d["metadata"]["title"] == "Nỗi Buồn Gác Trọ"
    assert "language" in d and d["language"]["is_vietnamese_song"] is True
    assert d["language"]["is_vietnamese_lyrics"] is None
    assert "lyrics" in d and d["lyrics"]["status"] == "missing"
    assert "audio" in d and "sha256" in d["audio"]
    assert "enrichment" in d and "msd" in d["enrichment"] and "fma" in d["enrichment"] and "upf" in d["enrichment"]
    assert "vietnamese_relevance" in d
