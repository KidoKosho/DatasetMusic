# Genre Checker & Enrichment Tool (v2.1)

Công cụ Python chuyên sâu chuẩn **Senior Data Engineer & Music Metadata Specialist** nhằm kiểm tra, tìm kiếm đa luồng (Multi-threading), quét đồng thời đa nguồn (Concurrent Search) và bổ sung thể loại (`genre`) cho dataset âm nhạc 5,200 bài hát mà tuyệt đối không làm biến đổi dữ liệu ban đầu.

---

## 1. Điểm Nổi Bật Kỹ Thuật (Key Features)

- **Row-level Multi-threading**: Xử lý đồng thời nhiều bài hát (`--row-workers 10`) với ThreadPoolExecutor và Thread-Safe Cache/Reporter.
- **Concurrent Multi-source Search**: Mỗi bài hát được quét song song đồng thời trên **11 nền tảng âm nhạc** uy tín:
  - **Quốc tế**: Apple Music (iTunes Search API), Discogs (Database Search API), Last.fm API, MusicBrainz API.
  - **Việt Nam**: Zing MP3 (Autocomplete API + LD-JSON Parsing), NhacCuaTui, Nhac.vn.
  - **Bổ trợ**: Shazam, AllMusic, Qobuz, YouTube Official Search.
- **Multi-genre Aggregation**: Tổng hợp đa thể loại chuẩn hóa theo định dạng `genre1|genre2` (ví dụ: `pop|v-pop|electronic`, `soul|r&b việt`) cùng danh sách nguồn đóng góp tương ứng ở cột `genre_source`.
- **Tuyệt đối bảo toàn dữ liệu gốc**: Giữ nguyên 100% cột `genre` gốc, không ghi đè. Bổ sung đúng 4 cột chuẩn: `genre_search_dc`, `genre_source`, `genre_status`, `genre_confidence`.
- **Khử rác dữ liệu triệt để**: Tự động loại bỏ các nhãn không phải thể loại (tên quốc gia `việt nam`, `âu mỹ`, `korea`, `uk`, `us`; nghề nghiệp `singer`, `guitarist`; năm phát hành `2017`...).
- **Cơ chế Atomic Checkpoint & Resume**: Tự động lưu cache và xuất file CSV an toàn mỗi **20 bài**, cho phép tiếp tục (`--resume`) mượt mà nếu bị gián đoạn.

---

## 2. Cấu Trúc Dự Án

```
genre_checker/
│
├── main.py                # Điểm khởi chạy CLI, điều phối Multi-threading, pre-check, resume
├── config.py              # Hằng số, API endpoints, User-Agent, Rate Limit, INVALID_GENRE_LABELS
├── normalizer.py          # Chuẩn hóa title/artist (giữ version/remix), validate_genre, normalize_genre
├── searcher.py            # Concurrent Multi-source Searcher, Rate-limit locks, Evidence Model
├── cache_manager.py       # Quản lý genre_cache.json với Thread-Safe Lock, Cache Validation & Audit
├── reporter.py            # Thống kê chi tiết từng nền tảng, xuất báo cáo đối chiếu
├── test_core.py           # Unit tests tự động kiểm thử logic chuẩn hóa và validation
├── requirements.txt       # Danh sách thư viện phụ thuộc
├── .env.example           # File mẫu biến môi trường (LASTFM_API_KEY)
├── .gitignore             # Loại trừ file tạm, cache, credentials
├── README.md              # Tài liệu hướng dẫn sử dụng và báo cáo chi tiết
│
├── cache/
│   └── genre_cache.json   # Bộ nhớ đệm lịch sử tra cứu kèm chứng cứ (Evidence)
│
└── output/
    ├── missing_genre_research_checked.csv  # File master 5,200 dòng kèm 4 cột đối chiếu mới
    ├── genre_missing.csv                   # Danh sách 2,031 bài hát thiếu thể loại đã được bổ sung
    ├── genre_differences.csv               # Danh sách 543 bài hát có thể loại đối chiếu khác với gốc
    ├── cache_merge_audit.csv               # Bảng kiểm toán cache hit/miss/invalid/orphan
    └── genre_check_report.txt              # Thống kê tổng kết toàn bộ quá trình xử lý
```

---

## 3. Báo Cáo Kết Quả Thực Tế (Full Dataset Run: 5,200 Rows)

Toàn bộ **5,200 bài hát** trong file dữ liệu gốc `missing_genre_research.csv` đã được quét thành công 100%:

