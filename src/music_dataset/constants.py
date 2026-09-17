"""Constants and Enums for Music Dataset System."""

from enum import Enum

class DownloadStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    FAILED = "failed"
    CORRUPT = "corrupt"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"

class LanguageStatus(str, Enum):
    DETECTED_VI = "detected_vi"
    DETECTED_NON_VI = "detected_non_vi"
    DATASET_ASSERTED_VI = "dataset_asserted_vi"
    UNKNOWN = "unknown"

class LanguageDetectionMethod(str, Enum):
    ENSEMBLE = "ensemble"
    DATASET_ASSERTION = "dataset_assertion"
    HEURISTIC_NGRAM = "heuristic_ngram"
    NOT_CHECKED = "not_checked"

class DatasetName(str, Enum):
    MILLION_SONG_DATASET = "million_song_dataset"
    FMA = "fma"
    UPF = "upf"
    VIETNAM_MUSIC_GENRE = "vietnam_music_genre"

class MetadataStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    EMPTY = "empty"

class AssetStatus(str, Enum):
    FOUND = "found"
    MISSING = "missing"
    DOWNLOADED = "downloaded"
    EXTRACTED = "extracted"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"

class RelevanceStatus(str, Enum):
    CONFIRMED = "confirmed"
    LIKELY = "likely"
    POSSIBLE = "possible"
    UNKNOWN = "unknown"
    NOT_VIETNAMESE = "not_vietnamese"

class EvidenceType(str, Enum):
    VIETNAMESE_LYRICS = "vietnamese_lyrics"
    VIETNAMESE_LANGUAGE_TAG = "vietnamese_language_tag"
    VIETNAMESE_ARTIST = "vietnamese_artist"
    VIETNAMESE_ARTIST_BIO = "vietnamese_artist_bio"
    VIETNAMESE_COUNTRY = "vietnamese_country"
    VIETNAMESE_GENRE = "vietnamese_genre"
    VIETNAMESE_TITLE = "vietnamese_title"
    VIETNAMESE_DATASET_ASSERTION = "vietnamese_dataset_assertion"
    EXTERNAL_METADATA = "external_metadata"
    UNKNOWN = "unknown"
