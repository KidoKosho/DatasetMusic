"""Configuration parser for Music Dataset Pipeline."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field

class StorageConfig(BaseModel):
    root: Path = Field(default=Path("datasets"))
    data_dir: Path = Field(default=Path("data"))
    reports_dir: Path = Field(default=Path("reports"))
    logs_dir: Path = Field(default=Path("logs"))

class DownloadConfig(BaseModel):
    concurrency: int = 4
    requests_per_second: float = 2.0
    timeout: int = 60
    max_retries: int = 5
    chunk_size: int = 1048576  # 1MB
    resume: bool = True
    verify_checksum: bool = True

class LanguageConfig(BaseModel):
    minimum_confidence: float = 0.80
    model_type: str = "ensemble"

class SourceLimit(BaseModel):
    concurrency: int = 2
    requests_per_second: float = 2.0

class AppConfig(BaseModel):
    storage: StorageConfig = Field(default_factory=StorageConfig)
    download: DownloadConfig = Field(default_factory=DownloadConfig)
    language: LanguageConfig = Field(default_factory=LanguageConfig)
    fma: Dict[str, Any] = Field(default_factory=dict)
    million_song_dataset: Dict[str, Any] = Field(default_factory=dict)
    upf: Dict[str, Any] = Field(default_factory=dict)
    vietnam_music_genre: Dict[str, Any] = Field(default_factory=dict)
    lyrics: Dict[str, Any] = Field(default_factory=dict)
    artwork: Dict[str, Any] = Field(default_factory=dict)
    providers: Dict[str, Any] = Field(default_factory=dict)
    sources: Dict[str, SourceLimit] = Field(default_factory=dict)

def load_config(config_path: Optional[Path] = None) -> AppConfig:
    """Load configuration from file or fallback to defaults."""
    search_paths = []
    if config_path:
        search_paths.append(Path(config_path))
    search_paths.extend([
        Path("config/config.yaml"),
        Path("music-dataset-crawler/config/config.yaml"),
        Path(__file__).resolve().parents[2] / "config" / "config.yaml",
        Path(__file__).resolve().parents[3] / "config" / "config.yaml",
    ])

    for p in search_paths:
        if p.exists() and p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return AppConfig(**data)

    return AppConfig()
