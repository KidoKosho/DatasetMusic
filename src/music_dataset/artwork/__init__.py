"""Artwork package."""

from music_dataset.artwork.downloader import ArtworkDownloader
from music_dataset.artwork.extractor import ArtworkExtractor

__all__ = ["ArtworkExtractor", "ArtworkDownloader"]
