from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlsplit

from .config import PoolConfig
from .models import Candidate, Fish, FishSummary, SearchResult
from .outputs import OutputStore
from .providers import ImageSearchProvider, ProviderFatalError
from .queries import generate_queries
from .urls import candidate_id, normalize_url
from .validation import ImageValidator, ValidationResult, phash_distance

LOGGER = logging.getLogger(__name__)


class Validator(Protocol):
    def validate(self, url: str) -> ValidationResult: ...


class CandidatePoolBuilder:
    def __init__(
        self,
        config: PoolConfig,
        provider: ImageSearchProvider,
        store: OutputStore | None = None,
        validator: Validator | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.store = store or OutputStore(config.output_dir)
        self.validator = validator or ImageValidator(
            timeout=config.http_timeout,
            retry_count=config.retry_count,
            retry_backoff=config.retry_backoff,
            max_image_bytes=config.max_image_bytes,
            user_agent=config.user_agent,
            compute_phash=config.dedupe_mode == "url+phash",
        )
        self.halt_reason: str | None = None

    def build(
        self,
        fishes: list[Fish],
        *,
        resume: bool = True,
        force: bool = False,
        missing_photos: tuple[str, ...] = (),
    ) -> list[FishSummary]:
        self.store.initialize()
        coverage_phase = False
        if self.config.processing_priority == "coverage_first" and resume and not force:
            fishes, coverage_phase = self._prioritize_fishes(fishes)
        summaries: list[FishSummary] = []
        for fish in fishes:
            try:
                candidates, summary = self.collect_fish(
                    fish,
                    resume=resume,
                    force=force,
                    query_limit=1 if coverage_phase else None,
                )
            except KeyboardInterrupt:
                raise
            except ProviderFatalError as exc:
                candidates, progress = self.store.load_fish(fish.fish_id) if resume and not force else ([], {})
                summary = FishSummary(
                    fish_id=fish.fish_id,
                    canonical_name=fish.canonical_name,
                    target_count=self.config.target_per_fish,
                    accepted_count=len(candidates),
                    status="partial" if candidates else "not_started",
                    error=str(exc),
                )
                self.store.save_fish(fish, candidates, progress, summary)
                self.store.append_log({
                    "event": "run_halted", "fish_id": fish.fish_id, "reason": str(exc),
                })
                self.halt_reason = str(exc)
                summaries.append(summary)
                aggregate_summaries, aggregate_candidates = self.store.load_all()
                self.store.write_aggregate(
                    aggregate_summaries, aggregate_candidates, self.config.public_dict(), missing_photos
                )
                LOGGER.warning("Stopping the run safely: %s", exc)
                break
            except Exception as exc:
                LOGGER.exception("Candidate collection failed for %s %s", fish.fish_id, fish.canonical_name)
                candidates, progress = self.store.load_fish(fish.fish_id) if resume and not force else ([], {})
                summary = FishSummary(
                    fish_id=fish.fish_id,
                    canonical_name=fish.canonical_name,
                    target_count=self.config.target_per_fish,
                    accepted_count=len(candidates),
                    status="failed",
                    error=f"{type(exc).__name__}: {exc}",
                )
                self.store.save_fish(fish, candidates, progress, summary)
                self.store.append_log({"event": "fish_failed", "fish_id": fish.fish_id, "error": summary.error})
            summaries.append(summary)
            aggregate_summaries, aggregate_candidates = self.store.load_all()
            self.store.write_aggregate(
                aggregate_summaries, aggregate_candidates, self.config.public_dict(), missing_photos
            )
        if not fishes:
            self.store.write_aggregate([], [], self.config.public_dict(), missing_photos)
        return summaries

    def _prioritize_fishes(self, fishes: list[Fish]) -> tuple[list[Fish], bool]:
        """Cover every fish with one canonical-name API page before filling pools."""
        untouched: list[Fish] = []
        partial: list[Fish] = []
        for fish in fishes:
            candidates, progress = self.store.load_fish(fish.fish_id)
            if not candidates and not progress:
                untouched.append(fish)
            elif len(candidates) < self.config.target_per_fish:
                partial.append(fish)
        if untouched:
            LOGGER.info(
                "Coverage-first phase: %d untouched fish; deferring %d partial fish",
                len(untouched), len(partial),
            )
            return untouched, True
        LOGGER.info("Completion phase: all selected fish have search progress; filling %d partial pools", len(partial))
        return partial, False

    def collect_fish(
        self,
        fish: Fish,
        *,
        resume: bool = True,
        force: bool = False,
        query_limit: int | None = None,
    ) -> tuple[list[Candidate], FishSummary]:
        summary = FishSummary(fish.fish_id, fish.canonical_name, self.config.target_per_fish)
        existing, progress = self.store.load_fish(fish.fish_id) if resume and not force else ([], {})
        candidates = self._clean_existing(fish, existing)
        seen_urls = {candidate.normalized_image_url for candidate in candidates}
        hashes = [candidate.phash for candidate in candidates if candidate.phash]
        summary.accepted_count = len(candidates)
        queries = generate_queries(fish, self.config.query_templates)[: self.config.max_queries_per_fish]
        if query_limit is not None:
            queries = queries[:query_limit]
        if len(candidates) >= self.config.target_per_fish:
            summary.status = "complete"
            self.store.save_fish(fish, candidates, progress, summary)
            LOGGER.info("%s %s already complete: %d/%d", fish.fish_id, fish.canonical_name, len(candidates), self.config.target_per_fish)
            return candidates, summary

        raw_budget = min(
            math.ceil(self.config.target_per_fish * self.config.oversample_factor),
            len(queries) * self.config.max_results_per_query,
        )
        LOGGER.info("%s %s: starting with %d/%d candidates", fish.fish_id, fish.canonical_name, len(candidates), self.config.target_per_fish)
        summary.status = "partial"
        exhausted: set[str] = set()
        query_index = 0
        successful_batches = 0
        search_error_count = 0
        while len(candidates) < self.config.target_per_fish and summary.raw_result_count < raw_budget:
            available = [
                query for query in queries
                if query not in exhausted and progress.get(query, 0) < self.config.max_results_per_query
            ]
            if not available:
                break
            query = available[query_index % len(available)]
            query_index += 1
            offset = progress.get(query, 0)
            limit = min(
                self.config.provider_page_size,
                self.config.max_results_per_query - offset,
                raw_budget - summary.raw_result_count,
            )
            try:
                batch = self.provider.search(query, offset, limit)
            except ProviderFatalError:
                raise
            except Exception as exc:
                search_error_count += 1
                LOGGER.error("%s query %r failed: %s", fish.fish_id, query, exc)
                exhausted.add(query)
                self.store.append_log({
                    "event": "search_error", "fish_id": fish.fish_id, "query": query,
                    "offset": offset, "error": f"{type(exc).__name__}: {exc}",
                })
                continue
            successful_batches += 1
            result_count = len(batch.results)
            raw_count = batch.raw_count if batch.raw_count is not None else result_count
            summary.raw_result_count += raw_count
            self.store.append_log({
                "event": "search_batch", "fish_id": fish.fish_id, "query": query,
                "offset": offset, "requested": limit, "returned": result_count,
            })
            unique_results: list[SearchResult] = []
            normalized_results: list[str] = []
            raw_indices: list[int] = []
            for batch_index, result in enumerate(batch.results):
                normalized = normalize_url(result.image_url)
                try:
                    parsed = urlsplit(normalized)
                    is_http_url = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
                except ValueError:
                    is_http_url = False
                if not is_http_url:
                    summary.invalid_count += 1
                    continue
                if normalized in seen_urls:
                    summary.url_duplicate_count += 1
                    continue
                # Reserve within this batch so duplicated URLs are only validated once.
                seen_urls.add(normalized)
                unique_results.append(result)
                normalized_results.append(normalized)
                raw_indices.append(result.raw_index if result.raw_index is not None else batch_index)

            validations = self._validate(unique_results)
            reached_target_at: int | None = None
            for result, normalized, raw_index, validation in zip(
                unique_results, normalized_results, raw_indices, validations, strict=True
            ):
                if len(candidates) >= self.config.target_per_fish:
                    break
                if not validation.ok:
                    summary.invalid_count += 1
                    self.store.append_log({
                        "event": "candidate_invalid", "fish_id": fish.fish_id,
                        "image_url": result.image_url, "status": validation.status,
                        "error": validation.error,
                    })
                    continue
                if validation.phash and self._is_near_duplicate(validation.phash, hashes):
                    summary.phash_duplicate_count += 1
                    continue
                candidate = self._candidate(fish, result, normalized, query, validation)
                candidates.append(candidate)
                if candidate.phash:
                    hashes.append(candidate.phash)
                if len(candidates) >= self.config.target_per_fish:
                    reached_target_at = raw_index
                    break
            consumed_raw = raw_count
            if reached_target_at is not None:
                consumed_raw = min(raw_count, reached_target_at + 1)
            progress[query] = min(offset + consumed_raw, self.config.max_results_per_query)
            if batch.exhausted and consumed_raw >= raw_count:
                exhausted.add(query)
            summary.accepted_count = len(candidates)
            self.store.save_fish(fish, candidates, progress, summary)

        summary.accepted_count = len(candidates)
        if len(candidates) >= self.config.target_per_fish:
            summary.status = "complete"
        elif successful_batches == 0 and search_error_count > 0 and not candidates:
            summary.status = "failed"
            summary.error = f"All {search_error_count} attempted search queries failed"
        else:
            summary.status = "partial"
        self.store.save_fish(fish, candidates, progress, summary)
        self.store.append_log({"event": "fish_complete", **summary.to_dict()})
        LOGGER.info(
            "%s %s | raw=%d url_duplicates=%d broken=%d phash_duplicates=%d accepted=%d status=%s",
            fish.fish_id, fish.canonical_name, summary.raw_result_count, summary.url_duplicate_count,
            summary.invalid_count, summary.phash_duplicate_count, summary.accepted_count, summary.status,
        )
        return candidates, summary

    def _validate(self, results: list[SearchResult]) -> list[ValidationResult]:
        if not results:
            return []
        needs_fetch = self.config.validation or self.config.dedupe_mode == "url+phash"
        if not needs_fetch:
            return [ValidationResult(True, "not_checked") for _ in results]
        with ThreadPoolExecutor(max_workers=self.config.workers) as executor:
            return list(executor.map(lambda item: self.validator.validate(item.image_url), results))

    def _clean_existing(self, fish: Fish, existing: list[Candidate]) -> list[Candidate]:
        cleaned: list[Candidate] = []
        seen: set[str] = set()
        hashes: list[str] = []
        for candidate in existing:
            if candidate.fish_id != fish.fish_id or not candidate.image_url:
                continue
            if candidate.validation_status not in {"ok", "not_checked"}:
                continue
            normalized = normalize_url(candidate.image_url)
            if normalized in seen:
                continue
            if self.config.dedupe_mode == "url+phash" and candidate.phash:
                if self._is_near_duplicate(candidate.phash, hashes):
                    continue
                hashes.append(candidate.phash)
            candidate.normalized_image_url = normalized
            candidate.candidate_id = candidate_id(fish.fish_id, normalized)
            seen.add(normalized)
            cleaned.append(candidate)
        return cleaned

    def _is_near_duplicate(self, phash: str, known_hashes: list[str]) -> bool:
        for known in known_hashes:
            try:
                if phash_distance(phash, known) <= self.config.phash_threshold:
                    return True
            except (TypeError, ValueError):
                LOGGER.warning("Ignoring malformed pHash value during deduplication")
        return False

    def _candidate(
        self,
        fish: Fish,
        result: SearchResult,
        normalized: str,
        query: str,
        validation: ValidationResult,
    ) -> Candidate:
        try:
            source = urlsplit(result.source_page_url or "")
            source_domain = source.hostname.lower() if source.hostname else None
        except ValueError:
            source_domain = None
        return Candidate(
            candidate_id=candidate_id(fish.fish_id, normalized),
            fish_id=fish.fish_id,
            canonical_name=fish.canonical_name,
            image_url=result.image_url,
            normalized_image_url=normalized,
            thumbnail_url=result.thumbnail_url,
            source_page_url=result.source_page_url,
            source_domain=source_domain,
            provider=self.provider.name,
            query=query,
            search_rank=result.rank,
            retrieved_at=datetime.now(UTC).isoformat(),
            validation_status=validation.status,
            http_status=validation.http_status,
            content_type=validation.content_type,
            width=validation.width,
            height=validation.height,
            phash=validation.phash,
            validation_error=validation.error,
        )
