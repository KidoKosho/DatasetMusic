"""Special tests for Vietnam Music Genre dataset semantics.

Critical Principle:
- MP3 without title -> MUST BE INGESTED
- MP3 without artist -> MUST BE INGESTED
- MP3 without lyrics -> MUST BE INGESTED
- MP3 without artwork -> MUST BE INGESTED
- Folder name = genre_original
- Audio tracks are 100% preserved.
"""

from pathlib import Path
from mutagen.id3 import ID3, TIT2
from music_dataset.constants import LanguageDetectionMethod, LanguageStatus
from music_dataset.datasets.vietnam_music_genre import VietnamMusicGenreAdapter


def _create_minimal_mp3(file_path: Path, title: str | None = None) -> None:
    frame = b"\xff\xfb\x90\x44" + (b"\x00" * 413)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(frame * 5)
    if title:
        id3 = ID3()
        id3.add(TIT2(encoding=3, text=[title]))
        id3.save(file_path)


def test_vietnam_music_genre_preserves_empty_metadata_tracks(tmp_path: Path):
    raw_staging = tmp_path / "raw" / "vietnam_music_genre"
    normalized_out = tmp_path / "datasets"

    # Create folder hierarchy:
    # Bolero/
    #   ├── 001_complete.mp3 (has title)
    #   └── 002_raw_no_meta.mp3 (no title, no artist, no lyrics, no artwork)
    # Pop/
    #   └── 999_nameless.mp3 (no tags at all)

    f1 = raw_staging / "Bolero" / "001_complete.mp3"
    f2 = raw_staging / "Bolero" / "002_raw_no_meta.mp3"
    f3 = raw_staging / "Pop" / "999_nameless.mp3"

    _create_minimal_mp3(f1, title="Duyên Phận")
    _create_minimal_mp3(f2, title=None)
    _create_minimal_mp3(f3, title=None)

    adapter = VietnamMusicGenreAdapter(raw_dir=raw_staging.parent, output_dir=normalized_out)
    tracks = adapter.discover_tracks()

    # Verify: All 3 tracks are preserved! Zero dropped!
    assert len(tracks) == 3

    track_map = {t.source_filename: t for t in tracks}

    # Track 1: Has title
    t1 = track_map["001_complete.mp3"]
    assert t1.title == "Duyên Phận"
    assert t1.genre_original == "Bolero"
    assert t1.genre == "bolero"
    assert t1.is_vietnamese_song is True
    assert t1.is_vietnamese_lyrics is None
    assert t1.language_status == LanguageStatus.DATASET_ASSERTED_VI.value
    assert t1.language_detection_method == LanguageDetectionMethod.DATASET_ASSERTION.value

    # Track 2: No title, no artist, no lyrics, no artwork -> STILL A VALID TRACK!
    t2 = track_map["002_raw_no_meta.mp3"]
    assert t2.title in ("raw_no_meta", "002_raw_no_meta", "002 Raw No Meta") or t2.title is None  # fallback
    assert t2.artist is None
    assert t2.lyrics is None
    assert t2.genre_original == "Bolero"
    assert t2.genre == "bolero"
    assert t2.is_vietnamese_song is True
    assert t2.is_vietnamese_lyrics is None
    assert t2.language_status == LanguageStatus.DATASET_ASSERTED_VI.value
    assert (normalized_out / "vietnam_music_genre" / "audio" / f"{t2.track_id}.mp3").exists()

    # Track 3: In Pop folder
    t3 = track_map["999_nameless.mp3"]
    assert t3.genre_original == "Pop"
    assert t3.genre == "pop"
    assert t3.is_vietnamese_song is True
    assert t3.lyrics is None
    assert t3.artwork_path is None
    assert (normalized_out / "vietnam_music_genre" / "audio" / f"{t3.track_id}.mp3").exists()


def test_vietnam_music_genre_segment_filename_parsing(tmp_path: Path):
    raw_staging = tmp_path / "raw" / "vietnam_music_genre"
    normalized_out = tmp_path / "datasets"

    f = raw_staging / "Pop" / "100YearsLOVESingle-NamDuc-6207759_hq_segment_7.mp3"
    _create_minimal_mp3(f, title=None)

    adapter = VietnamMusicGenreAdapter(raw_dir=raw_staging.parent, output_dir=normalized_out)
    tracks = adapter.discover_tracks()

    assert len(tracks) == 1
    t = tracks[0]
    assert "100 Years" in t.title
    assert "Nam Duc" in t.artist
    assert t.genre_original == "Pop"
    assert t.genre == "pop"
    assert t.is_vietnamese_song is True
    assert t.provenance.get("source_song_id") == "6207759"
    assert t.provenance.get("segment") == "7"
