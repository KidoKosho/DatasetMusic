"""Scoring functions for Vietnamese language heuristics and lexical patterns."""

import re
from typing import Dict, List, Set, Tuple

# Characters strictly unique to Vietnamese orthography (NOT present in Portuguese, Spanish, French, etc.)
# Excludes single ã/õ which are ubiquitous in Portuguese (São, Pão, Não, Canções).
# Includes Vietnamese compound tildes: ẵ, ẫ, ễ, ỗ, ỡ, ữ, ỹ which exist exclusively in Vietnamese.
VI_STRICTLY_UNIQUE_CHARS = set("đĐăĂơƠưƯảẢạẠắẮằẰẳẲẵẴặẶấẤầẦẩẨẫẪậẬẻẺẽẼẹẸếẾềỀểỂễỄệỆỉỈĩĨịỊỏỎọỌốỐồỒổỔỗỖộỘớỚờỜởỞỡỠợỢủỦũŨụỤứỨừỪửỬữỮựỰỷỶỹỸỵỴ")

# All Vietnamese diacritic characters (including single acute/grave/tilde vowels shared with Romance languages)
VI_SPECIFIC_CHARS = VI_STRICTLY_UNIQUE_CHARS | set("âÂêÊôÔáÁàÀéÉèÈíÍìÌóÓòÒúÚùÙýÝãÃõÕ")

# High-frequency Vietnamese function words / stopwords (single 'à' removed to avoid matching French 'à la')
VI_STOPWORDS: Set[str] = {
    "và", "của", "là", "có", "không", "người", "tôi", "em", "anh", "yêu",
    "trong", "một", "những", "với", "cho", "về", "được", "này", "khi",
    "đã", "sẽ", "nhưng", "như", "tình", "nhớ", "thương", "mưa", "đêm",
    "ngày", "đời", "tim", "hát", "lời", "mắt", "buồn", "mộng", "sầu",
    "môi", "tay", "lòng", "nơi", "sao", "trên", "dưới", "bao", "mùa",
    "hoa", "gió", "mây", "sống", "chết", "quê", "hương", "đất", "nước",
    "việt", "nam", "con", "mẹ", "cha", "bạn", "vui", "buồn", "xa", "gần",
    "đâu", "đến", "đi", "vào", "ra", "lại", "thấy", "biết", "muốn", "nghe",
    "nhau", "cùng", "mình", "ai", "thế", "còn", "nào", "đang", "thì", "mà",
    "rồi", "hay", "đây", "rất", "quá", "lắm", "ơi", "ạ", "nhé", "nhe",
    "hôm", "nay", "mai", "chiều", "sáng", "bóng", "mây", "nắng", "giọt",
    "bàn", "chân", "tiếng", "đàn", "khóc", "cười", "buông", "rơi", "bay",
}

# High-frequency unaccented Vietnamese syllables for non-diacritic detection
VI_UNACCENTED_SYLLABLES: Set[str] = {
    "va", "cua", "la", "co", "khong", "nguoi", "toi", "em", "anh", "yeu",
    "trong", "mot", "nhung", "voi", "cho", "ve", "duoc", "nay", "khi",
    "da", "se", "nhung", "nhu", "tinh", "nho", "thuong", "mua", "dem",
    "ngay", "doi", "tim", "hat", "loi", "mat", "buon", "mong", "sau",
    "moi", "tay", "long", "noi", "sao", "tren", "duoi", "bao", "mua",
    "hoa", "gio", "may", "song", "chet", "que", "huong", "dat", "nuoc",
    "viet", "nam", "con", "me", "cha", "ban", "vui", "xa", "gan",
    "dau", "den", "di", "vao", "ra", "lai", "thay", "biet", "muon", "nghe",
    "nhau", "cung", "minh", "ai", "the", "con", "nao", "dang", "thi", "ma",
    "roi", "hay", "day", "rat", "qua", "lam", "oi", "hom", "nay", "mai",
    "chieu", "sang", "bong", "nang", "giot", "ban", "chan", "tieng", "dan",
    "khoc", "cuoi", "buong", "roi", "bay", "thoi", "quen", "duong", "pho",
}

