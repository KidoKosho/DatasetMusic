"""SQLite State Database for resumable pipeline execution."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from music_dataset.schema import Track


class StateDatabase:
    def __init__(self, db_path: Path = Path("data/state/datasets.db")):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'pending',
                    total_tracks INTEGER DEFAULT 0,
                    last_inspected_at TEXT,
                    created_at TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS tracks (
                    track_id TEXT PRIMARY KEY,
                    dataset TEXT NOT NULL,
                    source_id TEXT,
                    source_url TEXT,
                    title TEXT,
                    artist TEXT,
                    album TEXT,
                    year INTEGER,
                    genre TEXT,
                    genre_original TEXT,
                    lyrics TEXT,
                    is_vietnamese_song INTEGER,
                    is_vietnamese_lyrics INTEGER,
                    language_status TEXT,
                    language_confidence REAL,
                    language_detection_method TEXT,
                    language_evidence_json TEXT,
                    audio_path TEXT,
                    artwork_path TEXT,
                    source_filename TEXT,
                    source_relative_path TEXT,
                    metadata_status TEXT,
                    lyrics_status TEXT,
                    audio_status TEXT,
                    artwork_status TEXT,
                    sha256 TEXT,
                    provenance_json TEXT,
                    enrichment_json TEXT,
                    vietnamese_relevance_json TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

            # Safe migration for existing DB
            cur.execute("PRAGMA table_info(tracks)")
            cols = [r[1] for r in cur.fetchall()]
            if "enrichment_json" not in cols:
                cur.execute("ALTER TABLE tracks ADD COLUMN enrichment_json TEXT")
            if "vietnamese_relevance_json" not in cols:
                cur.execute("ALTER TABLE tracks ADD COLUMN vietnamese_relevance_json TEXT")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id TEXT,
                    url TEXT,
                    destination TEXT,
                    status TEXT,
                    attempts INTEGER DEFAULT 0,
                    bytes_downloaded INTEGER DEFAULT 0,
                    total_bytes INTEGER DEFAULT 0,
                    sha256 TEXT,
                    http_status INTEGER,
                    error TEXT,
                    started_at TEXT,
                    finished_at TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS artworks (
                    track_id TEXT PRIMARY KEY,
                    source TEXT,
                    artwork_path TEXT,
                    status TEXT,
                    extracted_at TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS lyrics (
                    track_id TEXT PRIMARY KEY,
                    source TEXT,
                    source_url TEXT,
                    status TEXT,
                    fetched_at TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id TEXT,
                    dataset TEXT,
                    operation TEXT,
                    error_type TEXT,
                    status_code INTEGER,
                    message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    timestamp TEXT
                )
            """)
            conn.commit()

    def upsert_track(self, track: Track) -> None:
        """Insert or update a Track in SQLite."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO tracks (
                    track_id, dataset, source_id, source_url, title, artist, album,
                    year, genre, genre_original, lyrics, is_vietnamese_song,
                    is_vietnamese_lyrics, language_status, language_confidence,
                    language_detection_method, language_evidence_json,
                    audio_path, artwork_path, source_filename, source_relative_path,
                    metadata_status, lyrics_status, audio_status, artwork_status,
                    sha256, provenance_json, enrichment_json, vietnamese_relevance_json,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(track_id) DO UPDATE SET
                    title=COALESCE(excluded.title, tracks.title),
                    artist=COALESCE(excluded.artist, tracks.artist),
                    album=COALESCE(excluded.album, tracks.album),
                    year=COALESCE(excluded.year, tracks.year),
                    genre=COALESCE(excluded.genre, tracks.genre),
                    genre_original=COALESCE(excluded.genre_original, tracks.genre_original),
                    lyrics=COALESCE(excluded.lyrics, tracks.lyrics),
                    is_vietnamese_song=COALESCE(excluded.is_vietnamese_song, tracks.is_vietnamese_song),
                    is_vietnamese_lyrics=COALESCE(excluded.is_vietnamese_lyrics, tracks.is_vietnamese_lyrics),
                    language_status=excluded.language_status,
                    language_confidence=COALESCE(excluded.language_confidence, tracks.language_confidence),
                    language_detection_method=COALESCE(excluded.language_detection_method, tracks.language_detection_method),
                    language_evidence_json=COALESCE(excluded.language_evidence_json, tracks.language_evidence_json),
                    audio_path=COALESCE(excluded.audio_path, tracks.audio_path),
                    artwork_path=COALESCE(excluded.artwork_path, tracks.artwork_path),
                    metadata_status=excluded.metadata_status,
                    lyrics_status=excluded.lyrics_status,
                    audio_status=excluded.audio_status,
                    artwork_status=excluded.artwork_status,
                    sha256=COALESCE(excluded.sha256, tracks.sha256),
                    provenance_json=COALESCE(excluded.provenance_json, tracks.provenance_json),
                    enrichment_json=COALESCE(excluded.enrichment_json, tracks.enrichment_json),
                    vietnamese_relevance_json=COALESCE(excluded.vietnamese_relevance_json, tracks.vietnamese_relevance_json),
                    updated_at=?
            """, (
                track.track_id, track.dataset, track.source_id, track.source_url,
                track.title, track.artist, track.album, track.year,
                track.genre, track.genre_original, track.lyrics,
                1 if track.is_vietnamese_song is True else (0 if track.is_vietnamese_song is False else None),
                1 if track.is_vietnamese_lyrics is True else (0 if track.is_vietnamese_lyrics is False else None),
                track.language_status, track.language_confidence, track.language_detection_method,
                json.dumps(track.language_evidence, ensure_ascii=False),
                track.audio_path, track.artwork_path, track.source_filename, track.source_relative_path,
                track.metadata_status, track.lyrics_status, track.audio_status, track.artwork_status,
                track.sha256, json.dumps(track.provenance, ensure_ascii=False),
                json.dumps(track.enrichment, ensure_ascii=False),
                json.dumps(track.vietnamese_relevance, ensure_ascii=False),
                track.created_at, track.updated_at,
                now,
            ))
            conn.commit()

    def get_track(self, track_id: str) -> Optional[Track]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM tracks WHERE track_id = ?", (track_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_track(row)

    def list_tracks(
        self,
        dataset: Optional[str] = None,
        language_status: Optional[str] = None,
        genre: Optional[str] = None,
        has_lyrics: Optional[bool] = None,
        has_audio: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> List[Track]:
        query = "SELECT * FROM tracks WHERE 1=1"
        params: List[Any] = []
        if dataset:
            query += " AND dataset = ?"
            params.append(dataset)
        if language_status:
            query += " AND language_status = ?"
            params.append(language_status)
        if genre:
            query += " AND (genre = ? OR genre_original = ?)"
            params.extend([genre, genre])
        if has_lyrics is True:
            query += " AND lyrics IS NOT NULL AND lyrics != ''"
        elif has_lyrics is False:
            query += " AND (lyrics IS NULL OR lyrics = '')"
        if has_audio is True:
            query += " AND audio_path IS NOT NULL AND audio_path != ''"
        elif has_audio is False:
            query += " AND (audio_path IS NULL OR audio_path = '')"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, tuple(params))
            return [self._row_to_track(r) for r in cur.fetchall()]

    def record_download(
        self,
        track_id: str,
        url: str,
        destination: str,
        status: str,
        attempts: int = 1,
        bytes_downloaded: int = 0,
        total_bytes: int = 0,
        sha256: Optional[str] = None,
        http_status: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO downloads (
                    track_id, url, destination, status, attempts,
                    bytes_downloaded, total_bytes, sha256, http_status,
                    error, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                track_id, url, destination, status, attempts,
                bytes_downloaded, total_bytes, sha256, http_status,
                error, now, now if status in ("downloaded", "failed", "skipped") else None
            ))
            conn.commit()

    def record_error(
        self,
        track_id: Optional[str],
        dataset: str,
        operation: str,
        error_type: str,
        status_code: Optional[int] = None,
        message: str = "",
        retry_count: int = 0,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO errors (
                    track_id, dataset, operation, error_type, status_code,
                    message, retry_count, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (track_id, dataset, operation, error_type, status_code, message, retry_count, now))
            conn.commit()

    def _row_to_track(self, row: sqlite3.Row) -> Track:
        d = dict(row)
        return Track(
            track_id=d["track_id"],
            dataset=d["dataset"],
            source_id=d["source_id"] or "",
            source_url=d["source_url"] or "",
            title=d["title"],
            artist=d["artist"],
            album=d["album"],
            year=d["year"],
            genre=d["genre"],
            genre_original=d["genre_original"],
            lyrics=d["lyrics"],
            is_vietnamese_song=(
                True if d["is_vietnamese_song"] == 1
                else (False if d["is_vietnamese_song"] == 0 else None)
            ),
            is_vietnamese_lyrics=(
                True if d["is_vietnamese_lyrics"] == 1
                else (False if d["is_vietnamese_lyrics"] == 0 else None)
            ),
            language_status=d["language_status"],
            language_confidence=d["language_confidence"],
            language_detection_method=d["language_detection_method"],
            language_evidence=json.loads(d["language_evidence_json"] or "{}"),
            audio_path=d["audio_path"],
            artwork_path=d["artwork_path"],
            source_filename=d["source_filename"],
            source_relative_path=d["source_relative_path"],
            metadata_status=d["metadata_status"],
            lyrics_status=d["lyrics_status"],
            audio_status=d["audio_status"],
            artwork_status=d["artwork_status"],
            sha256=d["sha256"],
            provenance=json.loads(d["provenance_json"] or "{}"),
            enrichment=json.loads(d.get("enrichment_json") or "{\"msd\": {}, \"fma\": {}, \"upf\": {}}"),
            vietnamese_relevance=json.loads(d.get("vietnamese_relevance_json") or "{\"status\": \"unknown\", \"confidence\": 0.0, \"evidence\": []}"),
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )
