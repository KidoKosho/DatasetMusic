"""Safe resume manager checking HTTP Range support and handling .part files."""

from pathlib import Path
from typing import Dict, Optional, Tuple


class ResumeManager:
    @staticmethod
    def get_part_file(destination: Path) -> Path:
        """Return the temporary .part path for a destination file."""
        dest = Path(destination)
        return dest.parent / f"{dest.name}.part"

    @staticmethod
    def prepare_resume(destination: Path, resume_enabled: bool = True) -> Tuple[Path, int, Dict[str, str]]:
        """
        Check if .part exists and prepare Range headers if resume is enabled.
        Returns: (part_path, existing_size, headers)
        """
        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        part_path = ResumeManager.get_part_file(dest)

        if not resume_enabled:
            if part_path.exists():
                part_path.unlink()
            return part_path, 0, {}

        if part_path.exists() and part_path.stat().st_size > 0:
            existing_size = part_path.stat().st_size
            headers = {"Range": f"bytes={existing_size}-"}
            return part_path, existing_size, headers

        return part_path, 0, {}

    @staticmethod
    def handle_server_range_response(
        part_path: Path,
        status_code: int,
        existing_size: int,
    ) -> Tuple[str, int]:
        """
        Inspect server response status code:
        - 206 Partial Content: Resume is supported -> append ('ab')
        - 200 OK: Resume is NOT supported -> remove .part and start fresh ('wb')
        - 416 Range Not Satisfiable: File might already be fully downloaded or invalid range
        """
        if status_code == 206:
            return "ab", existing_size
        else:
            # Server sent full content or does not support Range. Truncate to avoid corrupt duplicate
            if part_path.exists():
                part_path.unlink()
            return "wb", 0
