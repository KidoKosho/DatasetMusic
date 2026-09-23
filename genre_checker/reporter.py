"""
Module tạo báo cáo thống kê và xuất các file đối chiếu theo đúng đặc tả Data Engineering:
- genre_check_report.txt: Thống kê chi tiết từng nguồn nhạc VN & Quốc tế.
- genre_differences.csv: Các bài hát có genre gốc khác genre tìm được.
- genre_missing.csv: Các bài hát genre gốc bị thiếu nhưng tìm được genre mới.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd

from config import REPORT_TXT_FILE, DIFF_CSV_FILE, MISSING_CSV_FILE

import threading
logger = logging.getLogger("GenreChecker.Reporter")


class GenreReporter:
    """Quản lý các chỉ số thống kê và xuất báo cáo kết quả (Thread-safe)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.stats: Dict[str, int] = {
            "total_rows": 0,
            "processed": 0,
            "from_cache": 0,
            "cache_miss": 0,
            # Nguồn API chính
            "lastfm": 0,
            "musicbrainz": 0,
            "apple_music": 0,
            "discogs": 0,
            # Nguồn Việt Nam
            "zingmp3": 0,
            "nhaccuatui": 0,
            "nhac_vn": 0,
            "chiasenhac": 0,
            "keeng": 0,
            # Nguồn Quốc tế & Bổ trợ
            "spotify": 0,
            "youtube": 0,
            "soundcloud": 0,
            "bandcamp": 0,
            "qobuz": 0,
            "allmusic": 0,
            "shazam": 0,
            # Nguồn Web chung
            "general_web": 0,
            # Trạng thái
            "not_found": 0,
            "errors": 0,
            "conflicts": 0,
            "invalid_cache": 0,
            "orphan_cache": 0,
            # So sánh với genre gốc
            "original_missing": 0,
            "different_genre": 0,
            "matched_genre": 0,
        }

    def record_row(
        self,
        source: str,
        status: str,
        is_cached: bool = False,
    ) -> None:
        """Cập nhật các bộ đếm sau khi xử lý mỗi dòng (Thread-safe)."""
        with self._lock:
            self.stats["processed"] += 1

        if is_cached:
            self.stats["from_cache"] += 1
        else:
            self.stats["cache_miss"] += 1

        src = (source or "").lower()
        if "lastfm" in src:
            self.stats["lastfm"] += 1
        if "musicbrainz" in src:
            self.stats["musicbrainz"] += 1
        if "apple_music" in src or "apple" in src:
            self.stats["apple_music"] += 1
        if "discogs" in src:
            self.stats["discogs"] += 1
        if "zingmp3" in src:
            self.stats["zingmp3"] += 1
        if "nhaccuatui" in src:
            self.stats["nhaccuatui"] += 1
        if "nhac_vn" in src or "nhac.vn" in src:
            self.stats["nhac_vn"] += 1
        if "chiasenhac" in src:
            self.stats["chiasenhac"] += 1
        if "keeng" in src:
            self.stats["keeng"] += 1
        if "spotify" in src:
            self.stats["spotify"] += 1
        if "youtube" in src:
            self.stats["youtube"] += 1
        if "soundcloud" in src:
            self.stats["soundcloud"] += 1
        if "bandcamp" in src:
            self.stats["bandcamp"] += 1
        if "qobuz" in src:
            self.stats["qobuz"] += 1
        if "allmusic" in src:
            self.stats["allmusic"] += 1
        if "shazam" in src:
            self.stats["shazam"] += 1
        if "web_search" in src and not any(p in src for p in ["zing", "nhaccuatui", "apple", "discogs", "qobuz", "allmusic", "shazam"]):
            self.stats["general_web"] += 1

        # Trạng thái so sánh
        if status == "ERROR":
            self.stats["errors"] += 1
        elif status == "CONFLICT":
            self.stats["conflicts"] += 1
        elif status == "NOT_FOUND":
            self.stats["not_found"] += 1
        elif status == "MISSING_ORIGINAL":
            self.stats["original_missing"] += 1
        elif status == "DIFFERENT":
            self.stats["different_genre"] += 1
        elif status == "MATCH":
            self.stats["matched_genre"] += 1

    def generate_report_text(self) -> str:
        """Tạo chuỗi văn bản báo cáo theo định dạng yêu cầu."""
        s = self.stats
        report = (
            "==============================\n"
            "GENRE SEARCH REPORT\n"
            "==============================\n\n"
            f"Total rows:        {s['total_rows']}\n"
            f"Processed:         {s['processed']}\n"
            f"From cache:        {s['from_cache']}\n"
            f"Cache miss:        {s['cache_miss']}\n\n"
            f"Last.fm:           {s['lastfm']}\n"
            f"Apple Music:       {s['apple_music']}\n"
            f"Discogs:           {s['discogs']}\n"
            f"MusicBrainz:       {s['musicbrainz']}\n\n"
            f"Zing MP3:          {s['zingmp3']}\n"
            f"NhacCuaTui:        {s['nhaccuatui']}\n"
            f"Nhac.vn:           {s['nhac_vn']}\n"
            f"Chiasenhac:        {s['chiasenhac']}\n"
            f"Keeng:             {s['keeng']}\n\n"
            f"Spotify:           {s['spotify']}\n"
            f"YouTube:           {s['youtube']}\n"
            f"SoundCloud:        {s['soundcloud']}\n"
            f"Bandcamp:          {s['bandcamp']}\n"
            f"Qobuz:             {s['qobuz']}\n"
            f"AllMusic:          {s['allmusic']}\n"
            f"Shazam:            {s['shazam']}\n\n"
            f"General Web:       {s['general_web']}\n\n"
            f"Not found:         {s['not_found']}\n"
            f"Errors:            {s['errors']}\n"
            f"Conflicts:         {s['conflicts']}\n"
            f"Invalid cache:     {s['invalid_cache']}\n"
            f"Orphan cache:      {s['orphan_cache']}\n\n"
            f"Original genre missing: {s['original_missing']}\n"
            f"Different genre:        {s['different_genre']}\n"
            f"Matched genre:          {s['matched_genre']}\n"
            "=============================="
        )
        return report

    def save_reports(
        self,
        df_result: pd.DataFrame,
        report_txt_path: Optional[Path | str] = None,
        diff_csv_path: Optional[Path | str] = None,
        missing_csv_path: Optional[Path | str] = None,
    ) -> None:
        """Ghi báo cáo ra file text và xuất các file CSV phụ trợ."""
        txt_path = Path(report_txt_path or REPORT_TXT_FILE)
        diff_path = Path(diff_csv_path or DIFF_CSV_FILE)
        miss_path = Path(missing_csv_path or MISSING_CSV_FILE)

        try:
            txt_path.parent.mkdir(parents=True, exist_ok=True)
            report_text = self.generate_report_text()
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(report_text + "\n")
            logger.info("Đã lưu báo cáo thống kê tại: %s", txt_path)
        except Exception as e:
            logger.error("Lỗi khi ghi report.txt: %s", e)

        # Xuất genre_differences.csv
        try:
            diff_df = df_result[df_result["genre_status"] == "DIFFERENT"]
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            diff_df.to_csv(diff_path, index=False, encoding="utf-8-sig")
            logger.info("Đã xuất %d dòng khác biệt thể loại tại: %s", len(diff_df), diff_path)
        except Exception as e:
            logger.error("Lỗi khi xuất genre_differences.csv: %s", e)

        # Xuất genre_missing.csv
        try:
            missing_df = df_result[df_result["genre_status"] == "MISSING_ORIGINAL"]
            miss_path.parent.mkdir(parents=True, exist_ok=True)
            missing_df.to_csv(miss_path, index=False, encoding="utf-8-sig")
            logger.info("Đã xuất %d dòng bổ sung thể loại thiếu tại: %s", len(missing_df), miss_path)
        except Exception as e:
            logger.error("Lỗi khi xuất genre_missing.csv: %s", e)
