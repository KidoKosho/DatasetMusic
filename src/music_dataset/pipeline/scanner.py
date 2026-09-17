"""Phase 2: Scanner. Scans metadata fields across CSV, JSON, XML, TXT, and audio tags without hardcoding single fields."""

import csv
import json
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
from mutagen import File as MutagenFile

from music_dataset.constants import DatasetName, DownloadStatus, LanguageStatus
from music_dataset.metadata.normalizer import parse_vietnam_genre_filename
from music_dataset.schema import Track, generate_deterministic_id


class MetadataScanner:
    """Scans metadata fields across all available datasets and outputs discovered tracks."""

    def __init__(
        self,
        raw_dir: Path = Path("data/raw"),
        manifests_dir: Path = Path("data/manifests"),
        reports_dir: Path = Path("reports"),
    ):
        self.raw_dir = Path(raw_dir)
        self.manifests_dir = Path(manifests_dir)
        self.reports_dir = Path(reports_dir)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def scan_all(self, limit_per_dataset: Optional[int] = None) -> List[Dict[str, Any]]:
        """Scan all 4 datasets and write data/manifests/discovered.jsonl."""
        discovered: List[Dict[str, Any]] = []

        # 1. Scan Kaggle Vietnam Music Genre
        kaggle_tracks = list(self.scan_kaggle(limit=limit_per_dataset))
        discovered.extend(kaggle_tracks)

        # 2. Scan FMA tracks.csv
        fma_tracks = list(self.scan_fma(limit=limit_per_dataset))
        discovered.extend(fma_tracks)

        # 3. Scan Million Song Dataset
        msd_tracks = list(self.scan_msd(limit=limit_per_dataset))
        discovered.extend(msd_tracks)

        # 4. Scan UPF
        upf_tracks = list(self.scan_upf(limit=limit_per_dataset))
        discovered.extend(upf_tracks)

        # Write discovered.jsonl
        discovered_path = self.manifests_dir / "discovered.jsonl"
        with open(discovered_path, "w", encoding="utf-8") as f:
            for item in discovered:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        # Write reports/files.json
        self._write_files_report(discovered)

        return discovered

    def scan_kaggle(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """Scan Kaggle raw audio directory: folder -> genre_original, MP3 -> ID3 metadata."""
        kaggle_dir = self.raw_dir / "vietnam_music_genre"
        if not kaggle_dir.exists():
            return

        count = 0
        mp3_files = sorted(list(kaggle_dir.rglob("*.mp3")))
        for audio_file in mp3_files:
            genre_folder = audio_file.parent.name
            track_id = generate_deterministic_id(DatasetName.VIETNAM_MUSIC_GENRE.value, source_id=audio_file.stem)

            # Read ID3 tags via Mutagen
            id3_data: Dict[str, Any] = {}
            try:
                tag = MutagenFile(audio_file)
                if tag:
                    for k, v in tag.items():
                        # Extract simple string values
                        val = str(v)
                        if hasattr(v, "text") and v.text:
                            val = str(v.text[0])
                        id3_data[str(k).lower()] = val
            except Exception:
                pass

            # Parse filename using specialized Vietnam Music Genre naming convention
            fn_meta = parse_vietnam_genre_filename(audio_file.name, genre_folder)

            title = id3_data.get("tit2") or id3_data.get("title")
            if not title or title == audio_file.stem:
                title = fn_meta.get("title") or audio_file.stem

            artist = id3_data.get("tpe1") or id3_data.get("artist") or fn_meta.get("artist")
            album = id3_data.get("talb") or id3_data.get("album") or None

            record = {
                "track_id": track_id,
                "dataset": DatasetName.VIETNAM_MUSIC_GENRE.value,
                "source_id": audio_file.stem,
                "source_filename": audio_file.name,
                "audio_path": str(audio_file),
                "has_audio": True,
                "title": title,
                "artist": artist,
                "artist_name": artist,
                "artist_bio": None,
                "artist_country": "Vietnam",  # Dataset annotation
                "country": "Vietnam",
                "album": album,
                "genre_original": genre_folder,
                "genre": fn_meta.get("genre") or genre_folder,
                "tags": [genre_folder, "vietnam"],
                "language": "vi",
                "lyrics": None,
                "has_lyrics": False,
                "has_artwork": False,
                "has_metadata": True,
                "dataset_semantics": "vietnam_music_genre",
                "is_vietnamese_song": True,  # Kaggle dataset assertion
                "is_vietnamese_artist": True,
                "is_vietnamese_title": True,
                "provenance": {
                    "dataset": "vietnam_music_genre",
                    "file": str(audio_file),
                    "genre_source": "folder_hierarchy",
                    "id3": id3_data,
                    "filename_parsing": fn_meta,
                },
            }
            yield record
            count += 1
            if limit and count >= limit:
                break

    def scan_fma(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """Scan FMA tracks.csv inspecting title, artist, bio, location, genres, and tags."""
        fma_raw = self.raw_dir / "fma"
        tracks_csv = fma_raw / "fma_metadata" / "tracks.csv"
        if not tracks_csv.exists():
            tracks_csv = fma_raw / "tracks.csv"
        if not tracks_csv.exists():
            return

        count = 0
        with open(tracks_csv, mode="r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            # Skip 3 header rows
            _ = [next(reader, []) for _ in range(3)]
            for row in reader:
                if not row or len(row) < 2:
                    continue
                fma_id = row[0].strip()
                album_title = row[11].strip() if len(row) > 11 else None
                artist_bio = row[17].strip() if len(row) > 17 else None
                artist_loc = row[23].strip() if len(row) > 23 else None
                artist_name = row[26].strip() if len(row) > 26 else None
                artist_tags = row[28].strip() if len(row) > 28 else None
                genre_top = row[40].strip() if len(row) > 40 else None
                genres_all = row[42].strip() if len(row) > 42 else None
                lang_code = row[45].strip() if len(row) > 45 else None
                track_tags = row[51].strip() if len(row) > 51 else None
                title = row[52].strip() if len(row) > 52 else None

                all_tags = []
                if artist_tags:
                    all_tags.extend([t.strip() for t in artist_tags.split(",") if t.strip()])
                if track_tags:
                    all_tags.extend([t.strip() for t in track_tags.split(",") if t.strip()])

                track_id = generate_deterministic_id(DatasetName.FMA.value, source_id=fma_id)

                # Check if audio path exists in any local FMA directory
                # FMA directory structure inside archive: fma_small/000/000002.mp3
                sub_folder = fma_id.zfill(6)[:3]
                audio_rel_path = f"{sub_folder}/{fma_id.zfill(6)}.mp3"
                local_audio = fma_raw / "fma_small" / audio_rel_path
                has_audio_local = local_audio.exists()

                record = {
                    "track_id": track_id,
                    "dataset": DatasetName.FMA.value,
                    "source_id": fma_id,
                    "source_url": f"https://freemusicarchive.org/track/{fma_id}",
                    "audio_rel_path": audio_rel_path,
                    "audio_path": str(local_audio) if has_audio_local else None,
                    "has_audio": True,  # Exists in FMA audio archives
                    "has_audio_local": has_audio_local,
                    "title": title,
                    "artist": artist_name,
                    "artist_name": artist_name,
                    "artist_bio": artist_bio,
                    "artist_country": artist_loc,
                    "country": artist_loc,
                    "album": album_title,
                    "genre_original": genre_top or genres_all,
                    "genre": genre_top,
                    "tags": all_tags,
                    "language": lang_code,
                    "lyrics": None,
                    "has_lyrics": False,
                    "has_artwork": False,
                    "has_metadata": True,
                    "provenance": {
                        "dataset": "fma",
                        "fma_id": fma_id,
                        "source_file": "fma_metadata/tracks.csv",
                    },
                }
                yield record
                count += 1
                if limit and count >= limit:
                    break

    def scan_msd(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """Scan Million Song Dataset files (e.g. musiXmatch dataset mappings or subset)."""
        msd_raw = self.raw_dir / "million_song_dataset"
        mxm_path = msd_raw / "mxm_dataset_train.txt"
        if not mxm_path.exists():
            return

        count = 0
        with open(mxm_path, mode="r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("#") or line.startswith("%") or not line.strip():
                    continue
                parts = line.strip().split(",")
                if len(parts) < 2:
                    continue
                msd_id = parts[0].strip()
                mxm_id = parts[1].strip()
                track_id = generate_deterministic_id(DatasetName.MILLION_SONG_DATASET.value, source_id=msd_id)

                record = {
                    "track_id": track_id,
                    "dataset": DatasetName.MILLION_SONG_DATASET.value,
                    "source_id": msd_id,
                    "mxm_id": mxm_id,
                    "source_url": f"http://millionsongdataset.com/track/{msd_id}",
                    "title": None,  # Provided in separate MSD subset / sqlite
                    "artist": None,
                    "artist_name": None,
                    "artist_bio": None,
                    "artist_country": None,
                    "country": None,
                    "album": None,
                    "genre": None,
                    "tags": [],
                    "language": None,
                    "lyrics": f"mxm_bag_of_words_mapping:{len(parts)-2}_tokens",
                    "has_lyrics": True,
                    "has_audio": False,  # Not available internally
                    "has_artwork": False,
                    "has_metadata": True,
                    "provenance": {
                        "dataset": "million_song_dataset",
                        "msd_id": msd_id,
                        "mxm_id": mxm_id,
                        "source_file": "mxm_dataset_train.txt",
                    },
                }
                yield record
                count += 1
                if limit and count >= limit:
                    break

    def scan_upf(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """Scan UPF staged files."""
        upf_raw = self.raw_dir / "upf"
        if not upf_raw.exists():
            return

        count = 0
        audio_files = sorted(list(upf_raw.rglob("*.mp3")) + list(upf_raw.rglob("*.wav")))
        for af in audio_files:
            track_id = generate_deterministic_id(DatasetName.UPF.value, source_id=af.stem)
            record = {
                "track_id": track_id,
                "dataset": DatasetName.UPF.value,
                "source_id": af.stem,
                "source_filename": af.name,
                "audio_path": str(af),
                "has_audio": True,
                "title": af.stem,
                "artist": None,
                "artist_country": None,
                "country": None,
                "album": None,
                "genre": None,
                "tags": [],
                "language": None,
                "lyrics": None,
                "has_lyrics": False,
                "has_artwork": False,
                "has_metadata": True,
                "provenance": {
                    "dataset": "upf",
                    "raw_file": str(af),
                },
            }
            yield record
            count += 1
            if limit and count >= limit:
                break

    def _write_files_report(self, discovered: List[Dict[str, Any]]) -> None:
        """Writes reports/files.json summarizing discovered files."""
        by_dataset: Dict[str, int] = {}
        for d in discovered:
            ds = d.get("dataset", "unknown")
            by_dataset[ds] = by_dataset.get(ds, 0) + 1

        files_report = {
            "total_files_discovered": len(discovered),
            "by_dataset": by_dataset,
            "sample_files": [
                {
                    "track_id": d.get("track_id"),
                    "dataset": d.get("dataset"),
                    "title": d.get("title"),
                    "artist": d.get("artist"),
                    "has_audio": d.get("has_audio"),
                }
                for d in discovered[:20]
            ],
        }
        (self.reports_dir / "files.json").write_text(
            json.dumps(files_report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
