"""
Module cấu hình chuẩn cho hệ thống Genre Checker.
Chứa các hằng số, đường dẫn mặc định, luật chuẩn hóa, controlled vocabulary,
danh sách nhãn genre không hợp lệ (INVALID) và danh sách kênh/uploader nhiễu.
"""

from pathlib import Path

# Thư mục gốc của project
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
OUTPUT_DIR = BASE_DIR / "output"

# Đảm bảo các thư mục cần thiết luôn tồn tại
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Đường dẫn file mặc định
DEFAULT_INPUT_CSV = r"C:\Users\ADmin\Downloads\missing_genre_research.csv"
DEFAULT_OUTPUT_CSV = r"C:\Users\ADmin\Downloads\missing_genre_research_checked.csv"
DEFAULT_CACHE_FILE = CACHE_DIR / "genre_cache.json"

# File báo cáo thống kê mặc định
REPORT_TXT_FILE = OUTPUT_DIR / "genre_check_report.txt"
DIFF_CSV_FILE = OUTPUT_DIR / "genre_differences.csv"
MISSING_CSV_FILE = OUTPUT_DIR / "genre_missing.csv"
AUDIT_CSV_FILE = OUTPUT_DIR / "cache_merge_audit.csv"

# Cấu hình mạng & Rate Limiting
REQUEST_DELAY = 1.1           # Mặc định MusicBrainz delay >= 1.0s
LASTFM_DELAY = 0.25           # Delay giữa các request Last.fm
WEB_SEARCH_DELAY = 0.5        # Delay giữa các request Web Search
TIMEOUT = 10                  # Thời gian chờ tối đa (giây)
MAX_RETRIES = 3               # Số lần retry khi gặp lỗi mạng/HTTP
BACKOFF_FACTOR = 2            # Hệ số exponential backoff: 2s, 4s, 8s

# User-Agent bắt buộc theo chính sách của MusicBrainz và để gọi Web Search an toàn
USER_AGENT = "Kido/2.0 (contact: tranviet200553)"

# DANH SÁCH NHÃN THỂ LOẠI HOÀN TOÀN KHÔNG HỢP LỆ (INVALID GENRE LABELS)
# Bất kỳ cache hoặc search result nào trả về các nhãn này đều bị coi là INVALID_GENRE,
# tuyệt đối không được chấp nhận làm genre của bài hát.
INVALID_GENRE_LABELS = {
    "", "unknown", "none", "null", "n/a", "na", "nan", "khác", "other", "test",
    # Tên quốc gia, khu vực địa lý KHÔNG PHẢI là thể loại âm nhạc
    "việt nam", "viet nam", "vietnam", "vietnamese",
    "âu mỹ", "au my", "asia", "asian", "korean", "japanese", "china", "chinese",
    "uk", "us", "usa", "britain", "british", "england", "english", "america", "american",
    "france", "french", "germany", "german", "japan", "korea",
    # Nghề nghiệp, vai trò, nhạc cụ
    "singer", "guitarist", "drummer", "pianist", "vocalist", "producer", "composer",
    "musician", "band", "artist", "male vocalists", "female vocalists", "male vocalist", "female vocalist",
    # Từ ngữ mô tả chung / Noise
    "music", "favorite", "favorites", "seen live", "love",
    "80s", "90s", "00s", "2000s", "2010s", "songs", "tracks", "track", "song",
    "chill", "relax", "awesome", "beautiful", "good", "nice", "lyrics",
    "masterpiece", "relaxing", "theme", "ost", "soundtrack", "music for soccer moms"
}

# TỪ ĐIỂN TÊN KÊNH / UPLOADER / PUBLISHER CẦN LỌC KHỎI NGHỆ SĨ (ENTITY RESOLUTION)
CHANNEL_NOISE_WORDS = {
    "official", "music", "entertainment", "records", "label", "channel",
    "vevo", "topic", "studio", "media", "tv", "pops", "yeah1", "sound",
    "audio", "video", "production", "network", "club", "karaoke"
}

# CONTROLLED GENRE VOCABULARY & SYNONYMS
GENRE_SYNONYMS = {
    # Hip Hop / Rap
    "hip hop": "hip hop",
    "hip-hop": "hip hop",
    "hiphop": "hip hop",
    "rap": "rap",
    "rap việt": "rap việt",
    "viet rap": "rap việt",
    "rap viet": "rap việt",
    "hip hop việt": "hip hop",
    "trap": "trap",
    "boom bap": "hip hop",

    # R&B / Soul
    "r&b": "r&b",
    "r & b": "r&b",
    "rnb": "r&b",
    "rhythm and blues": "r&b",
    "soul": "soul",
    "neo-soul": "soul",
    "contemporary r&b": "r&b",

    # Pop
    "pop": "pop",
    "pop music": "pop",
    "nhạc trẻ": "nhạc trẻ",
    "v-pop": "v-pop",
    "vpop": "v-pop",
    "k-pop": "k-pop",
    "kpop": "k-pop",
    "j-pop": "j-pop",
    "jpop": "j-pop",
    "c-pop": "c-pop",
    "dance-pop": "dance-pop",
    "synthpop": "synthpop",
    "synth-pop": "synthpop",
    "indie pop": "indie pop",

    # Electronic / Dance / EDM
    "electronic": "electronic",
    "electronic dance music": "edm",
    "edm": "edm",
    "dance": "dance",
    "house": "house",
    "electro": "electronic",
    "techno": "techno",
    "trance": "trance",
    "dubstep": "dubstep",
    "vinahouse": "vinahouse",
    "vina house": "vinahouse",
    "future bass": "future bass",
    "ambient": "ambient",

    # Rock / Metal / Punk
    "rock": "rock",
    "hard rock": "hard rock",
    "punk": "punk",
    "punk rock": "punk",
    "alternative rock": "alternative rock",
    "indie rock": "indie rock",
    "metal": "metal",
    "heavy metal": "metal",

    # Indie & Alternative
    "indie": "indie",
    "alternative": "alternative",

    # Ballad & Trữ Tình
    "ballad": "ballad",
    "pop ballad": "ballad",
    "nhạc ballad": "ballad",
    "nhạc trữ tình": "trữ tình",
    "trữ tình": "trữ tình",
    "bolero": "bolero",
    "nhạc vàng": "trữ tình",
    "nhạc quê hương": "dân ca",
    "nhạc dân ca": "dân ca",
    "dân ca": "dân ca",
    "nhạc đỏ": "nhạc đỏ",
    "nhạc cách mạng": "nhạc đỏ",

    # Acoustic / Folk / Country
    "acoustic": "acoustic",
    "folk": "folk",
    "folk pop": "folk",
    "country": "country",

    # Jazz / Blues
    "jazz": "jazz",
    "blues": "blues",
    "funk": "funk",

    # Classical & Instrumental
    "classical": "classical",
    "cổ điển": "classical",
    "instrumental": "instrumental",

    # Other
    "latin": "latin",
    "reggae": "reggae",
    "experimental": "experimental",
}

# TẬP HỢP TỪ KHÓA BẢN PHỐI / PHIÊN BẢN CẦN GIỮ LẠI (VERSION TOKENS)
VERSION_KEYWORDS = [
    "remix", "live", "cover", "karaoke", "sped up", "slowed",
    "nightcore", "8d", "acoustic", "instrumental", "demo", "edit",
    "extended", "version", "ver"
]
