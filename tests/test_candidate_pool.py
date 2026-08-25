from __future__ import annotations

import json
from pathlib import Path

import pytest

from fish_candidate_pipeline.config import PoolConfig
from fish_candidate_pipeline.inputs import inspect_inputs, parse_aliases
from fish_candidate_pipeline.models import Fish, SearchResult
from fish_candidate_pipeline.outputs import OutputStore
from fish_candidate_pipeline.pipeline import CandidatePoolBuilder
from fish_candidate_pipeline.providers import (
    FakeImageSearchProvider,
    ProviderLimitReached,
    SerpApiGoogleImagesProvider,
)
from fish_candidate_pipeline.queries import generate_queries
from fish_candidate_pipeline.urls import candidate_id, normalize_url
from fish_candidate_pipeline.validation import ValidationResult


class StubValidator:
    def __init__(self, hashes: dict[str, str | None] | None = None) -> None:
        self.hashes = hashes or {}

    def validate(self, url: str) -> ValidationResult:
        return ValidationResult(True, "ok", 200, "image/jpeg", 100, 100, self.hashes.get(url))


def result(number: int, url: str | None = None) -> SearchResult:
    return SearchResult(url or f"https://images.example/fish-{number}.jpg", rank=number)


def config(tmp_path: Path, **overrides) -> PoolConfig:
    values = {
        "output_dir": tmp_path / "pool",
        "target_per_fish": 2,
        "query_templates": ["{canonical_name}"],
        "max_results_per_query": 20,
        "max_queries_per_fish": 4,
        "provider_page_size": 5,
        "oversample_factor": 5,
        "validation": False,
        "workers": 2,
        "processing_priority": "input_order",
    }
    values.update(overrides)
    return PoolConfig(**values)


def test_alias_parsing_strips_blanks_and_duplicates() -> None:
    assert parse_aliases(" 盤仔魚 | 紅盤 | 盤仔魚 |  ") == ("盤仔魚", "紅盤")
    assert parse_aliases("") == ()


def test_query_generation_uses_canonical_and_each_alias_once() -> None:
    fish = Fish("fish_004", "日本血鯛", ("盤仔魚", "紅盤", "日本血鯛"))
    queries = generate_queries(fish, ["{canonical_name}", "{canonical_name} 魚", "{alias}", "{alias} 魚"])
    assert queries == ["日本血鯛", "日本血鯛 魚", "盤仔魚", "紅盤", "盤仔魚 魚", "紅盤 魚"]


def test_join_rejects_unknown_target_fish(tmp_path: Path) -> None:
    taxonomy = tmp_path / "taxonomy.csv"
    targets = tmp_path / "targets.csv"
    photos = tmp_path / "Photos"
    photos.mkdir()
    taxonomy.write_text("fish_id,canonical_name,aliases\nfish_001,紅紋笛鯛,赤筆\n", encoding="utf-8")
    targets.write_text("filename,fish_id\na.jpg,fish_999\n", encoding="utf-8")
    with pytest.raises(ValueError, match="fish_999"):
        inspect_inputs(taxonomy, targets, photos)


def test_one_photo_can_target_multiple_fish(tmp_path: Path) -> None:
    taxonomy = tmp_path / "taxonomy.csv"
    targets = tmp_path / "targets.csv"
    photos = tmp_path / "Photos"
    photos.mkdir()
    (photos / "同一張.jpg").write_bytes(b"reference data is not opened")
    taxonomy.write_text(
        "\ufefffish_id,canonical_name,aliases\nfish_001,紅紋笛鯛,\nfish_002,寒鯛,石佬\n",
        encoding="utf-8",
    )
    targets.write_text(
        "\ufefffilename,fish_id\n同一張.jpg,fish_001\n同一張.jpg,fish_002\n",
        encoding="utf-8",
    )
    report = inspect_inputs(taxonomy, targets, photos)
    assert report.target_fish_ids == ("fish_001", "fish_002")
    assert report.unique_target_photos == ("同一張.jpg",)


def test_candidate_id_is_deterministic_after_url_normalization() -> None:
    left = candidate_id("fish_001", "HTTPS://Example.COM:443/a/../fish.jpg?b=2&utm_source=x&a=1#part")
    right = candidate_id("fish_001", "https://example.com/fish.jpg?a=1&b=2")
    assert left == right
    assert left != candidate_id("fish_002", "https://example.com/fish.jpg?a=1&b=2")


def test_url_normalization() -> None:
    assert normalize_url("https://EXAMPLE.com:443/a/../b.jpg?z=2&utm_medium=x&a=1#x") == (
        "https://example.com/b.jpg?a=1&z=2"
    )


def test_url_deduplication_across_queries(tmp_path: Path) -> None:
    fish = Fish("fish_001", "紅紋笛鯛", ("赤筆",))
    cfg = config(tmp_path, query_templates=["{canonical_name}", "{alias}"], target_per_fish=3)
    duplicate = "https://EXAMPLE.com/fish.jpg?utm_source=a"
    provider = FakeImageSearchProvider({
        "紅紋笛鯛": [result(1, duplicate), result(2)],
        "赤筆": [result(3, "https://example.com/fish.jpg"), result(4)],
    })
    summary = CandidatePoolBuilder(cfg, provider).build([fish])[0]
    assert summary.accepted_count == 3
    assert summary.url_duplicate_count == 1


def test_phash_near_duplicate_is_rejected(tmp_path: Path) -> None:
    fish = Fish("fish_001", "魚")
    urls = ["https://img.example/a.jpg", "https://img.example/b.jpg", "https://img.example/c.jpg"]
    provider = FakeImageSearchProvider({"魚": [result(i, url) for i, url in enumerate(urls)]})
    cfg = config(tmp_path, dedupe_mode="url+phash", validation=True, phash_threshold=1)
    validator = StubValidator({urls[0]: "0000000000000000", urls[1]: "0000000000000001", urls[2]: "ffffffffffffffff"})
    summary = CandidatePoolBuilder(cfg, provider, validator=validator).build([fish])[0]
    assert summary.accepted_count == 2
    assert summary.phash_duplicate_count == 1


def test_resume_continues_from_saved_query_offset(tmp_path: Path) -> None:
    fish = Fish("fish_001", "魚")
    results = [result(i) for i in range(4)]
    first_provider = FakeImageSearchProvider({"魚": results})
    # The provider returns more results than the target; resume must continue at
    # the actual stopping position rather than skip the unconsumed batch tail.
    first_config = config(tmp_path, target_per_fish=2, provider_page_size=5)
    CandidatePoolBuilder(first_config, first_provider).build([fish])
    second_provider = FakeImageSearchProvider({"魚": results})
    second_config = config(tmp_path, target_per_fish=3, provider_page_size=2)
    summary = CandidatePoolBuilder(second_config, second_provider).build([fish], resume=True)[0]
    assert summary.accepted_count == 3
    assert second_provider.calls[0][1] == 2
    payload = json.loads(OutputStore(second_config.output_dir).fish_path("fish_001").read_text(encoding="utf-8"))
    assert len(payload["candidates"]) == 3


def test_target_count_stops_after_first_batch(tmp_path: Path) -> None:
    fish = Fish("fish_001", "魚")
    provider = FakeImageSearchProvider({"魚": [result(i) for i in range(10)]})
    cfg = config(tmp_path, target_per_fish=2, provider_page_size=5)
    summary = CandidatePoolBuilder(cfg, provider).build([fish])[0]
    assert summary.accepted_count == 2
    assert len(provider.calls) == 1


class _ProviderResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.headers: dict[str, str] = {}
        self.text = ""

    def json(self) -> dict:
        return self._payload


class _ProviderSession:
    def __init__(self, responses: list[_ProviderResponse]) -> None:
        self.responses = responses
        self.calls = 0

    def get(self, *args, **kwargs) -> _ProviderResponse:
        response = self.responses[self.calls]
        self.calls += 1
        return response


def test_provider_hard_request_cap_counts_http_attempts() -> None:
    response = _ProviderResponse(200, {"images_results": [{"original": "https://img.example/a.jpg"}]})
    session = _ProviderSession([response])
    provider = SerpApiGoogleImagesProvider(api_key="test", max_requests=1, session=session)
    provider.search("first", 0, 1)
    with pytest.raises(ProviderLimitReached, match="safety limit"):
        provider.search("second", 0, 1)
    assert session.calls == 1


def test_provider_does_not_retry_http_429() -> None:
    session = _ProviderSession([_ProviderResponse(429)])
    provider = SerpApiGoogleImagesProvider(api_key="test", retry_count=3, max_requests=50, session=session)
    with pytest.raises(ProviderLimitReached, match="429"):
        provider.search("fish", 0, 1)
    assert session.calls == 1


def test_coverage_first_defers_existing_partial_and_uses_one_query(tmp_path: Path) -> None:
    existing = Fish("fish_001", "既有魚")
    new = Fish("fish_002", "新魚", ("新魚俗名",))
    seed_config = config(tmp_path, target_per_fish=3)
    seed_provider = FakeImageSearchProvider({"既有魚": [result(1)]})
    CandidatePoolBuilder(seed_config, seed_provider).build([existing])

    coverage_config = config(tmp_path, target_per_fish=3, processing_priority="coverage_first")
    provider = FakeImageSearchProvider({
        "既有魚": [result(2), result(3)],
        "新魚": [result(4)],
        "新魚俗名 魚": [result(5)],
    })
    summaries = CandidatePoolBuilder(coverage_config, provider).build([existing, new])
    assert [summary.fish_id for summary in summaries] == ["fish_002"]
    assert [call[0] for call in provider.calls] == ["新魚"]
