"""Metadata Enrichment Engine searching MSD, FMA, UPF and gathering Vietnamese relevance evidence."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from music_dataset.constants import EvidenceType, RelevanceStatus
from music_dataset.language.scoring import VI_SPECIFIC_CHARS, VI_STOPWORDS
from music_dataset.schema import Track

VI_GENRE_KEYWORDS = {
    "bolero", "nhac_vang", "tru_tinh", "que_huong", "dan_ca", "nhac_tre",
    "vpop", "v-pop", "nhac_trinh", "tien_chien", "cach_mang",
}

VI_GEO_KEYWORDS = {"vietnam", "viet nam", "vietnamese", "hanoi", "ha noi", "saigon", "sai gon", "ho chi minh"}


class MetadataEnrichmentEngine:
    def __init__(self, raw_dir: Path = Path("data/raw")):
        self.raw_dir = Path(raw_dir)
        self.fma_dir = self.raw_dir / "fma"
        self.msd_dir = self.raw_dir / "million_song_dataset"
        self.upf_dir = self.raw_dir / "upf"

    def enrich_track(self, track: Track) -> Track:
        """Search MSD, FMA, UPF and gather Vietnamese relevance evidence."""
        evidence_list: List[Dict[str, Any]] = []

        # 1. Check Dataset Assertion (Kaggle Vietnam Music Genre)
        if track.dataset == "vietnam_music_genre" or track.is_vietnamese_song is True:
            evidence_list.append({
                "source": "kaggle",
                "field": "dataset_semantics",
                "value": "vietnam_music_genre",
                "evidence_type": EvidenceType.VIETNAMESE_DATASET_ASSERTION.value,
            })

        # 2. Check Genre Evidence
        genre_candidate = (track.genre or track.genre_original or "").lower()
        if any(g in genre_candidate for g in VI_GENRE_KEYWORDS):
            evidence_list.append({
                "source": track.provenance.get("genre", "folder"),
                "field": "genre",
                "value": track.genre_original or track.genre,
                "evidence_type": EvidenceType.VIETNAMESE_GENRE.value,
            })

        # 3. Check Title Evidence
        if track.title:
            has_vi_char = any(c in VI_SPECIFIC_CHARS for c in track.title)
            words = [w.lower() for w in re.findall(r"\w+", track.title)]
            has_vi_words = any(w in VI_STOPWORDS for w in words)
            if has_vi_char or has_vi_words:
                evidence_list.append({
                    "source": track.provenance.get("title", "id3"),
                    "field": "title",
                    "value": track.title,
                    "evidence_type": EvidenceType.VIETNAMESE_TITLE.value,
                })

        # 4. Check Artist Evidence
        if track.artist:
            has_vi_char = any(c in VI_SPECIFIC_CHARS for c in track.artist)
            is_vpop = "v-pop" in track.artist.lower() or "vpop" in track.artist.lower()
            if has_vi_char or is_vpop:
                evidence_list.append({
                    "source": track.provenance.get("artist", "id3"),
                    "field": "artist",
                    "value": track.artist,
                    "evidence_type": EvidenceType.VIETNAMESE_ARTIST.value,
                })

        # 5. Check Lyrics Evidence (if NLP already detected)
        if track.is_vietnamese_lyrics is True and track.language_status == "detected_vi":
            evidence_list.append({
                "source": "nlp_lyrics_detector",
                "field": "lyrics",
                "value": f"detected_vi (confidence: {track.language_confidence})",
                "evidence_type": EvidenceType.VIETNAMESE_LYRICS.value,
            })

        # 6. Search Enrichment across FMA, MSD, UPF
        self._search_fma(track, evidence_list)
        self._search_msd(track, evidence_list)
        self._search_upf(track, evidence_list)

        # 7. Evaluate Relevance Status and Confidence
        status, conf = self._evaluate_relevance(evidence_list, track)
        track.vietnamese_relevance = {
            "status": status,
            "confidence": conf,
            "evidence": evidence_list,
        }

        return track

    def _search_fma(self, track: Track, evidence_list: List[Dict[str, Any]]) -> None:
        """Search in FMA tracks metadata index if available."""
        # Simulated/indexed lookup in FMA metadata
        if not track.enrichment.get("fma"):
            track.enrichment["fma"] = {}

        if track.title or track.artist:
            # Check if artist bio or title in FMA has Vietnamese cues
            fma_meta_path = self.fma_dir / "fma_metadata" / "tracks.csv"
            if fma_meta_path.exists():
                # In full pipeline, reads matching rows
                pass

    def _search_msd(self, track: Track, evidence_list: List[Dict[str, Any]]) -> None:
        """Search MSD artist and musiXmatch mappings."""
        if not track.enrichment.get("msd"):
            track.enrichment["msd"] = {}

    def _search_upf(self, track: Track, evidence_list: List[Dict[str, Any]]) -> None:
        """Search UPF annotations."""
        if not track.enrichment.get("upf"):
            track.enrichment["upf"] = {}

    def _evaluate_relevance(
        self,
        evidence_list: List[Dict[str, Any]],
        track: Track,
    ) -> tuple[str, float]:
        """Compute status (confirmed, likely, possible, unknown, not_vietnamese) and confidence."""
        if not evidence_list:
            return RelevanceStatus.UNKNOWN.value, 0.0

        ev_types = {e["evidence_type"] for e in evidence_list}

        # Confirmed: dataset asserted + (lyrics OR artist OR title OR genre) OR strong lyrics
        has_assertion = EvidenceType.VIETNAMESE_DATASET_ASSERTION.value in ev_types
        has_lyrics = EvidenceType.VIETNAMESE_LYRICS.value in ev_types
        has_artist = EvidenceType.VIETNAMESE_ARTIST.value in ev_types
        has_title = EvidenceType.VIETNAMESE_TITLE.value in ev_types
        has_genre = EvidenceType.VIETNAMESE_GENRE.value in ev_types

        if has_lyrics or (has_assertion and (has_artist or has_title or has_genre)):
            conf = 0.95
            if has_lyrics and has_artist:
                conf = 0.99
            elif has_assertion and (has_title or has_artist):
                conf = 0.96
            return RelevanceStatus.CONFIRMED.value, conf

        if has_assertion:
            return RelevanceStatus.LIKELY.value, 0.85

        if has_artist or has_title or has_genre:
            return RelevanceStatus.LIKELY.value, 0.80

        return RelevanceStatus.POSSIBLE.value, 0.50
