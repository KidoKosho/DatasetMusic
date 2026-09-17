"""
Script tải tự động bộ dữ liệu Kaggle vietnam-music-genre của tác giả xuaam1.
Tổng cộng: 5,371 files âm thanh MP3 30 giây phân bố theo 5 thể loại:
(Pop, Bolero, Rap, Dân ca, Rock).

Yêu cầu:
- Đã cài đặt kaggle CLI (pip install kaggle)
- Đã cấu hình file kaggle.json trong ~/.kaggle/kaggle.json
"""

import os
import subprocess
import sys
from pathlib import Path

DATASET_SLUG = "xuaam1/vietnam-music-genre"
TARGET_DIR = Path("data/raw/vietnam_music_genre")


def download_xuaam1():
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 70)
    print(" BẮT ĐẦU TẢI DATASET: vietnam-music-genre (Tác giả: xuaam1)")
    print(f" URL: https://www.kaggle.com/datasets/{DATASET_SLUG}")
    print(f" Thư mục đích: {TARGET_DIR.resolve()}")
    print("=" * 70)

    cmd = [
        "kaggle", "datasets", "download",
        "-d", DATASET_SLUG,
        "-p", str(TARGET_DIR),
        "--unzip"
    ]
    try:
        subprocess.run(cmd, check=True)
        print("\n[THÀNH CÔNG] Đã tải và giải nén 5,371 files âm thanh từ xuaam1!")
    except FileNotFoundError:
        print("\n[LỖI] Chưa cài đặt Kaggle CLI. Vui lòng chạy: pip install kaggle")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"\n[LỖI] Quá trình tải thất bại: {e}")
        print("Gợi ý: Kiểm tra file kaggle.json trong C:\\Users\\<Username>\\.kaggle\\kaggle.json")
        sys.exit(e.returncode)


if __name__ == "__main__":
    download_xuaam1()
