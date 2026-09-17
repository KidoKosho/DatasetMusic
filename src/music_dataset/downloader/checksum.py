"""Checksum calculation and verification utilities."""

import hashlib
from pathlib import Path
from typing import Optional


def compute_file_sha256(file_path: Path, chunk_size: int = 1048576) -> str:
    """Calculate SHA-256 hash of a file efficiently using streaming chunks."""
    h = hashlib.sha256()
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def verify_file_checksum(file_path: Path, expected_sha256: str) -> bool:
    """Verify if file matches expected SHA-256 hash."""
    if not expected_sha256:
        return True
    actual = compute_file_sha256(file_path)
    return actual.lower() == expected_sha256.lower().strip()
