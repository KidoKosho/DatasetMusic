"""Targeted Downloader & Asset Organizer executing items strictly from data/manifests/download_queue.jsonl."""

import csv
import json
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional
from rich.console import Console

from music_dataset.artwork.extractor import ArtworkExtractor
from music_dataset.constants import AssetStatus, DownloadStatus
from music_dataset.downloader.checksum import compute_file_sha256
from music_dataset.lyrics.manager import LyricsManager
from music_dataset.schema import Track
from music_dataset.downloader.remote_zip import RemoteZipExtractor
from music_dataset.state.database import StateDatabase

console = Console(highlight=False)


class TargetedDownloader:
    """Executes downloads and asset standardization strictly for queued candidate tracks."""

    def __init__(
        self,
        manifests_dir: Path = Path("data/manifests"),
        output_dir: Path = Path("datasets"),
        reports_dir: Path = Path("reports"),
        state_db: Optional[StateDatabase] = None,
        fma_small_url: str = "https://os.unil.cloud.switch.ch/fma/fma_small.zip",
    ):
        self.manifests_dir = Path(manifests_dir)
        self.output_dir = Path(output_dir)
        self.reports_dir = Path(reports_dir)
        self.state_db = state_db or StateDatabase()
        self.lyrics_mgr = LyricsManager()
        self.fma_remote_zip = RemoteZipExtractor(fma_small_url)
        self._fma_indexed = False

    def process_queue(
        self,
        allow_full_archive: bool = False,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Reads download_queue.jsonl and ingests assets into datasets/<dataset>/[audio, lyric, avt, label]."""
        queue_path = self.manifests_dir / "download_queue.jsonl"
        if not queue_path.exists():
            console.print("[bold red]No download queue found. Run 'python -m music_dataset plan' first.[/bold red]")
            return {"processed": 0, "errors": 0}

        # Also load full candidate records for metadata preservation
        candidates_map: Dict[str, Dict[str, Any]] = {}
        cands_path = self.manifests_dir / "candidates.jsonl"
        if cands_path.exists():
            with open(cands_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        c = json.loads(line)
                        candidates_map[c.get("track_id")] = c

        processed_count = 0
        audio_count = 0
        lyrics_count = 0
        artwork_count = 0
        blocked_count = 0

        tracks_by_dataset: Dict[str, List[Dict[str, Any]]] = {}

        with open(queue_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                track_id = item.get("track_id")
                dataset = item.get("source") or "unknown"
                cand_meta = candidates_map.get(track_id, {})

                # Check archive policy default
                skip_audio = bool(item.get("archive_download_required") and not allow_full_archive)

                # Ensure 4-folder structure exists
                ds_dir = self.output_dir / dataset
                audio_dir = ds_dir / "audio"
                lyric_dir = ds_dir / "lyric"
                avt_dir = ds_dir / "avt"
                label_dir = ds_dir / "label"
                for d in [audio_dir, lyric_dir, avt_dir, label_dir]:
                    d.mkdir(parents=True, exist_ok=True)

                # 1. Process Audio Asset
                dest_audio_path = None

                # Check if FMA track can be extracted individually via HTTP Range
                fma_rel_path = cand_meta.get("audio", {}).get("rel_path")
                if dataset == "fma" and fma_rel_path:
                    target_member = f"fma_small/{fma_rel_path}".replace("\\", "/")
                    if not self._fma_indexed:
                        try:
                            console.print("[cyan]Indexing fma_small.zip Central Directory via HTTP Range...[/cyan]")
                            self.fma_remote_zip.fetch_index(known_cd_offset=7678967074, known_cd_size=627702)
                            self._fma_indexed = True
                            console.print(f"[green]Indexed {len(self.fma_remote_zip.entries)} files in remote archive.[/green]")
                        except Exception as e:
                            console.print(f"[yellow]Remote index unavailable: {e}[/yellow]")

                    if self._fma_indexed and target_member in self.fma_remote_zip.entries:
                        dest_candidate_path = audio_dir / f"{track_id}.mp3"
                        if not dest_candidate_path.exists():
                            try:
                                console.print(f"  -> Downloading {target_member} via HTTP Range...")
                                ok = self.fma_remote_zip.extract_file(target_member, dest_candidate_path)
                                if ok:
                                    dest_audio_path = dest_candidate_path
                                    audio_count += 1
                                    cand_meta.setdefault("audio", {})["downloaded"] = True
                                    cand_meta["audio"]["path"] = str(dest_audio_path)
                                    cand_meta["audio"]["sha256"] = compute_file_sha256(dest_audio_path)
                                    skip_audio = False
                            except Exception as e:
                                console.print(f"[yellow]Failed to extract {target_member}: {e}[/yellow]")
                        else:
                            dest_audio_path = dest_candidate_path
                            audio_count += 1
                            cand_meta.setdefault("audio", {})["downloaded"] = True
                            cand_meta["audio"]["path"] = str(dest_audio_path)
                            skip_audio = False

                if not dest_audio_path and not skip_audio:
                    src_audio_path = cand_meta.get("audio", {}).get("path")
                    if src_audio_path and Path(src_audio_path).exists():
                        dest_audio_path = audio_dir / f"{track_id}.mp3"
                        if not dest_audio_path.exists():
                            shutil.copy2(src_audio_path, dest_audio_path)
                        audio_count += 1
                        cand_meta.setdefault("audio", {})["downloaded"] = True
                        cand_meta["audio"]["path"] = str(dest_audio_path)
                        cand_meta["audio"]["sha256"] = compute_file_sha256(dest_audio_path)
                elif not dest_audio_path:
                    cand_meta.setdefault("audio", {})["downloaded"] = False
                    if item.get("archive_download_required"):
                        blocked_count += 1

                # 2. Process Lyrics Asset (Embedded or Provider)
                lyrics_text = None
                if dest_audio_path and dest_audio_path.exists():
                    # Extract embedded lyrics
                    res = self.lyrics_mgr.embedded_provider.extract_from_audio_file(dest_audio_path)
                    if res:
                        lyrics_text = res.lyrics
                if not lyrics_text and cand_meta.get("lyrics", {}).get("text"):
                    lyrics_text = cand_meta["lyrics"]["text"]

                if lyrics_text and lyrics_text.strip():
                    dest_lyric_path = lyric_dir / f"{track_id}.txt"
                    dest_lyric_path.write_text(lyrics_text, encoding="utf-8")
                    lyrics_count += 1
                    cand_meta["lyrics"]["available"] = True
                    cand_meta["lyrics"]["path"] = str(dest_lyric_path)

                # 3. Process Artwork Asset (Embedded APIC)
                if dest_audio_path and dest_audio_path.exists():
                    art_file = ArtworkExtractor.extract_from_file(dest_audio_path, avt_dir, track_id)
                    if art_file:
                        artwork_count += 1
                        cand_meta["artwork"]["available"] = True
                        cand_meta["artwork"]["path"] = str(art_file)

                # Collect track record for label generation
                tracks_by_dataset.setdefault(dataset, []).append(cand_meta)

                # Upsert into State Database
                self._upsert_track_record(cand_meta, dataset, track_id)

                processed_count += 1
                if limit and processed_count >= limit:
                    break

        # 4. Generate Section 25 Label records for all 4 canonical datasets
        all_canonical_datasets = ["vietnam_music_genre", "fma", "million_song_dataset", "upf"]
        for ds_name in all_canonical_datasets:
            tracks_list = tracks_by_dataset.get(ds_name, [])
            self._generate_dataset_labels(ds_name, tracks_list)

        return {
            "processed": processed_count,
            "audio_downloaded": audio_count,
            "lyrics_saved": lyrics_count,
            "artwork_saved": artwork_count,
            "blocked_archives": blocked_count,
        }

    def _generate_dataset_labels(self, dataset: str, tracks: List[Dict[str, Any]]) -> None:
        """Generates tracks.jsonl, tracks.csv, genres.json, dataset_summary.json in datasets/<dataset>/label/."""
        label_dir = self.output_dir / dataset / "label"
        label_dir.mkdir(parents=True, exist_ok=True)

        # tracks.jsonl
        with open(label_dir / "tracks.jsonl", "w", encoding="utf-8") as f:
            for t in tracks:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")

        # tracks.csv
        csv_path = label_dir / "tracks.csv"
        fieldnames = [
            "track_id",
            "title",
            "artist",
            "genre",
            "genre_original",
            "album",
            "audio_path",
            "has_audio",
            "audio_sha256",
            "lyrics_path",
            "has_lyrics",
            "avt_path",
            "has_avt",
            "source_song_id",
            "segment_index",
            "is_vietnamese_song",
            "is_vietnamese_artist",
            "is_vietnamese_title",
            "is_vietnamese_lyrics",
            "reasons",
        ]

        # Enriched track records
        enriched_tracks: List[Dict[str, Any]] = []
        genre_distribution: Dict[str, int] = {}

        for t in tracks:
            prov = t.get("provenance", {})
            fn_parsing = prov.get("filename_parsing", {})

            # Genre resolution
            g = t.get("genre") or fn_parsing.get("genre") or prov.get("folder_genre") or prov.get("genre_source") or "unknown"
            g_orig = t.get("genre_original") or fn_parsing.get("genre_original") or prov.get("folder_genre") or g
            g_clean = str(g).lower().strip()

            genre_distribution[g_clean] = genre_distribution.get(g_clean, 0) + 1

            # Asset paths & statuses
            aud_path = t.get("audio", {}).get("path")
            has_aud = bool(aud_path and Path(aud_path).exists())
            aud_sha = t.get("audio", {}).get("sha256")

            lyr_path = t.get("lyrics", {}).get("path")
            has_lyr = bool(t.get("lyrics", {}).get("available") or (lyr_path and Path(lyr_path).exists()))

            art_path = t.get("artwork", {}).get("path")
            has_art = bool(t.get("artwork", {}).get("available") or (art_path and Path(art_path).exists()))

            song_id = fn_parsing.get("song_id") or prov.get("fma_id") or t.get("source_id")
            seg_idx = fn_parsing.get("segment")

            is_vn = True if dataset == "vietnam_music_genre" else bool(t.get("is_vietnamese_song", False))

            enriched_record = {
                "track_id": t.get("track_id"),
                "title": t.get("title") or fn_parsing.get("title"),
                "artist": t.get("artist") or fn_parsing.get("artist"),
                "genre": g_clean,
                "genre_original": g_orig,
                "album": t.get("album"),
                "audio_path": aud_path,
                "has_audio": has_aud,
                "audio_sha256": aud_sha,
                "lyrics_path": lyr_path,
                "has_lyrics": has_lyr,
                "avt_path": art_path,
                "has_avt": has_art,
                "source_song_id": song_id,
                "segment_index": seg_idx,
                "is_vietnamese_song": is_vn,
                "is_vietnamese_artist": t.get("is_vietnamese_artist", is_vn),
                "is_vietnamese_title": t.get("is_vietnamese_title", is_vn),
                "is_vietnamese_lyrics": t.get("is_vietnamese_lyrics"),
                "candidate": t.get("candidate", True),
                "reasons": t.get("reasons", []),
                "provenance": prov,
            }
            enriched_tracks.append(enriched_record)

        # Write tracks.jsonl
        with open(label_dir / "tracks.jsonl", "w", encoding="utf-8") as f:
            for rec in enriched_tracks:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        # Write tracks.csv
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for rec in enriched_tracks:
                writer.writerow({
                    "track_id": rec["track_id"],
                    "title": rec["title"],
                    "artist": rec["artist"],
                    "genre": rec["genre"],
                    "genre_original": rec["genre_original"],
                    "album": rec["album"],
                    "audio_path": rec["audio_path"],
                    "has_audio": rec["has_audio"],
                    "audio_sha256": rec["audio_sha256"],
                    "lyrics_path": rec["lyrics_path"],
                    "has_lyrics": rec["has_lyrics"],
                    "avt_path": rec["avt_path"],
                    "has_avt": rec["has_avt"],
                    "source_song_id": rec["source_song_id"],
                    "segment_index": rec["segment_index"],
                    "is_vietnamese_song": rec["is_vietnamese_song"],
                    "is_vietnamese_artist": rec["is_vietnamese_artist"],
                    "is_vietnamese_title": rec["is_vietnamese_title"],
                    "is_vietnamese_lyrics": rec["is_vietnamese_lyrics"],
                    "reasons": ";".join(rec["reasons"]),
                })

        # genres.json with counts and percentages
        total_tracks_count = len(enriched_tracks)
        genres_report = {
            "dataset": dataset,
            "total_tracks": total_tracks_count,
            "genres_count": len(genre_distribution),
            "distribution": {
                g: {
                    "count": cnt,
                    "percentage": f"{(cnt / total_tracks_count * 100):.2f}%" if total_tracks_count > 0 else "0.00%",
                }
                for g, cnt in sorted(genre_distribution.items(), key=lambda x: -x[1])
            },
        }
        (label_dir / "genres.json").write_text(json.dumps(genres_report, indent=2, ensure_ascii=False), encoding="utf-8")

        # dataset_summary.json
        summary = {
            "dataset": dataset,
            "total_candidate_tracks": total_tracks_count,
            "audio_count": sum(1 for r in enriched_tracks if r["has_audio"]),
            "lyrics_count": sum(1 for r in enriched_tracks if r["has_lyrics"]),
            "artwork_count": sum(1 for r in enriched_tracks if r["has_avt"]),
            "genres_breakdown": genre_distribution,
        }
        (label_dir / "dataset_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def _upsert_track_record(self, cand_meta: Dict[str, Any], dataset: str, track_id: str) -> None:
        """Saves unified Track object into StateDatabase."""
        try:
            track = Track(
                track_id=track_id,
                dataset=dataset,
                source_id=track_id,
                title=cand_meta.get("title"),
                artist=cand_meta.get("artist"),
                album=cand_meta.get("album"),
                audio_path=cand_meta.get("audio", {}).get("path"),
                audio_status=DownloadStatus.DOWNLOADED.value if cand_meta.get("audio", {}).get("downloaded") else DownloadStatus.PENDING.value,
                lyrics_status=AssetStatus.FOUND.value if cand_meta.get("lyrics", {}).get("available") else AssetStatus.MISSING.value,
                artwork_path=cand_meta.get("artwork", {}).get("path"),
                artwork_status=AssetStatus.EXTRACTED.value if cand_meta.get("artwork", {}).get("available") else AssetStatus.MISSING.value,
                is_vietnamese_artist=cand_meta.get("is_vietnamese_artist"),
                is_vietnamese_title=cand_meta.get("is_vietnamese_title"),
                is_vietnamese_lyrics=cand_meta.get("is_vietnamese_lyrics"),
                vietnamese_relevance={
                    "status": "confirmed" if cand_meta.get("candidate") else "unknown",
                    "confidence": 0.95,
                    "evidence": cand_meta.get("evidence", []),
                },
                provenance=cand_meta.get("provenance", {}),
            )
            self.state_db.upsert_track(track)
        except Exception:
            pass
