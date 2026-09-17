"""Base DatasetAdapter abstract class."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
from music_dataset.schema import Track


class DatasetAdapter(ABC):
    dataset_name: str

    def __init__(
        self,
        raw_dir: Path = Path("data/raw"),
        output_dir: Path = Path("datasets"),
    ):
        self.raw_dir = Path(raw_dir) / self.dataset_name
        self.output_dir = Path(output_dir) / self.dataset_name
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "lyric").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "audio").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "avt").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "label").mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def inspect(self) -> Dict[str, Any]:
        """Inspect structure and availability of dataset assets."""
        pass

    @abstractmethod
    def discover_tracks(self, limit: Optional[int] = None) -> List[Track]:
        """Enumerate candidate tracks from raw or remote sources."""
        pass

    @abstractmethod
    def get_metadata(self, track: Track) -> Track:
        """Enrich and resolve metadata using precedence rules."""
        pass

    @abstractmethod
    def find_lyrics(self, track: Track) -> Optional[str]:
        """Find or extract lyrics."""
        pass

    @abstractmethod
    def get_audio(self, track: Track) -> Optional[Path]:
        """Locate or download normalized audio asset."""
        pass

    @abstractmethod
    def get_artwork(self, track: Track) -> Optional[Path]:
        """Extract or download cover art asset."""
        pass

    @abstractmethod
    def get_labels(self, track: Track) -> Dict[str, Any]:
        """Return standardized label dictionary."""
        pass
