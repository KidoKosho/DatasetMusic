"""
Module quản lý Cache theo chuẩn kiến trúc Data Engineering:
- Schema giàu chứng cứ (Rich Evidence Model).
- Kiểm tra tính hợp lệ chặt chẽ của cache (Cache Validation).
- Báo cáo kiểm toán cache đối chiếu với Master CSV (Cache Audit).
- Ghi đĩa nguyên tử (Atomic Save) chống lỗi hỏng dữ liệu JSON.
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd

from config import DEFAULT_CACHE_FILE, AUDIT_CSV_FILE
from normalizer import make_cache_key, validate_genre, normalize_genre

logger = logging.getLogger("GenreChecker.Cache")


def is_valid_cache_entry(entry: Optional[Dict[str, Any]]) -> bool:
    """
    Kiểm tra một bản ghi cache có hợp lệ và đáng tin cậy để tái sử dụng hay không:
    - Phải có genre hợp lệ (validate_genre trả về True).
    - Status không được là NOT_FOUND, ERROR, CONFLICT, INVALID_GENRE.
    - Confidence không được là 0 hoặc LOW.
    - Không chứa các nhãn rác như 'việt nam', 'khác', 'unknown'...
    Nếu không thỏa mãn, cache entry bị coi là INVALID CACHE -> cần RECHECK / SEARCH.
    """
    if not entry or not isinstance(entry, dict):
        return False

    status = str(entry.get("status", "")).upper()
    if status in {"NOT_FOUND", "ERROR", "CONFLICT", "INVALID_GENRE", ""}:
        return False

    confidence = str(entry.get("confidence", "")).upper()
    if confidence in {"0", "LOW", ""}:
        return False

    genre = entry.get("genre", "")
    if not validate_genre(genre):
        return False

    return True


class GenreCache:
    """Quản lý bộ nhớ đệm kết quả tìm kiếm genre kèm bằng chứng và cơ chế kiểm toán (Thread-safe)."""

    def __init__(self, cache_file: Path | str = DEFAULT_CACHE_FILE):
        self.cache_path = Path(cache_file)
        self.cache_data: Dict[str, Dict[str, Any]] = {}
        self._dirty = False
        self._lock = threading.Lock()
        self.load()

    def load(self) -> None:
        """Nạp dữ liệu cache từ file JSON."""
        with self._lock:
            if not self.cache_path.exists():
                logger.info("Chưa có file cache tại %s, khởi tạo cache mới.", self.cache_path)
                self.cache_data = {}
                return

            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self.cache_data = json.load(f)
                logger.info("Đã nạp thành công %d bản ghi từ cache.", len(self.cache_data))
            except Exception as e:
                logger.warning("Lỗi đọc file cache %s (%s). Khởi tạo cache trống.", self.cache_path, e)
                self.cache_data = {}

    def get(self, title: Optional[str], singer: Optional[str]) -> Optional[Dict[str, Any]]:
        """Lấy bản ghi cache theo title và singer (Thread-safe)."""
        key = make_cache_key(title, singer)
        with self._lock:
            val = self.cache_data.get(key)
            return val.copy() if isinstance(val, dict) else val

    def set(
        self,
        title: Optional[str],
        singer: Optional[str],
        genre: str,
        source: str,
        status: str,
        confidence: str,
        evidence: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Lưu kết quả tra cứu vào cache theo schema chuẩn v2.0 có evidence (Thread-safe).
        """
        key = make_cache_key(title, singer)
        norm_genre = normalize_genre(genre) if validate_genre(genre) else ""

        with self._lock:
            self.cache_data[key] = {
                "genre": norm_genre,
                "source": source or "",
                "status": status or ("FOUND" if norm_genre else "NOT_FOUND"),
                "confidence": confidence or "0",
                "evidence": evidence or [],
                "cache_version": "2.0",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._dirty = True

    def save(self, force: bool = False) -> None:
        """Ghi đĩa an toàn (Atomic Save) qua file tạm (Thread-safe)."""
        with self._lock:
            if not force and not self._dirty:
                return

            try:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                temp_file = self.cache_path.with_suffix(".tmp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(self.cache_data, f, ensure_ascii=False, indent=2)
                os.replace(temp_file, self.cache_path)
                self._dirty = False
            except Exception as e:
                logger.error("Lỗi khi lưu cache ra đĩa: %s", e)

    def audit(
        self,
        df: pd.DataFrame,
        title_col: str,
        singer_col: str,
        audit_csv_path: Optional[Path | str] = None,
    ) -> Tuple[Dict[str, int], pd.DataFrame]:
        """
        Thực hiện kiểm toán Cache đối chiếu với Master CSV:
        - So sánh toàn bộ dòng CSV với Cache.
        - Phát hiện Cache Hit, Cache Miss, Valid Cache, Invalid Cache.
        - Phát hiện Orphan Cache (các bản ghi chỉ có trong JSON nhưng không có trong CSV).
        - Xuất file output/cache_merge_audit.csv.
        """
        csv_total = len(df)
        cache_total = len(self.cache_data)

        csv_keys_seen = set()
        audit_rows = []

        cache_hit_count = 0
        cache_miss_count = 0
        valid_cache_count = 0
        invalid_cache_count = 0
        not_found_count = 0
        error_count = 0
        low_count = 0

        for idx, row in df.iterrows():
            title = str(row[title_col]) if pd.notna(row[title_col]) else ""
            singer = str(row[singer_col]) if pd.notna(row[singer_col]) else ""
            key = make_cache_key(title, singer)
            csv_keys_seen.add(key)

            entry = self.cache_data.get(key)
            if entry is not None:
                cache_hit_count += 1
                c_status = str(entry.get("status", ""))
                c_genre = str(entry.get("genre", ""))
                c_conf = str(entry.get("confidence", ""))

                if c_status == "NOT_FOUND":
                    not_found_count += 1
                elif c_status == "ERROR":
                    error_count += 1
                if c_conf == "LOW":
                    low_count += 1

                is_valid = is_valid_cache_entry(entry)
                if is_valid:
                    valid_cache_count += 1
                    action = "SKIP"  # Dùng kết quả cache
                else:
                    invalid_cache_count += 1
                    action = "RECHECK"  # Cần kiểm tra lại bằng nguồn tốt hơn

                audit_rows.append({
                    "row_index": idx,
                    "title": title,
                    "singer": singer,
                    "cache_key": key,
                    "cache_hit": True,
                    "cache_valid": is_valid,
                    "cache_status": c_status,
                    "cache_genre": c_genre,
                    "action": action,
                })
            else:
                cache_miss_count += 1
                audit_rows.append({
                    "row_index": idx,
                    "title": title,
                    "singer": singer,
                    "cache_key": key,
                    "cache_hit": False,
                    "cache_valid": False,
                    "cache_status": "MISS",
                    "cache_genre": "",
                    "action": "SEARCH",
                })

        # Đếm Orphan Cache
        orphan_cache_count = sum(1 for k in self.cache_data if k not in csv_keys_seen)

        stats = {
            "csv_total": csv_total,
            "cache_total": cache_total,
            "cache_hit": cache_hit_count,
            "cache_miss": cache_miss_count,
            "valid_cache": valid_cache_count,
            "invalid_cache": invalid_cache_count,
            "not_found": not_found_count,
            "error": error_count,
            "low": low_count,
            "orphan_cache": orphan_cache_count,
        }

        audit_df = pd.DataFrame(audit_rows)

        # Xuất file audit CSV
        target_csv = Path(audit_csv_path or AUDIT_CSV_FILE)
        try:
            target_csv.parent.mkdir(parents=True, exist_ok=True)
            audit_df.to_csv(target_csv, index=False, encoding="utf-8-sig")
            logger.info("Đã xuất báo cáo kiểm toán cache tại: %s", target_csv)
        except Exception as e:
            logger.error("Lỗi khi ghi cache_merge_audit.csv: %s", e)

        return stats, audit_df

    def __len__(self) -> int:
        return len(self.cache_data)
