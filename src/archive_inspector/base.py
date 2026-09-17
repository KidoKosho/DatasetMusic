"""Base interfaces and data structures for archive inspection."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ArchiveEntry:
    """Represents a single file or directory inside an archive."""
    filename: str
    size: int = 0
    compressed_size: int = 0
    is_dir: bool = False
    crc32: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "size": self.size,
            "compressed_size": self.compressed_size,
            "is_dir": self.is_dir,
            "crc32": self.crc32,
            "extra": self.extra,
        }


@dataclass
class ArchiveInfo:
    """Summary of inspected archive."""
    name: str
    size: int
    type: str  # "metadata", "audio", "lyrics", "other"
    remote_url: Optional[str] = None
    inspectable: bool = True
    remote_inspection: str = "supported"  # "supported", "unsupported", "local_only"
    total_entries: int = 0
    entries_sample: List[ArchiveEntry] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "size": self.size,
            "type": self.type,
            "remote_url": self.remote_url,
            "inspectable": self.inspectable,
            "remote_inspection": self.remote_inspection,
            "total_entries": self.total_entries,
            "entries_sample": [e.to_dict() for e in self.entries_sample[:50]],
            "notes": self.notes,
        }


class BaseArchiveInspector(ABC):
    """Abstract archive inspector."""

    @abstractmethod
    def inspect(self, target: Any) -> ArchiveInfo:
        """Inspect archive and return ArchiveInfo."""
        pass
