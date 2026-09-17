"""Tests for ID3 tag parsing and artwork extraction."""

from pathlib import Path
from mutagen.id3 import APIC, ID3, TALB, TCON, TDRC, TIT2, TPE1
from music_dataset.metadata.id3_parser import ID3Parser


def _create_dummy_mp3(file_path: Path, with_tags: bool = True) -> Path:
    # Minimal MPEG 1 Layer 3 audio frames
    frame = b"\xff\xfb\x90\x44" + (b"\x00" * 413)
    file_path.write_bytes(frame * 5)
    if with_tags:
        id3 = ID3()
        id3.add(TIT2(encoding=3, text=["Diễm Xưa"]))
        id3.add(TPE1(encoding=3, text=["Khánh Ly"]))
        id3.add(TALB(encoding=3, text=["Sơn Ca 7"]))
        id3.add(TCON(encoding=3, text=["Nhạc Trịnh"]))
        id3.add(TDRC(encoding=3, text=["1974"]))
        # Add 1x1 dummy JPEG artwork
        dummy_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        id3.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=dummy_jpeg))
        id3.save(file_path)
    return file_path


def test_parse_complete_id3(tmp_path: Path):
    mp3_file = tmp_path / "song.mp3"
    _create_dummy_mp3(mp3_file, with_tags=True)

    res = ID3Parser.parse_file(mp3_file)
    assert res.has_id3 is True
    assert res.title == "Diễm Xưa"
    assert res.artist == "Khánh Ly"
    assert res.album == "Sơn Ca 7"
    assert res.genre == "Nhạc Trịnh"
    assert res.year == 1974
    assert res.artwork_bytes is not None
    assert res.artwork_mime == "image/jpeg"


def test_parse_mp3_without_tags(tmp_path: Path):
    mp3_file = tmp_path / "untagged.mp3"
    _create_dummy_mp3(mp3_file, with_tags=False)

    res = ID3Parser.parse_file(mp3_file)
    assert res.title is None
    assert res.artist is None
    assert res.artwork_bytes is None
