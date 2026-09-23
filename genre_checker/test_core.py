"""
Bộ kiểm thử toàn diện cho các thành phần cốt lõi của genre_checker (v2.0):
- normalize_title (giữ lại remix, live, cover, sped up...)
- normalize_artist
- normalize_genre & validate_genre (loại bỏ nhãn rác 'việt nam', 'khác'...)
- is_valid_cache_entry
- compare_genre
"""

import unittest
from normalizer import (
    normalize_title,
    normalize_artist,
    make_cache_key,
    normalize_genre,
    validate_genre,
    compare_genre,
)
from cache_manager import is_valid_cache_entry


class TestGenreCheckerV2(unittest.TestCase):
    def test_normalize_title_preserves_version(self):
        # Giữ lại remix
        t1 = "05 (Không Phai) (Masew Remix)"
        self.assertIn("remix", normalize_title(t1))
        self.assertFalse(normalize_title(t1).startswith("05"))

        # Giữ lại live, cover, acoustic
        self.assertIn("live", normalize_title("Chờ đợi có đáng sợ (Live) - Andiez"))
        self.assertIn("acoustic", normalize_title("Một Cú Lừa (Acoustic Version) | Bích Phương"))

        # Xóa hậu tố video rác
        t2 = "01. BINZ - HỜN LÃ SA VÀO (ft. TRIPLE D) | OFFICIAL LYRICS VIDEO"
        norm2 = normalize_title(t2)
        self.assertNotIn("official lyrics video", norm2)

    def test_normalize_artist(self):
        self.assertEqual(normalize_artist("MCK // Nger"), "mck")
        self.assertEqual(normalize_artist("Sơn Tùng M-TP - Topic"), "sơn tùng m-tp")
        self.assertEqual(normalize_artist("Binz Da Poet Official"), "binz da poet")

    def test_validate_genre(self):
        # Hợp lệ
        self.assertTrue(validate_genre("pop"))
        self.assertTrue(validate_genre("pop|dance"))
        self.assertTrue(validate_genre("rap việt"))
        self.assertTrue(validate_genre("r&b"))
        self.assertTrue(validate_genre("trữ tình"))

        # KHÔNG hợp lệ (INVALID)
        self.assertFalse(validate_genre(""))
        self.assertFalse(validate_genre(None))
        self.assertFalse(validate_genre("việt nam"))
        self.assertFalse(validate_genre("vietnam"))
        self.assertFalse(validate_genre("âu mỹ"))
        self.assertFalse(validate_genre("khác"))
        self.assertFalse(validate_genre("unknown"))
        self.assertFalse(validate_genre("pop|khác"))
        self.assertFalse(validate_genre("rock|việt nam"))

    def test_normalize_genre_filters_invalid_labels(self):
        # 'Việt Nam, Rap Việt' -> chỉ lấy 'rap việt'
        self.assertEqual(normalize_genre("Việt Nam, Rap Việt"), "rap việt")

        # 'Việt Nam' đơn lẻ -> trả về rỗng vì không phải thể loại
        self.assertEqual(normalize_genre("Việt Nam"), "")
        self.assertEqual(normalize_genre("Âu Mỹ"), "")

        # R&B bảo vệ không bị tách
        self.assertEqual(normalize_genre("R&B"), "r&b")
        self.assertEqual(normalize_genre("Hip-Hop, R&B"), "hip hop|r&b")

        # Chuẩn hóa đồng nghĩa
        self.assertEqual(normalize_genre("Electronic Dance Music"), "edm")
        self.assertEqual(normalize_genre("Pop Music"), "pop")

    def test_is_valid_cache_entry(self):
        # Valid entry
        valid_entry = {
            "genre": "pop",
            "source": "zingmp3",
            "status": "FOUND",
            "confidence": "HIGH",
        }
        self.assertTrue(is_valid_cache_entry(valid_entry))

        # Invalid entry do genre rác 'việt nam'
        invalid_genre_entry = {
            "genre": "việt nam",
            "source": "web_search",
            "status": "MISSING_ORIGINAL",
            "confidence": "MEDIUM",
        }
        self.assertFalse(is_valid_cache_entry(invalid_genre_entry))

        # Invalid entry do status NOT_FOUND
        not_found_entry = {
            "genre": "",
            "source": "",
            "status": "NOT_FOUND",
            "confidence": "0",
        }
        self.assertFalse(is_valid_cache_entry(not_found_entry))

        # Invalid entry do confidence LOW
        low_entry = {
            "genre": "pop",
            "source": "web_search",
            "status": "FOUND",
            "confidence": "LOW",
        }
        self.assertFalse(is_valid_cache_entry(low_entry))

    def test_compare_genre(self):
        self.assertEqual(compare_genre(None, "pop"), "MISSING_ORIGINAL")
        self.assertEqual(compare_genre("pop", None), "NOT_FOUND")
        self.assertEqual(compare_genre("Pop", "pop"), "MATCH")
        self.assertEqual(compare_genre("pop", "pop|dance"), "MATCH")
        self.assertEqual(compare_genre("rock", "pop"), "DIFFERENT")


if __name__ == "__main__":
    unittest.main()
