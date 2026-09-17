#!/usr/bin/env python3
"""Helper script to download all 6 Vietnamese music genre datasets by ndnm2k3 via Kaggle CLI."""

import subprocess
import sys
import shutil

DATASETS = [
    ("nhacdo", "ndnm2k3/nhacdo-vietnamese"),
    ("hiphop", "ndnm2k3/hiphop-vietnamese"),
    ("bolero", "ndnm2k3/bolero-vietnamese"),
    ("ballad", "ndnm2k3/ballad-vietnamese"),
    ("kidsong", "ndnm2k3/kidsong-vietnamese"),
    ("rb", "ndnm2k3/rb-vietnamese"),
]

def main():
    if not shutil.which("kaggle"):
        print("ERROR: Kaggle CLI is not installed or not in PATH.")
        print("Install via: pip install kaggle")
        print("And place your kaggle.json in ~/.kaggle/kaggle.json")
        sys.exit(1)

    print("=== Downloading all 6 Vietnamese Genre Datasets from ndnm2k3 ===")
    for genre, slug in DATASETS:
        dest = f"data/raw/ndnm2k3/{genre}"
        print(f"\n[+] Downloading {genre} ({slug}) -> {dest}...")
        cmd = ["kaggle", "datasets", "download", "-d", slug, "-p", dest, "--unzip"]
        try:
            res = subprocess.run(cmd, check=True)
            print(f"[✓] Successfully downloaded {genre}")
        except subprocess.CalledProcessError as e:
            print(f"[✗] Failed to download {genre}: {e}")

    print("\nAll downloads finished!")

if __name__ == "__main__":
    main()