# Characteristic Vietnamese consonant clusters and initial/final phonemes
VI_NGRAM_PATTERNS = [
    re.compile(r"ngh[a-zà-ỹ]", re.IGNORECASE),
    re.compile(r"kh[a-zà-ỹ]", re.IGNORECASE),
    re.compile(r"th[a-zà-ỹ]", re.IGNORECASE),
    re.compile(r"tr[a-zà-ỹ]", re.IGNORECASE),
    re.compile(r"ch[a-zà-ỹ]", re.IGNORECASE),
    re.compile(r"nh[a-zà-ỹ]", re.IGNORECASE),
    re.compile(r"ph[a-zà-ỹ]", re.IGNORECASE),
    re.compile(r"gi[a-zà-ỹ]", re.IGNORECASE),
    re.compile(r"[a-zà-ỹ]ng\b", re.IGNORECASE),
    re.compile(r"[a-zà-ỹ]nh\b", re.IGNORECASE),
    re.compile(r"[a-zà-ỹ]ch\b", re.IGNORECASE),
    re.compile(r"(?:ươ|uô|iê|oă|uyê)", re.IGNORECASE),
]

# Bigrams characteristic of Vietnamese unaccented collocations
VI_UNACCENTED_BIGRAMS = {
    ("anh", "yeu"), ("yeu", "em"), ("em", "yeu"), ("anh", "oi"),
    ("nguoi", "yeu"), ("khong", "sao"), ("noi", "buon"), ("que", "huong"),
    ("tinh", "yeu"), ("mua", "roi"), ("dem", "nay"), ("loi", "ca"),
    ("trai", "tim"), ("mong", "mo"), ("ngay", "mai"), ("viet", "nam"),
    ("con", "duong"), ("doi", "mat"), ("nguoi", "oi"), ("biet", "bao"),
    ("trong", "dem"), ("mot", "ngay"), ("ve", "dau"), ("xa", "nhau"),
}


def compute_diacritic_metrics(text: str) -> Tuple[int, float]:
    """Return count of Vietnamese diacritic characters and ratio over total alphabetic characters."""
    alpha_chars = [c for c in text if c.isalpha()]
    total_alpha = len(alpha_chars)
    if total_alpha == 0:
        return 0, 0.0

    vi_chars = [c for c in alpha_chars if c in VI_SPECIFIC_CHARS]
    count = len(vi_chars)
    ratio = count / total_alpha
    return count, ratio


def compute_lexical_metrics(words: List[str]) -> Tuple[int, float, int, float]:
    """
    Return:
    - stopword_matches, stopword_ratio
    - unaccented_matches, unaccented_ratio
    """
    total_words = len(words)
    if total_words == 0:
        return 0, 0.0, 0, 0.0

    stopword_count = sum(1 for w in words if w in VI_STOPWORDS)
    stopword_ratio = stopword_count / total_words

    unaccented_count = sum(1 for w in words if w in VI_UNACCENTED_SYLLABLES)
    unaccented_ratio = unaccented_count / total_words

    return stopword_count, stopword_ratio, unaccented_count, unaccented_ratio


def compute_bigram_matches(words: List[str]) -> int:
    """Check how many characteristic Vietnamese unaccented bigrams appear."""
    if len(words) < 2:
        return 0
    count = 0
    for i in range(len(words) - 1):
        pair = (words[i], words[i + 1])
        if pair in VI_UNACCENTED_BIGRAMS:
            count += 1
    return count


def compute_ngram_pattern_score(text: str) -> float:
    """Compute score based on characteristic Vietnamese character combinations."""
    if not text:
        return 0.0
    matches = sum(len(p.findall(text)) for p in VI_NGRAM_PATTERNS)
    words = text.split()
    if not words:
        return 0.0
    # Average matches per 10 words
    return min(1.0, (matches / max(1, len(words))) * 1.5)
