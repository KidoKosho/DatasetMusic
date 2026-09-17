"""Unified Vietnamese Relevance Detector coordinating NLP, Artist, Title, Genre, and Annotation evidence."""

from typing import Any, Dict, List, Optional
from music_dataset.language.artist_detector import ArtistDetector
from music_dataset.language.genre_tag_detector import GenreTagDetector
from music_dataset.language.title_detector import TitleDetector
from music_dataset.language.vietnamese_detector import VietnameseDetector


class RelevanceDetector:
    """
    Evaluates tracks against all Vietnamese evidence criteria using the core rule:
    candidate = any([
        is_vietnamese_lyrics,
        is_vietnamese_artist,
        is_vietnamese_title,
        is_vietnamese_language,
        is_vietnamese_country,
        has_vietnamese_genre,
        has_vietnamese_tag,
        has_vietnamese_annotation,
    ])
    """

    def __init__(self):
        self.artist_detector = ArtistDetector()
        self.title_detector = TitleDetector()
        self.genre_detector = GenreTagDetector()
        self.lyrics_detector = VietnameseDetector()

    def evaluate_track(self, metadata: Dict[str, Any], source: str = "unknown") -> Dict[str, Any]:
        """
        Evaluate full track metadata dictionary and return candidate decision with provenance.
        """
        reasons: List[str] = []
        evidence_list: List[Dict[str, Any]] = []

        # 1. Dataset annotation / assertion (e.g. Kaggle Vietnam Music Genre)
        is_vietnamese_annotation = False
        dataset_name = str(metadata.get("dataset") or "").lower()
        if dataset_name == "vietnam_music_genre" or metadata.get("is_vietnamese_song") is True:
            is_vietnamese_annotation = True
            reasons.append("vietnamese_annotation")
            evidence_list.append({
                "type": "vietnamese_annotation",
                "source": "kaggle" if dataset_name == "vietnam_music_genre" else source,
                "field": "dataset_semantics",
                "value": metadata.get("dataset_semantics") or "vietnam_music_genre",
                "reason": "dataset_is_curated_vietnamese_music",
            })

        # 2. Artist & Country Detector
        artist_res = self.artist_detector.detect(metadata, source=source)
        is_vietnamese_artist = bool(artist_res.get("is_vietnamese_artist"))
        is_vietnamese_country = False
        if is_vietnamese_artist:
            reasons.append("vietnamese_artist")
            ev = artist_res.get("evidence")
            if ev:
                evidence_list.append({
                    "type": "vietnamese_artist",
                    "source": ev.get("source", source),
                    "field": ev.get("field", "artist"),
                    "value": ev.get("value"),
                    "reason": ev.get("reason"),
                })
                if ev.get("reason") == "country_is_vietnam":
                    is_vietnamese_country = True
                    reasons.append("vietnamese_country")

        # 3. Title Detector
        title = metadata.get("title")
        title_res = self.title_detector.detect(title, source=source)
        is_vietnamese_title = bool(title_res.get("is_vietnamese_title"))
        if is_vietnamese_title:
            reasons.append("vietnamese_title")
            ev = title_res.get("evidence")
            if ev:
                evidence_list.append({
                    "type": "vietnamese_title",
                    "source": ev.get("source", source),
                    "field": "title",
                    "value": ev.get("value"),
                    "reason": ev.get("reason"),
                })

        # Curated dataset inheritance (all tracks in vietnam_music_genre are Vietnamese)
        if is_vietnamese_annotation:
            if not is_vietnamese_artist:
                is_vietnamese_artist = True
                reasons.append("vietnamese_artist")
                evidence_list.append({
                    "type": "vietnamese_artist",
                    "source": "kaggle",
                    "field": "artist",
                    "value": metadata.get("artist") or "Vietnamese Artist",
                    "reason": "curated_vietnam_music_dataset",
                })
            if not is_vietnamese_title:
                is_vietnamese_title = True
                reasons.append("vietnamese_title")
                evidence_list.append({
                    "type": "vietnamese_title",
                    "source": "kaggle",
                    "field": "title",
                    "value": metadata.get("title") or "Vietnamese Title",
                    "reason": "curated_vietnam_music_dataset",
                })

        # 4. Genre & Tag Detector
        genre = metadata.get("genre_original") or metadata.get("genre")
        tags = metadata.get("tags")
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        genre_res = self.genre_detector.detect(genre=genre, tags=tags, source=source)
        has_vietnamese_genre = False
        has_vietnamese_tag = False
        if genre_res.get("has_vietnamese_genre"):
            ev = genre_res.get("evidence")
            if ev and ev.get("field") == "tags":
                has_vietnamese_tag = True
                reasons.append("vietnamese_tag")
                evidence_list.append({
                    "type": "vietnamese_tag",
                    "source": ev.get("source", source),
                    "field": "tags",
                    "value": ev.get("value"),
                    "reason": ev.get("reason"),
                })
            else:
                has_vietnamese_genre = True
                reasons.append("vietnamese_genre")
                if ev:
                    evidence_list.append({
                        "type": "vietnamese_genre",
                        "source": ev.get("source", source),
                        "field": "genre",
                        "value": ev.get("value"),
                        "reason": ev.get("reason"),
                    })

        # 5. Language code field
        lang = str(metadata.get("language") or metadata.get("lang") or "").lower()
        is_vietnamese_language = lang in ("vi", "vie", "vietnamese", "tiếng việt")
        if is_vietnamese_language:
            reasons.append("vietnamese_language")
            evidence_list.append({
                "type": "vietnamese_language",
                "source": source,
                "field": "language",
                "value": lang,
            })

        # 6. Lyrics Detector (Strictly independent!)
        lyrics = metadata.get("lyrics")
        is_vietnamese_lyrics: Optional[bool] = None
        lyrics_conf = 0.0
        if lyrics and isinstance(lyrics, str) and len(lyrics.strip()) > 10:
            det_res = self.lyrics_detector.detect(lyrics)
            lyrics_conf = det_res.confidence
            if det_res.status == "detected_vi":
                is_vietnamese_lyrics = True
                reasons.append("vietnamese_lyrics")
                evidence_list.append({
                    "type": "vietnamese_lyrics",
                    "source": "lyrics_nlp_detector",
                    "field": "lyrics",
                    "value": f"detected_vi (confidence: {lyrics_conf:.2f})",
                    "method": det_res.method,
                })
            elif det_res.status == "detected_non_vi":
                is_vietnamese_lyrics = False
            else:
                is_vietnamese_lyrics = None

        # Section 16 Core Logic: Any single reason qualifies the track as a candidate!
        candidate = any([
            is_vietnamese_lyrics is True,
            is_vietnamese_artist,
            is_vietnamese_title,
            is_vietnamese_language,
            is_vietnamese_country,
            has_vietnamese_genre,
            has_vietnamese_tag,
            is_vietnamese_annotation,
        ])

        return {
            "candidate": candidate,
            "reasons": sorted(list(set(reasons))),
            "is_vietnamese_artist": is_vietnamese_artist,
            "is_vietnamese_title": is_vietnamese_title,
            "is_vietnamese_lyrics": is_vietnamese_lyrics,
            "is_vietnamese_language": is_vietnamese_language,
            "is_vietnamese_country": is_vietnamese_country,
            "has_vietnamese_genre": has_vietnamese_genre,
            "has_vietnamese_tag": has_vietnamese_tag,
            "is_vietnamese_annotation": is_vietnamese_annotation,
            "evidence": evidence_list,
        }
