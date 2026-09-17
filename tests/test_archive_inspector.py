"""Tests for Archive Inspector module."""

import zipfile
from pathlib import Path
import pytest

from archive_inspector.base import ArchiveEntry, ArchiveInfo
from archive_inspector.zip_inspector import ZipInspector
from archive_inspector.tar_inspector import TarInspector
from archive_inspector.manifest import ManifestGenerator


def test_zip_inspector_local(tmp_path: Path):
    zip_path = tmp_path / "test_archive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("subfolder/file1.txt", "Hello world from file 1")
        zf.writestr("subfolder/file2.mp3", b"\x00" * 100)

    inspector = ZipInspector()
    info = inspector.inspect_local(zip_path, archive_type="test")

    assert info.inspectable is True
    assert info.total_entries == 2
    assert len(info.entries_sample) == 2
    filenames = [e.filename for e in info.entries_sample]
    assert "subfolder/file1.txt" in filenames
    assert "subfolder/file2.mp3" in filenames


def test_zip_inspector_missing_file(tmp_path: Path):
    inspector = ZipInspector()
    info = inspector.inspect_local(tmp_path / "non_existent.zip")
    assert info.inspectable is False
    assert info.remote_inspection == "local_not_found"


def test_manifest_generator_paths(tmp_path: Path):
    gen = ManifestGenerator(manifests_dir=tmp_path)
    kaggle_p = gen.generate_kaggle_manifest()
    assert kaggle_p.exists()
    assert kaggle_p.name == "vietnam_music_genre_archives.json"