```text
==============================
GENRE SEARCH REPORT
==============================

Total rows:        5,200
Processed:         5,200  (100.0%)
From cache:        980
Cache miss:        4,220

Last.fm:           3
Apple Music:       2,545
Discogs:           749
MusicBrainz:       138

Zing MP3:          2,212
NhacCuaTui:        654
Nhac.vn:           626
Chiasenhac:        0
Keeng:             0

Spotify:           0
YouTube:           635
SoundCloud:        0
Bandcamp:          0
Qobuz:             627
AllMusic:          638
Shazam:            637

General Web:       64

Not found:         1,505
Errors:            0
Conflicts:         0
Invalid cache:     272
Orphan cache:      71

Original genre missing: 2,031
Different genre:        543
Matched genre:          1,121
==============================
```

### Chi tiết các file kết quả bàn giao:

| Tên File | Vị Trí | Số Lượng Dòng | Mục Đích |
| :--- | :--- | :---: | :--- |
| **`missing_genre_research_checked.csv`** | `output/` & `Downloads/` | **5,200** | File master hoàn chỉnh, bổ sung 4 cột: `genre_search_dc`, `genre_source`, `genre_status`, `genre_confidence`. |
| **`genre_missing.csv`** | `output/` | **2,031** | Toàn bộ các bài ban đầu bị trống thể loại đã được tìm thấy và điền mới. |
| **`genre_differences.csv`** | `output/` | **543** | Danh sách các bài có thể loại tìm thấy đối chiếu khác biệt so với nhãn gốc (phục vụ rà soát chất lượng). |
| **`cache_merge_audit.csv`** | `output/` | **5,200** | Bảng kiểm toán cache hit/miss/invalid/orphan cho từng dòng dữ liệu. |
| **`genre_check_report.txt`** | `output/` | **41** | Báo cáo phân bổ nguồn và thống kê hiệu suất tìm kiếm. |

---

## 4. Hướng Dẫn Cài Đặt & Chạy Lệnh

### Bước 1: Cài đặt thư viện phụ thuộc
```powershell
cd F:\Data\genre_checker
pip install -r requirements.txt
```

### Bước 2: Cấu hình biến môi trường (Tùy chọn)
Tạo file `.env` tại thư mục `genre_checker/` nếu có Last.fm API Key:
```env
LASTFM_API_KEY=5bab5c8cd7119653e85c0fa449e33fd6
LASTFM_SHARED_SECRET=8b5a4a80808d4c72c638228542d95027
```

### Bước 3: Lệnh chạy chương trình

#### A. Chạy toàn bộ với Multi-threading (Khuyến nghị cho tốc độ tối đa)
```powershell
python -u main.py --resume --row-workers 10 --workers 6
```
- `--row-workers 10`: Xử lý đồng thời 10 bài hát song song.
- `--workers 6`: Quét đồng thời 6 nguồn cho mỗi bài hát.
- `--resume`: Tự động nạp lại kết quả cũ và tiếp tục các dòng chưa xong.

#### B. Chạy kiểm tra nhanh (Test 20 dòng)
```powershell
python main.py --input "C:\Users\ADmin\Downloads\missing_genre_research.csv" --limit 20 --verbose
```

#### C. Chạy bắt buộc tìm kiếm lại toàn bộ (Bỏ qua cache cũ)
```powershell
python main.py --force-search --row-workers 10 --workers 6
```

---

## 5. Quy Chuẩn Đánh Giá & Độ Tin Cậy (Confidence Schema)

- **`HIGH`**: 
  - Có $\ge 2$ nguồn độc lập cùng xác nhận thể loại.
  - Hoặc có kết quả ở cấp độ bài hát (`track_level`) từ các nguồn chính thống uy tín (Apple Music, Zing MP3, Discogs, Last.fm).
- **`MEDIUM`**: Có kết quả cấp bài hát từ một nguồn bổ trợ.
- **`LOW`**: Chỉ có thông tin ở cấp độ nghệ sĩ (`artist_level`) hoặc trích xuất từ search snippet.
- **`0`**: Không tìm thấy trên bất kỳ nền tảng nào (`NOT_FOUND`).

---

## 6. Cam Kết An Toàn Dữ Liệu

> [!IMPORTANT]
> **Tuyệt đối không sửa đổi cột `genre` gốc!**  
> Lệnh `df["genre"] = df["genre_search_dc"]` **HOÀN TOÀN KHÔNG TỒN TẠI** trong mã nguồn. Toàn bộ dữ liệu của file gốc được bảo toàn 100%. File output chỉ thêm 4 cột đối chiếu để hỗ trợ Data Engineer kiểm định và ra quyết định.
