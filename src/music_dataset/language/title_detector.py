"""Vietnamese Title Detector.

Analyzes song titles for Vietnamese linguistic evidence without assuming artist origin.
"""

import re
from typing import Any, Dict, List, Optional
from music_dataset.language.scoring import VI_SPECIFIC_CHARS, VI_STRICTLY_UNIQUE_CHARS, VI_STOPWORDS

VI_TITLE_KEYWORDS = {
    "bai", "bài", "tinh", "tình", "khuc", "khúc", "ca", "loi", "lời",
    "em", "anh", "que", "quê", "huong", "hương", "nho", "nhớ", "dem", "đêm",
    "ngay", "ngày", "mua", "mùa", "yeu", "yêu", "thuong", "thương",
    "buon", "buồn", "nang", "nắng", "mua", "mưa", "chieu", "chiều",
    "saigon", "sài gòn", "hanoi", "hà nội", "vietnam", "việt nam",
}


# Romance language markers that definitively distinguish Spanish, Portuguese, French from Vietnamese
ROMANCE_EXCLUSION_WORDS = {
    "los", "las", "del", "el", "contra", "sobre", "ojos", "abiertos", "luchar",
    "fazendo", "mim", "volveran", "para", "por", "uma", "não", "pão", "são",
    "avec", "dans", "pour", "sans", "est", "une", "des", "les",
}

VI_PHRASE_PATTERNS = [
    r"\banh\s+yeu\s+em\b", r"\bem\s+yeu\s+anh\b", r"\btinh\s+yeu\b", r"\bque\s+huong\b",
    r"\bnoi\s+nho\b", r"\bmua\s+xuan\b", r"\bduong\s+xua\b", r"\bchieu\s+mua\b",
    r"\bnguoi\s+ve\b", r"\bdem\s+nay\b", r"\bngay\s+mai\b", r"\bviet\s+nam\b",
    r"\bnhac\s+vang\b", r"\bnhac\s+do\b", r"\bca\s+khuc\b", r"\bduyen\s+phan\b"
]


class TitleDetector:
    """Detects whether a song title exhibits genuine Vietnamese linguistic cues with high precision."""

    def detect(self, title: Optional[str], source: str = "metadata") -> Dict[str, Any]:
        if not title or not title.strip():
            return {
                "is_vietnamese_title": False,
                "confidence": 0.0,
                "evidence": None,
            }

        title_str = title.strip()
        words = [w.lower() for w in re.findall(r"\w+", title_str)]

        # Exclude Romance language titles
        if any(w in ROMANCE_EXCLUSION_WORDS for w in words):
            return {
                "is_vietnamese_title": False,
                "confidence": 0.0,
                "evidence": None,
            }

        # 1. Check strictly unique Vietnamese diacritical characters
        strict_chars = [c for c in title_str if c in VI_STRICTLY_UNIQUE_CHARS]

        # Disambiguate Slavic Đ/đ: if strict_chars only contains đ/Đ, require at least 1 true VN tone vowel
        is_slavic_solitary_d = False
        if strict_chars and set(strict_chars).issubset({"đ", "Đ"}):
            has_vn_tone = any(c in "ăơưảạắằẳẵặấầẩẫậẻẽẹếềểễệỉĩịỏọốồổỗộớờởỡợủũụứừửữựỳỷỹỵ" for c in title_str.lower())
            if not has_vn_tone:
                is_slavic_solitary_d = True

        if strict_chars and not is_slavic_solitary_d:
            ratio = len(strict_chars) / max(1, len(title_str.replace(" ", "")))
            conf = min(0.98, 0.88 + ratio * 0.5)
            return {
                "is_vietnamese_title": True,
                "confidence": round(conf, 2),
                "evidence": {
                    "field": "title",
                    "value": title_str,
                    "source": source,
                    "reason": "vietnamese_diacritics",
                    "chars_matched": list(set(strict_chars)),
                },
            }

        # 2. Check for characteristic Vietnamese multi-word phrases (avoiding single word collisions)
        for pattern in VI_PHRASE_PATTERNS:
            if re.search(pattern, title_str, re.IGNORECASE):
                return {
                    "is_vietnamese_title": True,
                    "confidence": 0.90,
                    "evidence": {
                        "field": "title",
                        "value": title_str,
                        "source": source,
                        "reason": "vietnamese_phrase_match",
                        "pattern": pattern,
                    },
                }

        return {
            "is_vietnamese_title": False,
            "confidence": 0.0,
            "evidence": None,
        }
