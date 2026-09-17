"""Vietnamese Artist and Geographical Metadata Detector.

Evaluates artist name, bio, and country fields without assuming lyrics language.
"""

import re
from typing import Any, Dict, List, Optional
from music_dataset.language.scoring import VI_SPECIFIC_CHARS, VI_STRICTLY_UNIQUE_CHARS, VI_STOPWORDS

VIETNAM_COUNTRY_VALUES = {
    "vietnam", "viet nam", "việt nam", "vn", "vnm", "vietnamese",
}

VIETNAM_GEO_KEYWORDS = [
    "vietnam", "viet nam", "việt nam", "hanoi", "ha noi", "hà nội",
    "saigon", "sai gon", "sài gòn", "ho chi minh", "hồ chí minh",
    "danang", "da nang", "đà nẵng", "haiphong", "hai phong", "hải phòng",
    "can tho", "cần thơ", "hue", "huế", "mekong",
]

UNAMBIGUOUS_VN_SURNAMES = {
    "nguyen", "nguyễn", "tran", "trần", "pham", "phạm", "hoang", "hoàng",
    "huynh", "huỳnh", "phan", "vu", "vũ", "vo", "võ", "dang", "đặng",
    "bui", "bùi", "truong", "trương", "dinh", "đinh",
}

AMBIGUOUS_SURNAMES = {"le", "lê", "do", "đỗ", "ngo", "ngô", "ly", "lý"}
VN_MIDDLE_NAMES = {"van", "văn", "thi", "thị", "duc", "đức", "anh", "minh", "quang", "tuan", "tuấn", "thanh", "hai", "hải", "hoang", "hoàng", "kim", "ngoc", "ngọc"}


class ArtistDetector:
    """Detects whether artist, author, bio, or country indicates Vietnamese origin."""

    def detect(self, metadata: Dict[str, Any], source: str = "unknown") -> Dict[str, Any]:
        """
        Evaluate metadata dictionary containing possible fields:
        artist, artist_name, artist_bio, artist_country, country, bio, description.
        """
        # 1. Check direct country/location fields using strict word boundary matching
        raw_country = str(metadata.get("artist_country") or metadata.get("country") or "").strip()
        country_lower = raw_country.lower()
        if country_lower:
            matched_geo = None
            # Strict regex matching to avoid 'vn' matching inside words like 'Kryvorivnia', 'Slovenia'
            for v in ["vietnam", "viet nam", "việt nam", "vnm"]:
                if re.search(r"\b" + re.escape(v) + r"\b", country_lower):
                    matched_geo = v
                    break
            if not matched_geo and re.search(r"^\s*vn\s*$", country_lower):
                matched_geo = "vn"
            if not matched_geo:
                for geo in ["hanoi", "ha noi", "hà nội", "saigon", "sai gon", "sài gòn", "ho chi minh", "hồ chí minh", "da nang", "đà nẵng"]:
                    if re.search(r"\b" + re.escape(geo) + r"\b", country_lower):
                        matched_geo = geo
                        break

            if matched_geo:
                return {
                    "is_vietnamese_artist": True,
                    "confidence": 0.96,
                    "evidence": {
                        "field": "artist_country" if metadata.get("artist_country") else "country",
                        "value": raw_country,
                        "source": source,
                        "reason": "country_is_vietnam",
                        "matched_geo": matched_geo,
                    },
                }

        # 2. Check artist name
        artist_name = str(metadata.get("artist_name") or metadata.get("artist") or "").strip()
        if artist_name:
            # Check for Vietnamese diacritics in artist name (excluding South Slavic names with solitary Đ/đ)
            strict_vi_chars = [c for c in artist_name if c in VI_STRICTLY_UNIQUE_CHARS]
            # If the only "strict" char is Đ/đ, ensure it's not a Slavic name like Đorđe, Đurić
            if set(strict_vi_chars).issubset({"đ", "Đ"}):
                # Require genuine Vietnamese structure or Vietnamese tone vowels
                has_vn_tone = any(c in "ăơưảạắằẳẵặấầẩẫậẻẽẹếềểễệỉĩịỏọốồổỗộớờởỡợủũụứừửữựỳỷỹỵ" for c in artist_name.lower())
                has_strict_vi = has_vn_tone
            else:
                has_strict_vi = bool(strict_vi_chars)

            has_generic_vi = any(c in VI_SPECIFIC_CHARS for c in artist_name)
            name_words = [w.lower() for w in re.findall(r"\w+", artist_name)]
            first_word = name_words[0] if name_words else ""
            second_word = name_words[1] if len(name_words) > 1 else ""

            is_valid_unaccented_name = False
            if len(name_words) in (2, 3, 4):
                if first_word in UNAMBIGUOUS_VN_SURNAMES:
                    is_valid_unaccented_name = True
                elif first_word in AMBIGUOUS_SURNAMES and second_word in VN_MIDDLE_NAMES:
                    is_valid_unaccented_name = True

            if has_strict_vi or (has_generic_vi and is_valid_unaccented_name):
                return {
                    "is_vietnamese_artist": True,
                    "confidence": 0.95 if has_strict_vi else 0.88,
                    "evidence": {
                        "field": "artist_name",
                        "value": artist_name,
                        "source": source,
                        "reason": "vietnamese_diacritics_in_name",
                    },
                }

            # Check if name contains "V-Pop" or specific artist tokens
            lower_name = artist_name.lower()
            if "v-pop" in lower_name or "vpop" in lower_name:
                return {
                    "is_vietnamese_artist": True,
                    "confidence": 0.88,
                    "evidence": {
                        "field": "artist_name",
                        "value": artist_name,
                        "source": source,
                        "reason": "vpop_in_artist_name",
                    },
                }

            if is_valid_unaccented_name:
                return {
                    "is_vietnamese_artist": True,
                    "confidence": 0.82,
                    "evidence": {
                        "field": "artist_name",
                        "value": artist_name,
                        "source": source,
                        "reason": "vietnamese_naming_pattern",
                    },
                }

        # 3. Check artist bio or description (High precision: require explicit heritage, ignore war/travel mentions)
        bio = str(metadata.get("artist_bio") or metadata.get("bio") or metadata.get("description") or "").strip()
        if bio:
            lower_bio = bio.lower()
            # Explicitly exclude historical/travel references
            is_war_or_travel = bool(re.search(r"\b(vietnam\s+war|war\s+in\s+vietnam|movies\s+about\s+vietnam|traveled\s+to\s+vietnam|traveling\s+in\s+vietnam)\b", lower_bio))
            if not is_war_or_travel:
                if re.search(r"\b(vietnamese\s+(?:singer|artist|musician|band|vocalist|composer|traditional|music|folk)|born\s+in\s+vietnam|from\s+vietnam|traditional\s+vietnamese)\b", lower_bio):
                    match_snippet = self._extract_snippet(bio, "vietnam")
                    return {
                        "is_vietnamese_artist": True,
                        "confidence": 0.92,
                        "evidence": {
                            "field": "artist_bio",
                            "value": match_snippet,
                            "source": source,
                            "reason": "explicit_vietnamese_heritage",
                        },
                    }

        return {
            "is_vietnamese_artist": False,
            "confidence": 0.0,
            "evidence": None,
        }

    def _extract_snippet(self, text: str, keyword: str, window: int = 50) -> str:
        idx = text.lower().find(keyword)
        if idx == -1:
            return text[:100]
        start = max(0, idx - window)
        end = min(len(text), idx + len(keyword) + window)
        snippet = text[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet
