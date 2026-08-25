from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .queries import DEFAULT_QUERY_TEMPLATES


@dataclass
class PoolConfig:
    taxonomy_path: Path = Path("Fish_Map/fish_taxonomy.csv")
    photo_targets_path: Path = Path("Fish_Map/photo_targets.csv")
    photos_dir: Path = Path("Photos")
    output_dir: Path = Path("Candidate_Pool")
    provider: str = "serpapi_google_images"
    target_per_fish: int = 100
    query_templates: list[str] = field(default_factory=lambda: list(DEFAULT_QUERY_TEMPLATES))
    max_results_per_query: int = 100
    max_queries_per_fish: int = 12
    oversample_factor: float = 3.0
    provider_page_size: int = 20
    workers: int = 8
    http_timeout: float = 10.0
    retry_count: int = 1
    retry_backoff: float = 1.0
    max_provider_requests: int = 50
    processing_priority: str = "coverage_first"
    dedupe_mode: str = "url"
    phash_threshold: int = 6
    validation: bool = True
    max_image_bytes: int = 25_000_000
    user_agent: str = "FishCandidatePool/1.0"

    def validate(self) -> None:
        positive = {
            "target_per_fish": self.target_per_fish,
            "max_results_per_query": self.max_results_per_query,
            "max_queries_per_fish": self.max_queries_per_fish,
            "oversample_factor": self.oversample_factor,
            "provider_page_size": self.provider_page_size,
            "workers": self.workers,
            "http_timeout": self.http_timeout,
            "max_image_bytes": self.max_image_bytes,
            "max_provider_requests": self.max_provider_requests,
        }
        invalid = [name for name, value in positive.items() if value <= 0]
        if invalid:
            raise ValueError(f"Configuration values must be positive: {', '.join(invalid)}")
        if self.retry_count < 0 or self.phash_threshold < 0:
            raise ValueError("retry_count and phash_threshold must not be negative")
        if self.dedupe_mode not in {"url", "url+phash"}:
            raise ValueError("dedupe_mode must be 'url' or 'url+phash'")
        if self.processing_priority not in {"coverage_first", "input_order"}:
            raise ValueError("processing_priority must be 'coverage_first' or 'input_order'")
        if not self.query_templates:
            raise ValueError("At least one query template is required")

    def public_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key, value in result.items():
            if isinstance(value, Path):
                result[key] = str(value)
        return result


PATH_FIELDS = {"taxonomy_path", "photo_targets_path", "photos_dir", "output_dir"}


def load_config(path: Path | None, overrides: dict[str, Any]) -> PoolConfig:
    values: dict[str, Any] = {}
    if path:
        if not path.is_file():
            raise ValueError(f"Config file not found: {path}")
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Config root must be a mapping: {path}")
        values.update(loaded.get("candidate_pool", loaded))
    values.update({key: value for key, value in overrides.items() if value is not None})
    known = PoolConfig.__dataclass_fields__.keys()
    unknown = sorted(set(values) - set(known))
    if unknown:
        raise ValueError(f"Unknown configuration keys: {', '.join(unknown)}")
    for key in PATH_FIELDS:
        if key in values:
            values[key] = Path(values[key])
    config = PoolConfig(**values)
    config.validate()
    return config
