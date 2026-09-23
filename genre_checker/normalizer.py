"""
Module chuẩn hóa chuỗi tiêu đề, nghệ sĩ, cache key và thể loại âm nhạc.
Bao gồm kiểm định tính hợp lệ của genre (validate_genre) và so sánh đối chiếu (compare_genre).
"""

import re
import unicodedata
from typing import Optional, Set
import pandas as pd

from config import INVALID_GENRE_LABELS, GENRE_SYNONYMS


def strip_accents_ascii_lower(text: str) -> str:
    """Chuyển chuỗi về chữ thường không dấu để so sánh đối chiếu mờ nếu cần."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.strip()


def normalize_title(title: Optional[str]) -> str:
    """
    Chuẩn hóa tiêu đề bài hát cho cache key và định danh:
    - Lowercase, strip whitespace, Unicode normalization NFC.
    - Loại bỏ số thứ tự track (01., 02 ), hậu tố MV/Official video, tag album.
    - TUYỆT ĐỐI GIỮ LẠI các thông tin phiên bản quan trọng:
      remix, live, cover, karaoke, sped up, slowed, nightcore, 8d, acoustic, instrumental, version...
    """
    if not title or pd.isna(title):
        return ""

    s = unicodedata.normalize("NFC", str(title)).lower().strip()

    # 1. Bỏ số thứ tự đầu bài hát (Ví dụ: "01. ", "07. ", "02 - ", "01 ") nhưng giữ các số là tên bài như "1 2 3 4", "12 Bến Nước"
    s = re.sub(r"^\s*(\d{1,3}[\.\-_\)]|0\d+\s+)\s*", "", s)

    # 2. Bỏ các hậu tố video/visualizer rác nhưng KHÔNG xóa version/remix
    s = re.sub(
        r"\s*(\|{1,2}|//|-)\s*(official\s*(music\s*)?video|official\s*lyrics(\s*video)?|"
        r"mv\s*official|official\s*audio|lyrics\s*video|audio\s*official|video\s*lyric|"
        r"video\s*official|official\s*mv|visualizer).*$",
        "",
        s,
    )

    # 3. Bỏ tag album dạng: | " 99% " the album
    s = re.sub(r'\|\s*["\'].*?["\']\s*the\s*album.*$', "", s)

    # 4. Bỏ các ngoặc vuông chỉ chứa tag video: [OFFICIAL MV], [Lyrics Video]
    s = re.sub(r"\[(official\s*(music\s*)?video|mv|lyrics|audio|mv\s*official)\]", "", s)

    # 5. Chuẩn hóa khoảng trắng
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_artist(artist: Optional[str]) -> str:
    """
    Chuẩn hóa tên nghệ sĩ cho cache key và entity matching:
    - Lowercase, strip whitespace, Unicode normalization NFC.
    - Loại bỏ hậu tố '- Topic', 'Official', alias '// ...'.
    - Loại bỏ @handle.
    """
    if not artist or pd.isna(artist):
        return ""

    s = unicodedata.normalize("NFC", str(artist)).lower().strip()

    # Bỏ hậu tố '- Topic' (kênh tự động YouTube)
    s = re.sub(r"\s*-\s*topic$", "", s)

    # Bỏ hậu tố 'Official'
    s = re.sub(r"\s+official$", "", s)

    # Nếu có dạng 'MCK // Nger' -> lấy nghệ sĩ chính đầu tiên
    if "//" in s:
        s = s.split("//")[0].strip()

    # Bỏ @handle
    s = re.sub(r"@\w+", "", s).strip()

    s = re.sub(r"\s+", " ", s).strip()
    return s


def make_cache_key(title: Optional[str], singer: Optional[str]) -> str:
    """
    Tạo cache key chuẩn:
    normalized_title + "||" + normalized_singer
    """
    return f"{normalize_title(title)}||{normalize_artist(singer)}"


def clean_for_search_query(title: Optional[str], artist: Optional[str]) -> tuple[str, str]:
    """
    Làm sạch thêm các phần phụ (như ft. / featuring) để tạo câu query tìm kiếm
    chính xác nhất trên các Search Engine / Music APIs.
    """
    t = normalize_title(title)
    a = normalize_artist(artist)

    # Bỏ (ft. ...), [feat. ...] trong title để tìm đúng tên bài hát gốc
    t_clean = re.sub(r"\s*[\(\[]\s*(ft|feat|featuring)\.?\s+.*?[\)\]]", "", t)
    t_clean = re.sub(r"\s+", " ", t_clean).strip()

    return t_clean, a


def validate_genre_label(label: str) -> bool:
    """Kiểm tra một nhãn genre đơn lẻ có hợp lệ hay không."""
    if not label:
        return False
    cleaned = label.lower().strip()
    if cleaned in INVALID_GENRE_LABELS:
        return False
    if len(cleaned) < 2:
        return False
    # Loại bỏ năm hoặc số (ví dụ: '2017', '1999', '2020s')
    if re.search(r"^\d{4}s?$", cleaned):
        return False
    # Loại bỏ nhãn dạng 'best of ...', 'top ...', 'album ...'
    if re.match(r"^(best of|top|album|year)\b", cleaned):
        return False
    # Phải chứa ít nhất 1 chữ cái
    if not re.search(r"[a-zà-ỹ]", cleaned):
        return False
    return True


def validate_genre(genre_str: Optional[str]) -> bool:
    """
    Kiểm tra chuỗi thể loại có hoàn toàn hợp lệ hay không:
    - Không được rỗng, None, null, unknown, n/a, khác...
    - Từng nhãn thể loại phân tách bởi '|' phải hợp lệ (không chứa nhãn địa lý như 'việt nam', 'âu mỹ'...)
    - Ví dụ: 'pop|khác' -> INVALID (False)
             'việt nam' -> INVALID (False)
             'pop|dance' -> VALID (True)
    """
    if not genre_str or pd.isna(genre_str):
        return False

    text = str(genre_str).strip().lower()
    if not text or text in INVALID_GENRE_LABELS:
        return False

    parts = [p.strip() for p in text.split("|") if p.strip()]
    if not parts:
        return False

    # Mọi nhãn con đều phải hợp lệ
    for p in parts:
        if not validate_genre_label(p):
            return False

    return True


def normalize_single_label(raw: str) -> str:
    """Chuẩn hóa một nhãn thể loại đơn lẻ qua từ điển đồng nghĩa."""
    cleaned = raw.lower().strip()
    cleaned = re.sub(r"^[\"\'\(\[\{]+|[\"\'\)\]\}]+$", "", cleaned).strip()

    if not validate_genre_label(cleaned):
        return ""

    if cleaned in GENRE_SYNONYMS:
        return GENRE_SYNONYMS[cleaned]

    if cleaned.endswith(" music"):
        cleaned = cleaned[:-6].strip()

    if cleaned in GENRE_SYNONYMS:
        return GENRE_SYNONYMS[cleaned]

    return cleaned


def normalize_genre(raw_genre: Optional[str]) -> str:
    """
    Chuẩn hóa chuỗi genre (có thể chứa nhiều genre ngăn cách bởi ',', ';', '/', '|').
    - Bảo vệ 'r&b' khỏi bị phân tách bởi dấu '&'.
    - Lọc bỏ triệt để các nhãn không hợp lệ (INVALID_GENRE_LABELS như 'việt nam', 'khác', 'music'...).
    - Chuẩn hóa các biến thể tương đương qua GENRE_SYNONYMS.
    - Nối các genre hợp lệ bằng dấu '|'.
    - Trả về rỗng nếu không có genre hợp lệ nào.
    """
    if not raw_genre or pd.isna(raw_genre):
        return ""

    text = unicodedata.normalize("NFC", str(raw_genre)).strip()
    if not text or text.lower() in INVALID_GENRE_LABELS:
        return ""

    # Bảo vệ R&B trước khi tách bằng dấu phân cách (đặc biệt là dấu &)
    text = re.sub(r"(?i)\br\s*&\s*b\b", "__RNB__", text)

    # Tách chuỗi theo các dấu phân cách phổ biến
    parts = re.split(r"[,;/\|\+&]+", text)

    valid_genres = []
    seen: Set[str] = set()

    for part in parts:
        part = part.replace("__RNB__", "r&b")
        norm = normalize_single_label(part)
        if norm and validate_genre_label(norm) and norm not in seen:
            seen.add(norm)
            valid_genres.append(norm)

    res = "|".join(valid_genres)
    # Xác thực lại toàn bộ chuỗi kết quả
    if validate_genre(res):
        return res
    return ""


def get_genre_tokens(genre_str: Optional[str]) -> Set[str]:
    """Phân rã chuỗi genre thành tập hợp các token chuẩn hóa để so sánh."""
    if not genre_str or pd.isna(genre_str):
        return set()

    normalized = normalize_genre(str(genre_str))
    if not normalized:
        return set()

    tokens = set()
    for item in normalized.split("|"):
        item = item.strip()
        if item:
            tokens.add(item)
            tokens.add(strip_accents_ascii_lower(item))
    return tokens


def compare_genre(original: Optional[str], searched: Optional[str]) -> str:
    """
    So sánh genre gốc và genre tìm được:
    - NOT_FOUND: nếu searched rỗng hoặc không hợp lệ
    - MISSING_ORIGINAL: nếu original rỗng/NaN nhưng searched hợp lệ
    - MATCH: nếu original và searched trùng khớp hoặc có giao nhau
    - DIFFERENT: nếu cả hai đều có giá trị nhưng khác nhau
    """
    if not searched or not validate_genre(searched):
        return "NOT_FOUND"

    searched_norm = normalize_genre(searched)
    if not searched_norm:
        return "NOT_FOUND"

    orig_norm = normalize_genre(original)
    if not orig_norm:
        return "MISSING_ORIGINAL"

    if orig_norm == searched_norm:
        return "MATCH"

    orig_tokens = get_genre_tokens(original)
    searched_tokens = get_genre_tokens(searched)

    if orig_tokens.intersection(searched_tokens):
        return "MATCH"

    return "DIFFERENT"
