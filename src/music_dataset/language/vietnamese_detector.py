"""Ensemble Vietnamese language detector for music lyrics."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from music_dataset.constants import LanguageDetectionMethod, LanguageStatus
from music_dataset.language.normalization import normalize_unicode, tokenize_words
from music_dataset.language.scoring import (
    compute_bigram_matches,
    compute_diacritic_metrics,
    compute_lexical_metrics,
    compute_ngram_pattern_score,
)


@dataclass
class VietnameseDetectionResult:
    language: str
    confidence: float
    status: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    method: str = LanguageDetectionMethod.ENSEMBLE.value


class VietnameseDetector:
    def __init__(self, threshold: float = 0.75):
        self.threshold = threshold

    def detect(self, lyrics: Optional[str]) -> VietnameseDetectionResult:
        """
        Analyze lyrics text and return VietnameseDetectionResult.
        Does NOT rely solely on diacritics (handles unaccented lyrics, slang, English mixing).
        """
        if not lyrics or not lyrics.strip():
            return VietnameseDetectionResult(
                language="unknown",
                confidence=0.0,
                status=LanguageStatus.UNKNOWN.value,
                evidence={"reason": "empty_or_null_lyrics"},
                method=LanguageDetectionMethod.NOT_CHECKED.value,
            )

        text = normalize_unicode(lyrics)
        words = tokenize_words(text)
        alpha_chars = [c for c in text if c.isalpha()]

        if len(alpha_chars) < 10 or len(words) < 3:
            return VietnameseDetectionResult(
                language="unknown",
                confidence=0.0,
                status=LanguageStatus.UNKNOWN.value,
                evidence={
                    "reason": "text_too_short",
                    "alpha_length": len(alpha_chars),
                    "word_count": len(words),
                },
                method=LanguageDetectionMethod.ENSEMBLE.value,
            )

        diacritic_count, diacritic_ratio = compute_diacritic_metrics(text)
        (
            stopword_count,
            stopword_ratio,
            unaccented_count,
            unaccented_ratio,
        ) = compute_lexical_metrics(words)
        bigram_matches = compute_bigram_matches(words)
        ngram_score = compute_ngram_pattern_score(text)

        evidence = {
            "total_words": len(words),
            "total_alpha": len(alpha_chars),
            "diacritic_count": diacritic_count,
            "diacritic_ratio": round(diacritic_ratio, 4),
            "stopword_count": stopword_count,
            "stopword_ratio": round(stopword_ratio, 4),
            "unaccented_count": unaccented_count,
            "unaccented_ratio": round(unaccented_ratio, 4),
            "bigram_matches": bigram_matches,
            "ngram_score": round(ngram_score, 4),
        }

        # Case A: Strong diacritic evidence
        if diacritic_count >= 5 and diacritic_ratio >= 0.02:
            confidence = min(
                1.0,
                0.55 + (diacritic_ratio * 3.0) + (stopword_ratio * 0.4) + (ngram_score * 0.1)
            )
            evidence["detected_feature"] = "accented_vietnamese"
            return VietnameseDetectionResult(
                language="vi",
                confidence=round(confidence, 4),
                status=LanguageStatus.DETECTED_VI.value,
                evidence=evidence,
            )

        # Case B: Light diacritics + strong lexical matches
        if diacritic_count >= 1 and (stopword_count >= 3 or stopword_ratio >= 0.08):
            confidence = min(
                0.95,
                0.50 + (stopword_ratio * 0.5) + (diacritic_ratio * 2.0)
            )
            evidence["detected_feature"] = "mixed_diacritics_lexical"
            return VietnameseDetectionResult(
                language="vi",
                confidence=round(confidence, 4),
                status=LanguageStatus.DETECTED_VI.value if confidence >= self.threshold else LanguageStatus.UNKNOWN.value,
                evidence=evidence,
            )

        # Case C: Unaccented Vietnamese (tiếng Việt không dấu)
        # Check high proportion of unaccented Vietnamese syllables and characteristic bigrams
        if unaccented_ratio >= 0.35 or (unaccented_ratio >= 0.20 and bigram_matches >= 1):
            confidence = min(
                0.90,
                0.40 + (unaccented_ratio * 0.6) + (bigram_matches * 0.08)
            )
            evidence["detected_feature"] = "unaccented_vietnamese"
            status = LanguageStatus.DETECTED_VI.value if confidence >= self.threshold else LanguageStatus.UNKNOWN.value
            return VietnameseDetectionResult(
                language="vi" if status == LanguageStatus.DETECTED_VI.value else "unknown",
                confidence=round(confidence, 4),
                status=status,
                evidence=evidence,
            )

        # Case D: Non-Vietnamese lyrics (English, Spanish, etc.)
        evidence["detected_feature"] = "non_vietnamese_lyrics"
        return VietnameseDetectionResult(
            language="non_vi",
            confidence=0.05,
            status=LanguageStatus.DETECTED_NON_VI.value,
            evidence=evidence,
        )
