"""Vietnamese Genre and Tag Detector.

Scans genres, tags, and category labels for Vietnamese musical genres.
"""

import re
from typing import Any, Dict, List, Optional

VIETNAMESE_GENRES = {
    "bolero", "nhac_vang", "nhac vang", "tru_tinh", "tru tinh",
    "que_huong", "que huong", "dan_ca", "dan ca", "nhac_tre", "nhac tre",
    "v-pop", "vpop", "vietnam pop", "vietnamese pop",
    "nhac_trinh", "nhac trinh", "tien_chien", "tien chien",
    "cach_mang", "cach mang", "cai_luong", "cai luong",
    "quan_ho", "quan ho", "ca_tru", "ca tru", "cheo", "chèo",
    "hat_van", "hat van", "vietnamese traditional", "vietnamese folk",
    "vietnamese music", "vietnamese song", "vietnamese", "vietnam",
}


class GenreTagDetector:
    """Detects whether genre or tag fields contain Vietnamese music categorizations."""

    def detect(self, genre: Optional[str] = None, tags: Optional[List[str]] = None, source: str = "metadata") -> Dict[str, Any]:
        matched_items: List[str] = []

        # Check genre string
        if genre and genre.strip():
            lower_genre = genre.strip().lower()
            for vg in VIETNAMESE_GENRES:
                if vg in lower_genre:
                    matched_items.append(genre)
                    return {
                        "has_vietnamese_genre": True,
                        "confidence": 0.95,
                        "evidence": {
                            "field": "genre",
                            "value": genre,
                            "source": source,
                            "reason": "matched_vietnamese_genre",
                            "matched_keyword": vg,
                        },
                    }

        # Check tags list
        if tags:
            for tag in tags:
                lower_tag = str(tag).strip().lower()
                # Exclude obvious non-Vietnamese music tags
                if any(ex in lower_tag for ex in ["vietnam cowboy", "vietnam war", "war in vietnam"]):
                    continue
                for vg in VIETNAMESE_GENRES:
                    # Word boundary matching
                    if re.search(r"\b" + re.escape(vg) + r"\b", lower_tag):
                        return {
                            "has_vietnamese_genre": True,
                            "confidence": 0.92,
                            "evidence": {
                                "field": "tags",
                                "value": tag,
                                "source": source,
                                "reason": "matched_vietnamese_tag",
                                "matched_keyword": vg,
                            },
                        }

        return {
            "has_vietnamese_genre": False,
            "confidence": 0.0,
            "evidence": None,
        }
