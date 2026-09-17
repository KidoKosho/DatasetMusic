"""TAR/GZ archive inspector supporting local archive examination and remote endpoint validation."""

from pathlib import Path
import tarfile
from typing import List, Optional, Union
import requests

from archive_inspector.base import ArchiveEntry, ArchiveInfo, BaseArchiveInspector


class TarInspector(BaseArchiveInspector):
    """Inspects TAR/GZ archives."""

    def __init__(self, timeout: int = 15, user_agent: str = "Mozilla/5.0"):
        self.timeout = timeout
        self.user_agent = user_agent

    def inspect(self, target: Union[str, Path], archive_type: str = "archive") -> ArchiveInfo:
        target_str = str(target)
        if target_str.startswith("http://") or target_str.startswith("https://"):
            return self.inspect_remote(target_str, archive_type=archive_type)
        else:
            return self.inspect_local(Path(target), archive_type=archive_type)

    def inspect_local(self, path: Path, archive_type: str = "archive") -> ArchiveInfo:
        if not path.exists():
            return ArchiveInfo(
                name=path.name,
                size=0,
                type=archive_type,
                inspectable=False,
                remote_inspection="local_not_found",
                notes=[f"Local archive not found: {path}"],
            )

        file_size = path.stat().st_size
        entries: List[ArchiveEntry] = []
        try:
            with tarfile.open(path, "r:*") as tf:
                members = tf.getmembers()
                for m in members:
                    entries.append(
                        ArchiveEntry(
                            filename=m.name,
                            size=m.size,
                            compressed_size=0,
                            is_dir=m.isdir(),
                        )
                    )
            return ArchiveInfo(
                name=path.name,
                size=file_size,
                type=archive_type,
                inspectable=True,
                remote_inspection="local_inspected",
                total_entries=len(entries),
                entries_sample=entries[:50],
                notes=[f"Locally inspected {len(entries)} TAR members."],
            )
        except Exception as e:
            return ArchiveInfo(
                name=path.name,
                size=file_size,
                type=archive_type,
                inspectable=False,
                remote_inspection="error",
                notes=[f"Failed to read local TAR archive: {e}"],
            )

    def inspect_remote(self, url: str, archive_type: str = "archive") -> ArchiveInfo:
        name = url.split("?")[0].split("/")[-1]
        headers = {"User-Agent": self.user_agent}

        try:
            head_res = requests.head(url, headers=headers, timeout=self.timeout, allow_redirects=True)
        except Exception as e:
            return ArchiveInfo(
                name=name,
                size=0,
                type=archive_type,
                remote_url=url,
                inspectable=False,
                remote_inspection="unsupported",
                notes=[f"Remote host unreachable: {e}"],
            )

        if head_res.status_code != 200:
            return ArchiveInfo(
                name=name,
                size=0,
                type=archive_type,
                remote_url=url,
                inspectable=False,
                remote_inspection="unsupported",
                notes=[f"HTTP HEAD returned {head_res.status_code}"],
            )

        total_size = int(head_res.headers.get("Content-Length", 0))
        # TAR headers are sequential, so random directory listing without full streaming is generally unsupported
        return ArchiveInfo(
            name=name,
            size=total_size,
            type=archive_type,
            remote_url=url,
            inspectable=False,
            remote_inspection="unsupported",
            notes=["TAR archives require sequential streaming; random listing is unsupported."],
        )
