"""Tests for Vietnamese lyrics detection engine."""

from music_dataset.constants import LanguageStatus
from music_dataset.language.vietnamese_detector import VietnameseDetector


def test_vietnamese_lyrics_with_diacritics():
    detector = VietnameseDetector(threshold=0.75)
    lyrics = """
    [00:15.20] Mưa vẫn mưa bay trên tầng tháp cổ
    [00:20.10] Dài tay em mấy thuở mắt xanh xao
    [00:25.40] Nghe lá thu mưa reo mòn gót nhỏ
    [00:30.00] Đường dài hun hút cho mắt thêm sâu
    """
    res = detector.detect(lyrics)

    assert res.language == "vi"
    assert res.status == LanguageStatus.DETECTED_VI.value
    assert res.confidence >= 0.85
    assert res.evidence["diacritic_count"] > 10


def test_vietnamese_lyrics_unaccented():
    detector = VietnameseDetector(threshold=0.70)
    # Unaccented Vietnamese song lyrics
    lyrics = "anh yeu em nguoi oi biet bao dem nay que huong xa xoi con duong mua roi"
    res = detector.detect(lyrics)

    assert res.language == "vi"
    assert res.status == LanguageStatus.DETECTED_VI.value
    assert res.confidence >= 0.70


def test_english_lyrics():
    detector = VietnameseDetector()
    lyrics = """
    Yesterday, all my troubles seemed so far away
    Now it looks as though they're here to stay
    Oh, I believe in yesterday
    Suddenly, I'm not half the man I used to be
    There's a shadow hanging over me
    """
    res = detector.detect(lyrics)

    assert res.language == "non_vi"
    assert res.status == LanguageStatus.DETECTED_NON_VI.value
    assert res.confidence < 0.20


def test_empty_or_short_lyrics():
    detector = VietnameseDetector()
    res_empty = detector.detect("")
    assert res_empty.status == LanguageStatus.UNKNOWN.value

    res_short = detector.detect("la la la")
    assert res_short.status == LanguageStatus.UNKNOWN.value
