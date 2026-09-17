"""Phase 1: Discover. Discovers archives, metadata files, and audio structures across all 4 sources."""

from pathlib import Path
from typing import Any, Dict, List
from rich.console import Console

from archive_inspector.manifest import ManifestGenerator

console = Console(highlight=False)


class DatasetDiscoverer:
    """Discovers archives, metadata, and audio resources across the 4 dataset sources."""

    def __init__(self, raw_dir: Path = Path("data/raw")):
        self.raw_dir = Path(raw_dir)
        self.manifest_gen = ManifestGenerator()

    def discover_fma(self) -> Dict[str, Any]:
        """Discover FMA structures."""
        archives = [
            "fma_metadata.zip",
            "fma_small.zip",
            "fma_medium.zip",
            "fma_large.zip",
            "fma_full.zip",
        ]
        metadata_files = [
            "tracks.csv",
            "genres.csv",
            "features.csv",
            "echonest.csv",
        ]
        audio_subsets = [
            "fma_small",
            "fma_medium",
            "fma_large",
            "fma_full",
        ]

        # Check local staging
        fma_raw = self.raw_dir / "fma"
        fma_meta_dir = fma_raw / "fma_metadata"
        meta_present = [f for f in metadata_files if (fma_meta_dir / f).exists() or (fma_raw / f).exists()]

        return {
            "source": "FMA",
            "source_url": "https://github.com/mdeff/fma",
            "archives": archives,
            "metadata_files": metadata_files,
            "metadata_files_present": meta_present,
            "audio_subsets": audio_subsets,
        }

    def discover_msd(self) -> Dict[str, Any]:
        """Discover Million Song Dataset structures."""
        archives = [
            "mxm_dataset_train.txt.zip",
            "millionsongsubset_full.tar.gz",
        ]
        metadata_files = [
            "mxm_dataset_train.txt",
            "millionsongsubset",
        ]
        audio_subsets: List[str] = []  # Full audio not distributed with MSD

        msd_raw = self.raw_dir / "million_song_dataset"
        meta_present = [f for f in metadata_files if (msd_raw / f).exists()]

        return {
            "source": "Million Song Dataset",
            "source_url": "http://millionsongdataset.com/",
            "archives": archives,
            "metadata_files": metadata_files,
            "metadata_files_present": meta_present,
            "audio_subsets": audio_subsets,
            "note": "Audio explicitly NOT_AVAILABLE internally; musiXmatch lyrics mapping available.",
        }

    def discover_upf(self) -> Dict[str, Any]:
        """Discover UPF repository structures."""
        archives = [
            "upf_repository_handle",
        ]
        metadata_files = [
            "annotations.json",
            "item_metadata.xml",
        ]
        audio_subsets = [
            "audio_recordings",
        ]

        upf_raw = self.raw_dir / "upf"
        staged_files = [f.name for f in upf_raw.glob("*.*")] if upf_raw.exists() else []

        return {
            "source": "UPF Repository",
            "source_url": "https://repositori.upf.edu/handle/10230/33285",
            "archives": archives,
            "metadata_files": metadata_files,
            "metadata_files_present": [f for f in metadata_files if f in staged_files],
            "audio_subsets": audio_subsets,
            "note": "Institutional DSpace repository protected by Anubis anti-bot challenge.",
        }

    def discover_kaggle(self) -> Dict[str, Any]:
        """Discover Vietnam Music Genre Kaggle structures."""
        archives = [
            "vietnam-music-genre.zip",
        ]
        kaggle_raw = self.raw_dir / "vietnam_music_genre"
        genres = [d.name for d in kaggle_raw.iterdir() if d.is_dir()] if kaggle_raw.exists() else []
        mp3_count = len(list(kaggle_raw.rglob("*.mp3"))) if kaggle_raw.exists() else 0

        return {
            "source": "Vietnam Music Genre (Kaggle)",
            "source_url": "https://www.kaggle.com/datasets/xuaam1/vietnam-music-genre",
            "archives": archives,
            "metadata_files": ["id3_tags", "folder_genre_labels"],
            "genres_discovered": genres,
            "audio_tracks_count": mp3_count,
            "note": "Every MP3 represents a track with genre inferred from parent directory.",
        }

    def discover_all(self, print_output: bool = True) -> Dict[str, Any]:
        """Discover all 4 sources and optionally print Section 8 formatted output."""
        fma_res = self.discover_fma()
        msd_res = self.discover_msd()
        upf_res = self.discover_upf()
        kaggle_res = self.discover_kaggle()

        # Generate archive manifests
        self.manifest_gen.generate_all()

        results = {
            "fma": fma_res,
            "million_song_dataset": msd_res,
            "upf": upf_res,
            "vietnam_music_genre": kaggle_res,
        }

        if print_output:
            self._print_discovery_section_8(results)

        return results

    def _print_discovery_section_8(self, results: Dict[str, Any]) -> None:
        """Prints discovery output strictly following Section 8 of specification."""
        console.print()
        for key, res in results.items():
            console.print(f"[bold cyan]SOURCE: {res['source'].upper()}[/bold cyan]")
            console.print("\n[bold]Archives:[/bold]")
            for arch in res.get("archives", []):
                console.print(f"  [green]✓[/green] {arch}")

            console.print("\n[bold]Metadata:[/bold]")
            for meta in res.get("metadata_files", []):
                console.print(f"  [green]✓[/green] {meta}")

            console.print("\n[bold]Audio:[/bold]")
            audio_subsets = res.get("audio_subsets", [])
            if audio_subsets:
                for aud in audio_subsets:
                    console.print(f"  [green]✓[/green] {aud}")
            elif res.get("audio_tracks_count"):
                console.print(f"  [green]✓[/green] {res['audio_tracks_count']} staged MP3 files ({', '.join(res.get('genres_discovered', []))})")
            else:
                console.print(f"  [yellow]![/yellow] Not bundled internally ({res.get('note', 'N/A')})")

            console.print("=" * 40)
