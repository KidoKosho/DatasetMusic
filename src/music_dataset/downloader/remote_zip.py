"""Remote Zip Archive single-file extractor using HTTP Range requests.

Allows fetching Central Directory without downloading the archive,
and extracting individual files directly by their local header offset.
Supports STORED (0), DEFLATE (8), and BZIP2 (12) compression methods,
including ZIP64 large file extensions.
"""

import bz2
import io
from pathlib import Path
import struct
from typing import Dict, List, Optional, Tuple
import zlib
import requests

import zipfile
from rich.console import Console

from music_dataset.downloader.checksum import compute_file_sha256

console = Console(highlight=False)


class RemoteZipMember:
    """Metadata for an individual entry in a remote ZIP archive."""

    def __init__(
        self,
        filename: str,
        comp_method: int,
        comp_size: int,
        uncomp_size: int,
        offset: int,
        crc32: int,
    ):
        self.filename = filename
        self.comp_method = comp_method
        self.comp_size = comp_size
        self.uncomp_size = uncomp_size
        self.offset = offset
        self.crc32 = crc32

    def __repr__(self) -> str:
        return f"<RemoteZipMember {self.filename} ({self.uncomp_size} bytes)>"


class RemoteZipExtractor:
    """Extracts individual files from a remote ZIP archive via HTTP Range requests."""

    def __init__(
        self,
        url: str,
        timeout: int = 30,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    ):
        self.url = url
        self.timeout = timeout
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.entries: Dict[str, RemoteZipMember] = {}
        self._total_size: Optional[int] = None

    def fetch_index(
        self,
        known_cd_offset: Optional[int] = None,
        known_cd_size: Optional[int] = None,
    ) -> Dict[str, RemoteZipMember]:
        """Fetches the Central Directory and indexes all member files."""
        if self.entries:
            return self.entries

        cd_offset = known_cd_offset
        cd_size = known_cd_size

        # If not provided, discover EOCD / Zip64 EOCD from the tail of the remote file
        if cd_offset is None or cd_size is None:
            cd_offset, cd_size = self._discover_central_directory()

        # Fetch Central Directory bytes
        headers = {"Range": f"bytes={cd_offset}-{cd_offset + cd_size - 1}"}
        res = self.session.get(self.url, headers=headers, timeout=self.timeout)
        if res.status_code not in (200, 206):
            raise RuntimeError(f"Failed to fetch Central Directory: HTTP {res.status_code}")

        cd_data = res.content
        pos = 0
        while pos < len(cd_data) - 46:
            if cd_data[pos:pos + 4] != b"PK\x01\x02":
                break
            vals = struct.unpack(zipfile.structCentralDir, cd_data[pos:pos + 46])
            comp_method = vals[6]
            crc32 = vals[9]
            comp_size = vals[10]
            uncomp_size = vals[11]
            flen = vals[12]
            xlen = vals[13]
            clen = vals[14]
            loc_offset = vals[18]

            fname = cd_data[pos + 46:pos + 46 + flen].decode("utf-8", errors="replace")
            extra = cd_data[pos + 46 + flen:pos + 46 + flen + xlen]

            actual_uncomp = uncomp_size
            actual_comp = comp_size
            actual_offset = loc_offset

            while len(extra) >= 4:
                tag, blen = struct.unpack("<HH", extra[:4])
                if tag == 1:  # Zip64 extra
                    zdata = extra[4:4 + blen]
                    try:
                        if actual_uncomp in (0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
                            actual_uncomp, = struct.unpack("<Q", zdata[:8])
                            zdata = zdata[8:]
                        if actual_comp == 0xFFFFFFFF:
                            actual_comp, = struct.unpack("<Q", zdata[:8])
                            zdata = zdata[8:]
                        if actual_offset == 0xFFFFFFFF:
                            actual_offset, = struct.unpack("<Q", zdata[:8])
                            zdata = zdata[8:]
                    except struct.error:
                        pass
                    break
                extra = extra[4 + blen:]

            self.entries[fname] = RemoteZipMember(
                filename=fname,
                comp_method=comp_method,
                comp_size=actual_comp,
                uncomp_size=actual_uncomp,
                offset=actual_offset,
                crc32=crc32,
            )
            pos += 46 + flen + xlen + clen

        return self.entries

    def _discover_central_directory(self) -> Tuple[int, int]:
        """Discovers Central Directory offset and size by reading the tail of the archive."""
        head_res = self.session.head(self.url, allow_redirects=True, timeout=self.timeout)
        if head_res.status_code != 200:
            raise RuntimeError(f"HEAD request failed: HTTP {head_res.status_code}")
        total_size = int(head_res.headers.get("Content-Length", 0))
        self._total_size = total_size

        read_size = min(65536, total_size)
        start_byte = total_size - read_size
        headers = {"Range": f"bytes={start_byte}-{total_size - 1}"}
        tail_res = self.session.get(self.url, headers=headers, timeout=self.timeout)
        data = tail_res.content

        eocd_pos = data.rfind(b"PK\x05\x06")
        if eocd_pos == -1:
            raise RuntimeError("EOCD signature not found in remote archive")

        eocd_data = data[eocd_pos:eocd_pos + 22]
        _, _, _, _, total_entries, cd_size, cd_offset, _ = struct.unpack("<4sHHHHIIH", eocd_data)

        # Check for Zip64 Locator
        zip64_loc_pos = data.rfind(b"PK\x06\x07", 0, eocd_pos)
        if zip64_loc_pos != -1:
            loc_data = data[zip64_loc_pos:zip64_loc_pos + 20]
            _, _, zip64_eocd_offset, _ = struct.unpack("<4sIQI", loc_data)
            # Read Zip64 EOCD Record (56 bytes)
            z64_res = self.session.get(
                self.url,
                headers={"Range": f"bytes={zip64_eocd_offset}-{zip64_eocd_offset + 55}"},
                timeout=self.timeout,
            )
            z64_data = z64_res.content
            if z64_data.startswith(b"PK\x06\x06"):
                _, _, _, _, _, _, _, _, cd_size, cd_offset = struct.unpack("<4sQHHIIQQQQ", z64_data[:56])

        return cd_offset, cd_size

    def extract_file(self, member_path: str, dest_path: Path) -> bool:
        """Extracts a single member file by requesting only its byte range."""
        if not self.entries:
            self.fetch_index()

        # Check exact or normalized path
        norm_key = member_path.replace("\\", "/")
        member = self.entries.get(norm_key)
        if not member:
            # Try finding suffix match
            for k, v in self.entries.items():
                if k.endswith(norm_key):
                    member = v
                    break
        if not member:
            return False

        # Request local header + compressed data
        loc_off = member.offset
        fetch_len = 256 + member.comp_size
        headers = {"Range": f"bytes={loc_off}-{loc_off + fetch_len - 1}"}
        res = self.session.get(self.url, headers=headers, timeout=self.timeout)
        if res.status_code not in (200, 206):
            return False

        fdata = res.content
        if not fdata.startswith(b"PK\x03\x04"):
            return False

        loc_flen, loc_xlen = struct.unpack("<HH", fdata[26:30])
        comp_data = fdata[30 + loc_flen + loc_xlen: 30 + loc_flen + loc_xlen + member.comp_size]

        # Decompress
        if member.comp_method == 0:  # STORED
            raw_bytes = comp_data
        elif member.comp_method == 8:  # DEFLATE
            raw_bytes = zlib.decompress(comp_data, -15)
        elif member.comp_method == 12:  # BZIP2
            raw_bytes = bz2.decompress(comp_data)
        else:
            raise ValueError(f"Unsupported compression method {member.comp_method} for {member_path}")

        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(raw_bytes)
        return True
