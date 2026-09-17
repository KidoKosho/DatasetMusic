"""Zip archive inspector supporting both local files and remote HTTP Range inspection."""

import io
from pathlib import Path
import struct
from typing import List, Optional, Tuple, Union
import zipfile
import requests

from archive_inspector.base import ArchiveEntry, ArchiveInfo, BaseArchiveInspector


class ZipInspector(BaseArchiveInspector):
    """Inspects ZIP archives locally or remotely without downloading the full archive."""

    def __init__(self, timeout: int = 15, user_agent: str = "Mozilla/5.0"):
        self.timeout = timeout
        self.user_agent = user_agent

    def inspect(self, target: Union[str, Path], archive_type: str = "archive") -> ArchiveInfo:
        """Inspect a local file path or remote HTTP(S) URL."""
        target_str = str(target)
        if target_str.startswith("http://") or target_str.startswith("https://"):
            return self.inspect_remote(target_str, archive_type=archive_type)
        else:
            return self.inspect_local(Path(target), archive_type=archive_type)

    def inspect_local(self, path: Path, archive_type: str = "archive") -> ArchiveInfo:
        """Inspect a local ZIP file using standard library."""
        if not path.exists():
            return ArchiveInfo(
                name=path.name,
                size=0,
                type=archive_type,
                inspectable=False,
                remote_inspection="local_not_found",
                notes=[f"Local file does not exist: {path}"],
            )

        file_size = path.stat().st_size
        entries: List[ArchiveEntry] = []
        try:
            with zipfile.ZipFile(path, "r") as zf:
                infolist = zf.infolist()
                for info in infolist:
                    entries.append(
                        ArchiveEntry(
                            filename=info.filename,
                            size=info.file_size,
                            compressed_size=info.compress_size,
                            is_dir=info.is_dir(),
                            crc32=info.CRC,
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
                notes=[f"Locally inspected {len(entries)} entries."],
            )
        except Exception as e:
            return ArchiveInfo(
                name=path.name,
                size=file_size,
                type=archive_type,
                inspectable=False,
                remote_inspection="error",
                notes=[f"Error reading local ZIP: {e}"],
            )

    def inspect_remote(self, url: str, archive_type: str = "archive") -> ArchiveInfo:
        """Inspect a remote ZIP archive using HTTP HEAD and Range requests on Central Directory."""
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
                notes=[f"Network error on HEAD request: {e}"],
            )

        if head_res.status_code != 200:
            return ArchiveInfo(
                name=name,
                size=0,
                type=archive_type,
                remote_url=url,
                inspectable=False,
                remote_inspection="unsupported",
                notes=[f"HTTP HEAD returned status {head_res.status_code}"],
            )

        total_size = int(head_res.headers.get("Content-Length", 0))
        accept_ranges = head_res.headers.get("Accept-Ranges", "").lower()
        if "bytes" not in accept_ranges and total_size > 0:
            # Server does not advertise Range support
            return ArchiveInfo(
                name=name,
                size=total_size,
                type=archive_type,
                remote_url=url,
                inspectable=False,
                remote_inspection="unsupported",
                notes=["Server does not declare Accept-Ranges: bytes support."],
            )

        # Attempt to read last 65536 bytes to find End of Central Directory (EOCD)
        read_size = min(65536, total_size) if total_size > 0 else 65536
        start_byte = (total_size - read_size) if total_size > 0 else 0
        range_header = {"Range": f"bytes={start_byte}-{total_size - 1}"} if total_size > 0 else {"Range": "bytes=-65536"}
        range_header["User-Agent"] = self.user_agent

        try:
            tail_res = requests.get(url, headers=range_header, timeout=self.timeout)
        except Exception as e:
            return ArchiveInfo(
                name=name,
                size=total_size,
                type=archive_type,
                remote_url=url,
                inspectable=False,
                remote_inspection="unsupported",
                notes=[f"Failed to fetch tail Range: {e}"],
            )

        if tail_res.status_code not in (200, 206):
            return ArchiveInfo(
                name=name,
                size=total_size,
                type=archive_type,
                remote_url=url,
                inspectable=False,
                remote_inspection="unsupported",
                notes=[f"Tail range request returned status {tail_res.status_code}, remote_inspection = unsupported."],
            )

        tail_data = tail_res.content
        eocd_pos = tail_data.rfind(b"PK\x05\x06")
        if eocd_pos == -1:
            return ArchiveInfo(
                name=name,
                size=total_size,
                type=archive_type,
                remote_url=url,
                inspectable=False,
                remote_inspection="unsupported",
                notes=["EOCD signature PK\\x05\\x06 not found in tail buffer."],
            )

        # Parse standard EOCD record
        eocd_data = tail_data[eocd_pos:eocd_pos + 22]
        if len(eocd_data) < 22:
            return ArchiveInfo(
                name=name,
                size=total_size,
                type=archive_type,
                remote_url=url,
                inspectable=False,
                remote_inspection="unsupported",
                notes=["Truncated EOCD record."],
            )

        sig, disk_num, cd_disk, entries_disk, total_entries, cd_size, cd_offset, comment_len = struct.unpack(
            "<4sHHHHIIH", eocd_data
        )

        # Check for Zip64 Locator if offsets overflow 0xFFFFFFFF
        zip64_loc_pos = tail_data.rfind(b"PK\x06\x07", 0, eocd_pos)
        if zip64_loc_pos != -1:
            loc_data = tail_data[zip64_loc_pos:zip64_loc_pos + 20]
            if len(loc_data) >= 20:
                sig64, disk64, zip64_eocd_offset, total_disks64 = struct.unpack("<4sIQI", loc_data)
                # Fetch Zip64 EOCD Record
                z64_req = requests.get(
                    url,
                    headers={"Range": f"bytes={zip64_eocd_offset}-{zip64_eocd_offset + 55}", "User-Agent": self.user_agent},
                    timeout=self.timeout,
                )
                if z64_req.status_code in (200, 206) and z64_req.content.startswith(b"PK\x06\x06"):
                    z64_data = z64_req.content[:56]
                    _, rec_size, v1, v2, d1, d2, ent_disk, total_entries, cd_size, cd_offset = struct.unpack(
                        "<4sQHHIIQQQQ", z64_data
                    )

        # Fetch Central Directory entries via Range
        # To avoid unbounded memory consumption on gigantic archives, we fetch a representative chunk (up to 512KB)
        fetch_len = min(cd_size, 524288)
        cd_req = requests.get(
            url,
            headers={"Range": f"bytes={cd_offset}-{cd_offset + fetch_len - 1}", "User-Agent": self.user_agent},
            timeout=self.timeout,
        )

        entries: List[ArchiveEntry] = []
        if cd_req.status_code in (200, 206):
            cd_buf = cd_req.content
            pos = 0
            while pos < len(cd_buf) - 46:
                if cd_buf[pos:pos + 4] != b"PK\x01\x02":
                    break
                flen, xlen, clen = struct.unpack("<HHH", cd_buf[pos + 28:pos + 34])
                uncomp_size = struct.unpack("<I", cd_buf[pos + 24:pos + 28])[0]
                comp_size = struct.unpack("<I", cd_buf[pos + 20:pos + 24])[0]
                fname = cd_buf[pos + 46:pos + 46 + flen].decode("utf-8", errors="replace")
                is_dir = fname.endswith("/")
                entries.append(
                    ArchiveEntry(
                        filename=fname,
                        size=uncomp_size,
                        compressed_size=comp_size,
                        is_dir=is_dir,
                    )
                )
                pos += 46 + flen + xlen + clen

        return ArchiveInfo(
            name=name,
            size=total_size,
            type=archive_type,
            remote_url=url,
            inspectable=True,
            remote_inspection="supported",
            total_entries=total_entries if total_entries > 0 else len(entries),
            entries_sample=entries[:50],
            notes=[
                f"Successfully parsed remote Central Directory via HTTP Range.",
                f"Total archive entries: {total_entries}.",
                f"Parsed sample: {len(entries)} file paths.",
            ],
        )
