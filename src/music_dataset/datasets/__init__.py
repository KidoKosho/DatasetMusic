"""Dataset adapters package."""

from music_dataset.datasets.base import DatasetAdapter
from music_dataset.datasets.fma import FmaAdapter
from music_dataset.datasets.million_song_dataset import MillionSongDatasetAdapter
from music_dataset.datasets.upf import UpfAdapter
from music_dataset.datasets.vietnam_music_genre import VietnamMusicGenreAdapter

__all__ = [
    "DatasetAdapter",
    "VietnamMusicGenreAdapter",
    "FmaAdapter",
    "MillionSongDatasetAdapter",
    "UpfAdapter",
]
