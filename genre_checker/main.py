"""
Chương trình chính: Music Genre Checker & Enrichment Tool (Phiên bản 2.0).
Xử lý dữ liệu CSV bài hát, tìm kiếm genre đa nguồn (Last.fm, MusicBrainz, ZingMP3, NhacCuaTui, Web...),
chuẩn hóa, kiểm định tính hợp lệ, phát hiện xung đột, kiểm toán cache và xuất báo cáo đối chiếu.
"""

import argparse
import concurrent.futures
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Optional, Tuple, List
import pandas as pd

from config import (
    DEFAULT_INPUT_CSV,
    DEFAULT_OUTPUT_CSV,
    DEFAULT_CACHE_FILE,
    OUTPUT_DIR,
    REQUEST_DELAY,
)
from normalizer import (
    normalize_title,
    normalize_artist,
    make_cache_key,
    compare_genre,
    validate_genre,
)
from cache_manager import GenreCache, is_valid_cache_entry
from searcher import GenreSearcher
from reporter import GenreReporter

# Cấu hình encoding cho stdout/stderr trên Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("GenreChecker")


def read_csv_with_fallback(file_path: Path | str) -> Tuple[pd.DataFrame, str]:
    """
    Đọc CSV bằng pandas không giả định cứng encoding.
    Thử lần lượt: utf-8 -> utf-8-sig -> cp1258 (Vietnamese Windows) -> latin1.
    """
    encodings_to_try = ["utf-8", "utf-8-sig", "cp1258", "latin1"]
    last_err: Optional[Exception] = None

    for enc in encodings_to_try:
        try:
            df = pd.read_csv(file_path, encoding=enc)
            logger.info("Đọc thành công file CSV với encoding: %s", enc)
            return df, enc
        except (UnicodeDecodeError, Exception) as e:
            last_err = e
            continue

    raise RuntimeError(f"Không thể đọc file CSV tại {file_path} với các encoding hỗ trợ: {last_err}")


