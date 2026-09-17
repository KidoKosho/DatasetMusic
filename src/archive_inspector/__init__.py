"""Archive Inspector module for inspecting local and remote archives without full download."""

from archive_inspector.base import ArchiveEntry, ArchiveInfo, BaseArchiveInspector
from archive_inspector.manifest import ManifestGenerator
from archive_inspector.remote_inspector import RemoteInspector
from archive_inspector.tar_inspector import TarInspector
from archive_inspector.zip_inspector import ZipInspector

__all__ = [
    "ArchiveEntry",
    "ArchiveInfo",
    "BaseArchiveInspector",
    "ZipInspector",
    "TarInspector",
    "RemoteInspector",
    "ManifestGenerator",
]
