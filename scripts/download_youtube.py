#!/usr/bin/env python3
"""Helper script to download online music videos / tracks into high quality WAV/MP3 using yt-dlp."""

import argparse
import subprocess
import sys
import shutil

def main():
    parser = argparse.ArgumentParser(description="Download music audio from YouTube/Web with yt-dlp.")
    parser.add_argument("url", help="YouTube URL or link to playlist/video")
    parser.add_argument("--format", default="wav", choices=["wav", "mp3"], help="Target audio format (default: wav)")
    parser.add_argument("--output", default="data/raw/custom_downloads/%(title)s.%(ext)s", help="Output template")
    parser.add_argument("--with-thumbnail", action="store_true", help="Download cover art / thumbnail")
    parser.add_argument("--with-subs", action="store_true", help="Download Vietnamese subtitles/lyrics if available")

    args = parser.parse_args()

    if not shutil.which("yt-dlp"):
        print("ERROR: yt-dlp is not installed.")
        print("Install via: pip install -U yt-dlp")
        sys.exit(1)

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", args.format,
        "--audio-quality", "0",
        "-o", args.output,
    ]

    if args.with_thumbnail:
        cmd.append("--write-thumbnail")
    if args.with_subs:
        cmd.extend(["--write-subs", "--sub-langs", "vi,en"])

    cmd.append(args.url)

    print(f"Running command: {' '.join(cmd)}")
    subprocess.run(cmd)

if __name__ == "__main__":
    main()
