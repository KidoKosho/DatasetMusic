"""Metadata parsing, normalization, and precedence modules."""

from music_dataset.metadata.enrichment import MetadataEnrichmentEngine
from music_dataset.metadata.id3_parser import ID3Parser, ParsedID3Metadata
from music_dataset.metadata.normalizer import fallback_title_from_filename, normalize_genre
from music_dataset.metadata.precedence import MetadataPrecedenceResolver

__all__ = [
    "ID3Parser",
    "ParsedID3Metadata",
    "normalize_genre",
    "fallback_title_from_filename",
    "MetadataPrecedenceResolver",
    "MetadataEnrichmentEngine",
]
