"""Phase 3: Vietnamese Relevance Detection. Evaluates discovered tracks and identifies candidates."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from music_dataset.language.relevance_detector import RelevanceDetector


class CandidateDetectorPhase:
    """Processes discovered tracks and filters them using the multi-evidence RelevanceDetector."""

    def __init__(
        self,
        manifests_dir: Path = Path("data/manifests"),
        reports_dir: Path = Path("reports"),
    ):
        self.manifests_dir = Path(manifests_dir)
        self.reports_dir = Path(reports_dir)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.detector = RelevanceDetector()

    def process_discovered_file(
        self,
        discovered_path: Optional[Path] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Reads discovered.jsonl, evaluates each track, and writes candidates.jsonl."""
        in_path = discovered_path or (self.manifests_dir / "discovered.jsonl")
        if not in_path.exists():
            return []

        candidates: List[Dict[str, Any]] = []
        all_evidence: List[Dict[str, Any]] = []

        out_candidates_path = self.manifests_dir / "candidates.jsonl"
        with open(in_path, "r", encoding="utf-8") as fin, open(out_candidates_path, "w", encoding="utf-8") as fout:
            count = 0
            for line in fin:
                if not line.strip():
                    continue
                track_meta = json.loads(line)
                source = track_meta.get("dataset", "unknown")
                eval_res = self.detector.evaluate_track(track_meta, source=source)

                # Merge evaluation results into track record
                track_record = {
                    "track_id": track_meta.get("track_id"),
                    "title": track_meta.get("title"),
                    "artist": track_meta.get("artist"),
                    "album": track_meta.get("album"),
                    "dataset": track_meta.get("dataset"),
                    "candidate": eval_res["candidate"],
                    "reasons": eval_res["reasons"],
                    "is_vietnamese_artist": eval_res["is_vietnamese_artist"],
                    "is_vietnamese_title": eval_res["is_vietnamese_title"],
                    "is_vietnamese_lyrics": eval_res["is_vietnamese_lyrics"],
                    "vietnamese_relevance": eval_res["candidate"],
                    "evidence": eval_res["evidence"],
                    "audio": {
                        "available": track_meta.get("has_audio", False),
                        "downloaded": track_meta.get("has_audio_local", False) or bool(track_meta.get("audio_path")),
                        "path": track_meta.get("audio_path"),
                        "rel_path": track_meta.get("audio_rel_path"),
                    },
                    "lyrics": {
                        "available": track_meta.get("has_lyrics", False),
                    },
                    "artwork": {
                        "available": track_meta.get("has_artwork", False),
                    },
                    "provenance": track_meta.get("provenance", {}),
                }

                if eval_res["candidate"]:
                    candidates.append(track_record)
                    all_evidence.extend(eval_res["evidence"])
                    fout.write(json.dumps(track_record, ensure_ascii=False) + "\n")

                count += 1
                if limit and count >= limit:
                    break

        # Generate reports/candidates.json
        self._write_candidates_report(candidates)

        # Generate reports/vietnamese_evidence.json
        self._write_evidence_report(all_evidence)

        return candidates

    def _write_candidates_report(self, candidates: List[Dict[str, Any]]) -> None:
        report_data = {
            "total_candidates": len(candidates),
            "by_dataset": {},
            "by_reason": {},
            "candidates_sample": candidates[:50],
        }
        for c in candidates:
            ds = c.get("dataset", "unknown")
            report_data["by_dataset"][ds] = report_data["by_dataset"].get(ds, 0) + 1
            for r in c.get("reasons", []):
                report_data["by_reason"][r] = report_data["by_reason"].get(r, 0) + 1

        (self.reports_dir / "candidates.json").write_text(
            json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _write_evidence_report(self, all_evidence: List[Dict[str, Any]]) -> None:
        report_data = {
            "total_evidence_collected": len(all_evidence),
            "evidence_items": all_evidence[:200],
        }
        (self.reports_dir / "vietnamese_evidence.json").write_text(
            json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
