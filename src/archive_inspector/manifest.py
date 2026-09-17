"""Generates dataset archive manifests in data/manifests/<dataset>_archives.json."""

import json
from pathlib import Path
from typing import Any, Dict, List

from archive_inspector.base import ArchiveInfo
from archive_inspector.remote_inspector import RemoteInspector


class ManifestGenerator:
    """Discovers, inspects, and writes archive manifests for all 4 target sources."""

    def __init__(self, manifests_dir: Path = Path("data/manifests")):
        self.manifests_dir = Path(manifests_dir)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.inspector = RemoteInspector()

    def generate_fma_manifest(self) -> Path:
        """Generate manifest for FMA archives (metadata, small, medium, large, full)."""
        archives_meta = [
            {"name": "fma_metadata.zip", "url": "https://os.unil.cloud.switch.ch/fma/fma_metadata.zip", "type": "metadata"},
            {"name": "fma_small.zip", "url": "https://os.unil.cloud.switch.ch/fma/fma_small.zip", "type": "audio"},
            {"name": "fma_medium.zip", "url": "https://os.unil.cloud.switch.ch/fma/fma_medium.zip", "type": "audio"},
            {"name": "fma_large.zip", "url": "https://os.unil.cloud.switch.ch/fma/fma_large.zip", "type": "audio"},
            {"name": "fma_full.zip", "url": "https://os.unil.cloud.switch.ch/fma/fma_full.zip", "type": "audio"},
        ]

        archives: List[Dict[str, Any]] = []
        for item in archives_meta:
            info = self.inspector.inspect_archive(item["url"], archive_type=item["type"])
            archives.append({
                "name": item["name"],
                "size": info.size,
                "type": item["type"],
                "remote_url": item["url"],
                "inspectable": info.inspectable,
                "remote_inspection": info.remote_inspection,
                "total_entries": info.total_entries,
                "sample_files": [e.filename for e in info.entries_sample[:10]],
            })

        manifest_data = {
            "dataset": "fma",
            "source_url": "https://github.com/mdeff/fma",
            "storage_host": "https://os.unil.cloud.switch.ch/fma/",
            "archives": archives,
        }

        out_path = self.manifests_dir / "fma_archives.json"
        out_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")
        return out_path

    def generate_msd_manifest(self) -> Path:
        """Generate manifest for Million Song Dataset archives."""
        archives_meta = [
            {"name": "mxm_dataset_train.txt.zip", "url": "http://millionsongdataset.com/sites/default/files/AdditionalFiles/mxm_dataset_train.txt.zip", "type": "lyrics"},
            {"name": "millionsongsubset_full.tar.gz", "url": "http://static.echonest.com/millionsongsubset_full.tar.gz", "type": "metadata"},
        ]

        archives: List[Dict[str, Any]] = []
        for item in archives_meta:
            info = self.inspector.inspect_archive(item["url"], archive_type=item["type"])
            archives.append({
                "name": item["name"],
                "size": info.size,
                "type": item["type"],
                "remote_url": item["url"],
                "inspectable": info.inspectable,
                "remote_inspection": info.remote_inspection,
                "total_entries": info.total_entries,
                "sample_files": [e.filename for e in info.entries_sample[:10]],
            })

        manifest_data = {
            "dataset": "million_song_dataset",
            "source_url": "http://millionsongdataset.com/",
            "archives": archives,
        }

        out_path = self.manifests_dir / "million_song_dataset_archives.json"
        out_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")
        return out_path

    def generate_upf_manifest(self) -> Path:
        """Generate manifest for UPF repository."""
        handle_url = "https://repositori.upf.edu/handle/10230/33285"
        probe = self.inspector.probe_url(handle_url)

        # UPF institutional DSpace has Anubis WAF challenge, so remote_inspection is unsupported unless solved
        manifest_data = {
            "dataset": "upf",
            "source_url": handle_url,
            "archives": [
                {
                    "name": "upf_repository_handle",
                    "size": probe["content_length"],
                    "type": "metadata_and_audio",
                    "remote_url": handle_url,
                    "inspectable": False,
                    "remote_inspection": "unsupported",
                    "notes": ["DSpace institutional repository protected by Anubis anti-bot challenge. Local staging or browser session required."],
                }
            ],
        }

        out_path = self.manifests_dir / "upf_archives.json"
        out_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")
        return out_path

    def generate_kaggle_manifest(self) -> Path:
        """Generate manifest for Kaggle Vietnam Music Genre dataset."""
        kaggle_url = "https://www.kaggle.com/datasets/xuaam1/vietnam-music-genre"
        raw_kaggle_dir = Path("data/raw/vietnam_music_genre")
        local_mp3s = list(raw_kaggle_dir.rglob("*.mp3")) if raw_kaggle_dir.exists() else []

        manifest_data = {
            "dataset": "vietnam_music_genre",
            "source_url": kaggle_url,
            "kaggle_dataset_id": "xuaam1/vietnam-music-genre",
            "archives": [
                {
                    "name": "vietnam-music-genre.zip",
                    "size": sum(f.stat().st_size for f in local_mp3s) if local_mp3s else 0,
                    "type": "audio",
                    "remote_url": kaggle_url,
                    "inspectable": bool(local_mp3s),
                    "remote_inspection": "unsupported_requires_kaggle_api_auth",
                    "local_staged_tracks": len(local_mp3s),
                    "notes": [
                        "Direct unauthenticated HTTP inspection returns 404/login redirect.",
                        "Dataset download uses Kaggle API client or local raw staging.",
                    ],
                }
            ],
        }

        out_path = self.manifests_dir / "vietnam_music_genre_archives.json"
        out_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")
        return out_path

    def generate_all(self) -> Dict[str, Path]:
        """Generate manifests for all 4 sources."""
        return {
            "fma": self.generate_fma_manifest(),
            "million_song_dataset": self.generate_msd_manifest(),
            "upf": self.generate_upf_manifest(),
            "vietnam_music_genre": self.generate_kaggle_manifest(),
        }
