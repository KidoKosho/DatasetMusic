"""Artwork extractor extracting embedded APIC images from MP3 files."""

from pathlib import Path
from typing import Optional
from music_dataset.metadata.id3_parser import ID3Parser


class ArtworkExtractor:
    @staticmethod
    def extract_from_file(
        audio_file_path: Path,
        output_dir: Path,
        track_id: str,
    ) -> Optional[Path]:
        """
        Extract embedded APIC image from MP3 and write to output_dir / {track_id}.jpg.
        Returns the created image path or None if no artwork found.
        """
        audio_path = Path(audio_file_path)
        if not audio_path.exists():
            return None

        parsed = ID3Parser.parse_file(audio_path)
        if not parsed.artwork_bytes:
            return None

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Detect extension from mime
        ext = ".jpg"
        if parsed.artwork_mime and "png" in parsed.artwork_mime.lower():
            ext = ".png"

        target_file = out_dir / f"{track_id}{ext}"
        target_file.write_bytes(parsed.artwork_bytes)
        return target_file
