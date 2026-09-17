"""Remote Endpoint Inspector discovering archives, checking Range support, and detecting anti-bot WAFs."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

from archive_inspector.base import ArchiveInfo
from archive_inspector.zip_inspector import ZipInspector
from archive_inspector.tar_inspector import TarInspector


class RemoteInspector:
    """Dispatches remote archive inspection via HTTP HEAD, Range testing, and content negotiation."""

    def __init__(self, timeout: int = 15, user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"):
        self.timeout = timeout
        self.user_agent = user_agent
        self.zip_inspector = ZipInspector(timeout=timeout, user_agent=user_agent)
        self.tar_inspector = TarInspector(timeout=timeout, user_agent=user_agent)

    def probe_url(self, url: str) -> Dict[str, Any]:
        """Send HEAD request to probe status, size, accept-ranges, and content type."""
        headers = {"User-Agent": self.user_agent}
        try:
            r = requests.head(url, headers=headers, timeout=self.timeout, allow_redirects=True)
            return {
                "url": url,
                "status_code": r.status_code,
                "content_length": int(r.headers.get("Content-Length", 0)),
                "content_type": r.headers.get("Content-Type", ""),
                "accept_ranges": r.headers.get("Accept-Ranges", ""),
                "supports_range": "bytes" in r.headers.get("Accept-Ranges", "").lower(),
                "error": None,
            }
        except Exception as e:
            return {
                "url": url,
                "status_code": 0,
                "content_length": 0,
                "content_type": "",
                "accept_ranges": "",
                "supports_range": False,
                "error": str(e),
            }

    def inspect_archive(self, url_or_path: str, archive_type: str = "archive") -> ArchiveInfo:
        """Inspect archive based on extension and protocol."""
        clean_target = url_or_path.split("?")[0].lower()
        if clean_target.endswith(".zip"):
            return self.zip_inspector.inspect(url_or_path, archive_type=archive_type)
        elif clean_target.endswith(".tar.gz") or clean_target.endswith(".tgz") or clean_target.endswith(".tar"):
            return self.tar_inspector.inspect(url_or_path, archive_type=archive_type)
        else:
            # Generic endpoint inspection
            probe = self.probe_url(url_or_path)
            name = url_or_path.split("/")[-1].split("?")[0] or "endpoint"
            if probe["status_code"] == 200:
                return ArchiveInfo(
                    name=name,
                    size=probe["content_length"],
                    type=archive_type,
                    remote_url=url_or_path,
                    inspectable=probe["supports_range"],
                    remote_inspection="supported" if probe["supports_range"] else "unsupported",
                    notes=[f"Content-Type: {probe['content_type']}"],
                )
            else:
                return ArchiveInfo(
                    name=name,
                    size=0,
                    type=archive_type,
                    remote_url=url_or_path,
                    inspectable=False,
                    remote_inspection="unsupported",
                    notes=[f"Endpoint probe returned status {probe['status_code']} (Error: {probe['error']})"],
                )
