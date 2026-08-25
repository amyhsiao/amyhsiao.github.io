from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Fish:
    fish_id: str
    canonical_name: str
    aliases: tuple[str, ...] = ()
    extra_names: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    image_url: str
    thumbnail_url: str | None = None
    source_page_url: str | None = None
    rank: int | None = None
    raw_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchBatch:
    results: tuple[SearchResult, ...]
    exhausted: bool = False
    raw_count: int | None = None


@dataclass
class Candidate:
    candidate_id: str
    fish_id: str
    canonical_name: str
    image_url: str
    normalized_image_url: str
    thumbnail_url: str | None
    source_page_url: str | None
    source_domain: str | None
    provider: str
    query: str
    search_rank: int | None
    retrieved_at: str
    validation_status: str
    http_status: int | None = None
    content_type: str | None = None
    width: int | None = None
    height: int | None = None
    phash: str | None = None
    validation_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Candidate":
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value.get(key) for key in allowed})


@dataclass
class FishSummary:
    fish_id: str
    canonical_name: str
    target_count: int
    accepted_count: int = 0
    raw_result_count: int = 0
    url_duplicate_count: int = 0
    phash_duplicate_count: int = 0
    invalid_count: int = 0
    status: str = "not_started"
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