def resolve_columns(
    df: pd.DataFrame,
    singer_col_arg: Optional[str] = None,
    genre_col_arg: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    Tự động nhận diện các cột: title, singer (hoặc artist), genre (hoặc genre_found).
    """
    cols = df.columns.tolist()

    title_col = "title"
    if "title" not in cols:
        for candidate in ["song_title", "name", "track_name"]:
            if candidate in cols:
                title_col = candidate
                break

    if singer_col_arg and singer_col_arg in cols:
        singer_col = singer_col_arg
    elif "singer" in cols:
        singer_col = "singer"
    elif "artist" in cols:
        singer_col = "artist"
    else:
        singer_col = "singer"

    if genre_col_arg and genre_col_arg in cols:
        genre_col = genre_col_arg
    elif "genre" in cols:
        genre_col = "genre"
    elif "genre_found" in cols:
        genre_col = "genre_found"
    else:
        genre_col = "genre"

    return title_col, singer_col, genre_col


def print_precheck_report(
    df: pd.DataFrame,
    title_col: str,
    singer_col: str,
    genre_col: str,
) -> None:
    """In báo cáo kiểm tra dữ liệu trước khi bắt đầu xử lý."""
    total_rows = len(df)
    missing_titles = df[title_col].isna().sum() + (df[title_col].astype(str).str.strip() == "").sum()
    missing_singers = df[singer_col].isna().sum() + (df[singer_col].astype(str).str.strip() == "").sum()
    missing_genres = df[genre_col].isna().sum() + (df[genre_col].astype(str).str.strip() == "").sum()

    dup_count = df.duplicated(subset=[title_col, singer_col]).sum()

    print("\n" + "=" * 50)
    print("THÔNG TIN DỮ LIỆU ĐẦU VÀO (PRE-CHECK REPORT)")
    print("=" * 50)
    print(f"Total rows:                 {total_rows}")
    print(f"Missing title:              {missing_titles}")
    print(f"Missing singer:             {missing_singers}")
    print(f"Missing original genre:     {missing_genres}")
    print(f"Duplicate title + singer:   {dup_count}")
    print("=" * 50 + "\n")


def print_cache_audit_report(stats: dict) -> None:
    """In báo cáo kiểm toán cache đối chiếu với Master CSV."""
    print("=" * 50)
    print("CACHE AUDIT & MERGE REPORT")
    print("=" * 50)
    print(f"CSV total:      {stats['csv_total']}")
    print(f"Cache total:    {stats['cache_total']}")
    print(f"Cache hit:      {stats['cache_hit']}")
    print(f"Cache miss:     {stats['cache_miss']}")
    print(f"Valid cache:    {stats['valid_cache']}")
    print(f"Invalid cache:  {stats['invalid_cache']}")
    print(f"NOT_FOUND:      {stats['not_found']}")
    print(f"ERROR:          {stats['error']}")
    print(f"LOW:            {stats['low']}")
    print(f"Orphan cache:   {stats['orphan_cache']}")
    print("=" * 50 + "\n")


def log_record_result(
    status: str,
    title: str,
    singer: str,
    genre_original: str,
    genre_search_dc: str,
    source: str,
    verbose: bool = False,
) -> None:
    """In log theo định dạng chuẩn của mục 28."""
    g_orig_display = "" if pd.isna(genre_original) or str(genre_original).lower() in {"nan", "none"} else str(genre_original)

    if status == "MISSING_ORIGINAL":
        print(
            f"[MISSING_ORIGINAL]\n"
            f"title={title}\n"
            f"singer={singer}\n"
            f"genre_original=\n"
            f"genre_search_dc={genre_search_dc}\n"
            f"source={source}\n"
        )
    elif status == "DIFFERENT":
        print(
            f"[DIFFERENT]\n"
            f"title={title}\n"
            f"singer={singer}\n"
            f"genre_original={g_orig_display}\n"
            f"genre_search_dc={genre_search_dc}\n"
            f"source={source}\n"
        )
    elif status == "MATCH":
        if verbose:
            print(
                f"[MATCH]\n"
                f"title={title}\n"
                f"singer={singer}\n"
                f"genre_original={g_orig_display}\n"
                f"genre_search_dc={genre_search_dc}\n"
                f"source={source}\n"
            )
    elif status == "NOT_FOUND":
        print(
            f"[NOT_FOUND]\n"
            f"title={title}\n"
            f"singer={singer}\n"
        )
    elif status == "CONFLICT":
        print(
            f"[CONFLICT]\n"
            f"title={title}\n"
            f"singer={singer}\n"
            f"conflicting_sources={source}\n"
        )
    elif status == "ERROR":
        print(
            f"[ERROR]\n"
            f"title={title}\n"
            f"singer={singer}\n"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Music Genre Checker & Enrichment Tool - Kiểm tra và bổ sung thể loại bài hát đa nguồn."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=DEFAULT_INPUT_CSV,
        help=f"Đường dẫn file CSV đầu vào (Mặc định: {DEFAULT_INPUT_CSV})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_OUTPUT_CSV,
        help=f"Đường dẫn file CSV đầu ra (Mặc định: {DEFAULT_OUTPUT_CSV})",
    )
    parser.add_argument(
        "--cache",
        type=str,
        default=str(DEFAULT_CACHE_FILE),
        help=f"Đường dẫn file cache (Mặc định: {DEFAULT_CACHE_FILE})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=REQUEST_DELAY,
        help=f"Thời gian nghỉ (giây) giữa các request (Mặc định: {REQUEST_DELAY}s)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Giới hạn số dòng xử lý (ví dụ: --limit 20)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Tiếp tục từ file output cũ nếu đã tồn tại (Mặc định: True)",
    )
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Chạy mới hoàn toàn, không nạp lại file output cũ",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="In chi tiết cả các dòng [MATCH] (Mặc định: False)",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="all",
        choices=["all", "lastfm", "musicbrainz", "vietnam", "international", "web"],
        help="Chỉ định phạm vi nguồn tìm kiếm (Mặc định: all)",
    )
    parser.add_argument(
        "--singer-col",
        type=str,
        default=None,
        help="Chỉ định tên cột ca sĩ nếu khác 'singer'/'artist'",
    )
    parser.add_argument(
        "--genre-col",
        type=str,
        default=None,
        help="Chỉ định tên cột thể loại gốc nếu khác 'genre'/'genre_found'",
    )
    parser.add_argument(
        "--force-search",
        action="store_true",
        default=False,
        help="Bắt buộc tìm kiếm lại đồng thời tất cả các nguồn (bỏ qua cache cũ và output cũ)",
    )
    parser.add_argument(
        "--refresh-single-source",
        action="store_true",
        default=False,
        help="Tìm kiếm lại các bản ghi chỉ có 1 nguồn để làm giàu đa thể loại",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Số luồng tìm kiếm đồng thời đa nguồn cho mỗi bài (Mặc định: 6)",
    )
    parser.add_argument(
        "--row-workers",
        type=int,
        default=8,
        help="Số bài hát xử lý đồng thời song song (Row-level Multi-threading, Mặc định: 8)",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        logger.error("File đầu vào không tồn tại: %s", input_path)
        sys.exit(1)

    # 1. Đọc dữ liệu đầu vào với fallback encoding
    logger.info("Đang đọc dữ liệu từ: %s", input_path)
    df, used_encoding = read_csv_with_fallback(input_path)

    # 2. Nhận diện các cột
    title_col, singer_col, genre_col = resolve_columns(df, args.singer_col, args.genre_col)

    # Kiểm tra cột bắt buộc
    missing_required = []
    if title_col not in df.columns:
        missing_required.append("title")
    if singer_col not in df.columns:
        missing_required.append("singer (hoặc artist)")
    if genre_col not in df.columns:
        missing_required.append("genre (hoặc genre_found)")

    if missing_required:
        logger.error("File CSV thiếu các cột bắt buộc: %s", missing_required)
        sys.exit(1)

    # 3. Báo cáo kiểm tra trước khi xử lý (Pre-check report)
    print_precheck_report(df, title_col, singer_col, genre_col)

    # 4. Khởi tạo Cache và thực hiện Cache Audit
    cache = GenreCache(args.cache)
    audit_stats, audit_df = cache.audit(df, title_col, singer_col)
    print_cache_audit_report(audit_stats)

    # 5. Khởi tạo hoặc nạp lại từ output cũ nếu có Resume
    new_cols = ["genre_search_dc", "genre_source", "genre_status", "genre_confidence"]

    resumed_count = 0
    if args.resume and output_path.exists():
        try:
            logger.info("Phát hiện output cũ tại %s. Đang nạp lại để Resume...", output_path)
            resumed_df, _ = read_csv_with_fallback(output_path)
            if all(c in resumed_df.columns for c in new_cols) and len(resumed_df) == len(df):
                for c in new_cols:
                    df[c] = resumed_df[c].fillna("")
                # Đếm các dòng đã có kết quả genre hợp lệ
                resumed_count = (df["genre_search_dc"].apply(validate_genre)).sum()
                logger.info("Đã nạp lại %d dòng đã có kết quả hợp lệ trước đó.", resumed_count)
            else:
                logger.info("File output cũ không khớp cấu trúc, khởi tạo mới các cột kết quả.")
                for col in new_cols:
                    if col not in df.columns:
                        df[col] = ""
        except Exception as e:
            logger.warning("Không thể nạp file output cũ (%s). Khởi tạo mới.", e)
            for col in new_cols:
                if col not in df.columns:
                    df[col] = ""
    else:
        for col in new_cols:
            if col not in df.columns:
                df[col] = ""

    # 6. Khởi tạo Searcher và Reporter
    searcher = GenreSearcher()
    reporter = GenreReporter()
    reporter.stats["total_rows"] = len(df)
    reporter.stats["invalid_cache"] = audit_stats["invalid_cache"]
    reporter.stats["orphan_cache"] = audit_stats["orphan_cache"]

    total_to_process = len(df) if args.limit is None else min(len(df), args.limit)
    logger.info("Bắt đầu xử lý %d dòng với chế độ source='%s'...", total_to_process, args.source)

    has_zing_id = "zing_id" in df.columns

    def process_row_task(idx: int) -> dict:
        row = df.iloc[idx]
        title = str(row[title_col]) if pd.notna(row[title_col]) else ""
        singer = str(row[singer_col]) if pd.notna(row[singer_col]) else ""
        orig_genre = str(row[genre_col]) if pd.notna(row[genre_col]) else ""
        zing_id = str(row["zing_id"]) if has_zing_id and pd.notna(row["zing_id"]) else None

        need_search = False
        if args.force_search:
            need_search = True
        else:
            raw_genre = df.at[idx, "genre_search_dc"]
            existing_genre = "" if pd.isna(raw_genre) else str(raw_genre).strip()
            if existing_genre.lower() in {"nan", "none", "null"}:
                existing_genre = ""

            raw_status = df.at[idx, "genre_status"]
            existing_status = "" if pd.isna(raw_status) else str(raw_status).strip()
            if existing_status.lower() in {"nan", "none", "null"}:
                existing_status = ""

            raw_src = df.at[idx, "genre_source"]
            existing_src = "" if pd.isna(raw_src) else str(raw_src).strip()
            if existing_src.lower() in {"nan", "none", "null"}:
                existing_src = ""

            if existing_genre and validate_genre(existing_genre):
                if args.refresh_single_source and len(existing_src.split("|")) < 2:
                    need_search = True
                else:
                    return {
                        "idx": idx,
                        "title": title,
                        "singer": singer,
                        "orig_genre": orig_genre,
                        "genre": existing_genre,
                        "source": existing_src,
                        "status": existing_status,
                        "confidence": str(df.at[idx, "genre_confidence"] or "HIGH"),
                        "is_cached": True,
                        "already_done": True,
                    }
            elif existing_status == "NOT_FOUND":
                return {
                    "idx": idx,
                    "title": title,
                    "singer": singer,
                    "orig_genre": orig_genre,
                    "genre": "",
                    "source": existing_src,
                    "status": "NOT_FOUND",
                    "confidence": "0",
                    "is_cached": True,
                    "already_done": True,
                }

        cached_val = cache.get(title, singer) if not args.force_search else None
        is_cached = False
        evidences_list: List[dict] = []

        if not need_search and cached_val and is_valid_cache_entry(cached_val):
            cached_src = cached_val.get("source", "")
            if args.refresh_single_source and len(cached_src.split("|")) < 2:
                need_search = True
            else:
                is_cached = True
                searched_genre = cached_val.get("genre", "")
                source = cached_src
                confidence = cached_val.get("confidence", "HIGH")
                status = compare_genre(orig_genre, searched_genre)

        if need_search or not is_cached:
            if args.source == "all":
                searched_genre, source, status, confidence, evidences_list = searcher.search_all_concurrent(
                    title=title,
                    singer=singer,
                    zing_id=zing_id,
                    max_workers=args.workers,
                )
            else:
                searched_genre, source, status, confidence, evidences_list = searcher.search_cascade(
                    title=title,
                    singer=singer,
                    zing_id=zing_id,
                    source_mode=args.source,
                )

            status = compare_genre(orig_genre, searched_genre)

            cache.set(
                title=title,
                singer=singer,
                genre=searched_genre,
                source=source,
                status=status,
                confidence=confidence,
                evidence=evidences_list,
            )

        return {
            "idx": idx,
            "title": title,
            "singer": singer,
            "orig_genre": orig_genre,
            "genre": searched_genre,
            "source": source,
            "status": status,
            "confidence": confidence,
            "is_cached": is_cached,
            "already_done": False,
        }

    try:
        completed_count = 0
        df_lock = threading.Lock()
        indices_to_process = list(range(total_to_process))

        logger.info(
            "Khởi chạy Multi-threading: %d bài xử lý song song (row_workers=%d, sub_workers=%d)...",
            args.row_workers,
            args.row_workers,
            args.workers,
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.row_workers) as executor:
            future_to_idx = {executor.submit(process_row_task, idx): idx for idx in indices_to_process}

            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    res = future.result()

                    with df_lock:
                        if not res.get("already_done"):
                            df.at[idx, "genre_search_dc"] = res["genre"]
                            df.at[idx, "genre_source"] = res["source"]
                            df.at[idx, "genre_status"] = res["status"]
                            df.at[idx, "genre_confidence"] = res["confidence"]

                            log_record_result(
                                status=res["status"],
                                title=res["title"],
                                singer=res["singer"],
                                genre_original=res["orig_genre"],
                                genre_search_dc=res["genre"],
                                source=res["source"],
                                verbose=args.verbose,
                            )

                        reporter.record_row(
                            source=res["source"],
                            status=res["status"],
                            is_cached=res["is_cached"],
                        )

                        completed_count += 1
                        if completed_count % 20 == 0 or completed_count == total_to_process:
                            cache.save()
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            df.to_csv(output_path, index=False, encoding="utf-8-sig")
                            logger.info(
                                "Checkpoint: đã xử lý %d/%d bài (%.1f%%)...",
                                completed_count,
                                total_to_process,
                                (completed_count / total_to_process) * 100,
                            )

                except Exception as ex:
                    logger.error("Lỗi ngoại lệ khi xử lý dòng %d: %s", idx, ex)

    except KeyboardInterrupt:
        logger.warning("\nNhận tín hiệu dừng (Ctrl+C). Đang lưu lại tiến độ...")
    finally:
        # Lưu cache và xuất kết quả cuối cùng
        cache.save(force=True)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info("Đã lưu kết quả hoàn chỉnh tại: %s", output_path)

        # Lưu bản copy vào thư mục output của project
        local_output_csv = OUTPUT_DIR / "missing_genre_research_checked.csv"
        df.to_csv(local_output_csv, index=False, encoding="utf-8-sig")

        # In và ghi báo cáo thống kê
        report_text = reporter.generate_report_text()
        print("\n" + report_text + "\n")

        reporter.save_reports(df)
        logger.info("Hoàn tất quy trình kiểm tra và bổ sung thể loại âm nhạc.")


if __name__ == "__main__":
    main()
