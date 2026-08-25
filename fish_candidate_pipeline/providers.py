from __future__ import annotations

import logging
import os
import random
import time
from abc import ABC, abstractmethod
from typing import Any

import requests

from .models import SearchBatch, SearchResult

LOGGER = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    pass


class ProviderFatalError(ProviderError):
    """An error that should stop the entire run rather than only one query."""


class ProviderLimitReached(ProviderFatalError):
    pass


class ImageSearchProvider(ABC):
    name: str

    @abstractmethod
    def search(self, query: str, offset: int, limit: int) -> SearchBatch:
        """Return a page of results beginning at a provider-neutral offset."""


class SerpApiGoogleImagesProvider(ImageSearchProvider):
    name = "serpapi_google_images"
    endpoint = "https://serpapi.com/search.json"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 10.0,
        retry_count: int = 1,
        retry_backoff: float = 1.0,
        max_requests: int = 50,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("SERPAPI_API_KEY")
        if not self.api_key:
            raise ProviderError("SERPAPI_API_KEY is not set")
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_backoff = retry_backoff
        self.max_requests = max_requests
        self.request_count = 0
        self.session = session or requests.Session()
        self._page_cache: dict[tuple[str, int], list[Any]] = {}

    def search(self, query: str, offset: int, limit: int) -> SearchBatch:
        # SerpAPI exposes Google Images in fixed batches of up to 100 via `ijn`.
        provider_page_size = 100
        selected: list[tuple[int, Any]] = []
        cursor = offset
        remaining = limit
        exhausted = False
        while remaining > 0:
            page_number = cursor // provider_page_size
            within_page = cursor % provider_page_size
            raw_results = self._get_page(query, page_number)
            page_slice = raw_results[within_page : within_page + remaining]
            selected.extend((cursor + index, item) for index, item in enumerate(page_slice))
            consumed = len(page_slice)
            remaining -= consumed
            cursor += consumed
            if len(raw_results) < provider_page_size:
                exhausted = within_page + consumed >= len(raw_results)
                break
            if consumed == 0:
                exhausted = True
                break
        parsed: list[SearchResult] = []
        for raw_index, (absolute_position, item) in enumerate(selected):
            if not isinstance(item, dict):
                continue
            image_url = item.get("original")
            if not isinstance(image_url, str) or not image_url.strip():
                continue
            parsed.append(
                SearchResult(
                    image_url=image_url.strip(),
                    thumbnail_url=_string_or_none(item.get("thumbnail")),
                    source_page_url=_string_or_none(item.get("link")),
                    rank=_integer_or_default(item.get("position"), absolute_position + 1),
                    raw_index=raw_index,
                    metadata={
                        key: item[key]
                        for key in ("title", "source", "original_width", "original_height")
                        if key in item
                    },
                )
            )
        return SearchBatch(tuple(parsed), exhausted=exhausted, raw_count=len(selected))

    def _get_page(self, query: str, page_number: int) -> list[Any]:
        cache_key = (query, page_number)
        cached = self._page_cache.get(cache_key)
        if cached is not None:
            return cached
        payload = self._request({
            "engine": "google_images",
            "q": query,
            "api_key": self.api_key,
            "ijn": page_number,
        })
        raw_results = payload.get("images_results")
        if not isinstance(raw_results, list):
            error = payload.get("error")
            if error:
                raise _provider_payload_error(str(error))
            return []
        self._page_cache[cache_key] = raw_results
        return raw_results

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.retry_count + 1):
            if self.request_count >= self.max_requests:
                raise ProviderLimitReached(
                    f"Provider request safety limit reached ({self.request_count}/{self.max_requests})"
                )
            self.request_count += 1
            try:
                response = self.session.get(self.endpoint, params=params, timeout=self.timeout)
                if response.status_code == 200:
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise ProviderError("SerpAPI returned a non-object JSON response")
                    return payload
                if response.status_code == 429:
                    raise ProviderLimitReached("SerpAPI hourly/rate limit reached (HTTP 429)")
                if response.status_code in {401, 402, 403}:
                    raise ProviderFatalError(f"SerpAPI authentication/quota error (HTTP {response.status_code})")
                if response.status_code not in {500, 502, 503, 504}:
                    raise ProviderError(f"SerpAPI HTTP {response.status_code}: {response.text[:200]}")
                last_error = ProviderError(f"SerpAPI transient HTTP {response.status_code}")
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else None
            except (requests.Timeout, requests.ConnectionError) as exc:
                # requests exception strings can include the prepared URL and API key.
                last_error = ProviderError(f"{type(exc).__name__}: connection failed")
                delay = None
            except requests.RequestException as exc:
                raise ProviderError(f"SerpAPI request failed: {type(exc).__name__}") from exc
            if attempt >= self.retry_count:
                break
            wait = delay if delay is not None else self.retry_backoff * (2**attempt) + random.uniform(0, 0.25)
            LOGGER.warning("Transient SerpAPI failure; retrying in %.1fs", wait)
            time.sleep(wait)
        raise ProviderError(f"SerpAPI request failed after retries: {last_error}")


class FakeImageSearchProvider(ImageSearchProvider):
    """Deterministic provider used by tests; it never performs network I/O."""

    name = "fake"

    def __init__(self, results_by_query: dict[str, list[SearchResult]]) -> None:
        self.results_by_query = results_by_query
        self.calls: list[tuple[str, int, int]] = []

    def search(self, query: str, offset: int, limit: int) -> SearchBatch:
        self.calls.append((query, offset, limit))
        results = self.results_by_query.get(query, [])
        page = tuple(results[offset : offset + limit])
        return SearchBatch(page, exhausted=offset + limit >= len(results))


def create_provider(name: str, **kwargs: Any) -> ImageSearchProvider:
    if name == "serpapi_google_images":
        return SerpApiGoogleImagesProvider(**kwargs)
    raise ValueError(f"Unsupported image search provider: {name}")


def _string_or_none(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _integer_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _provider_payload_error(message: str) -> ProviderError:
    lowered = message.lower()
    fatal_markers = ("rate limit", "quota", "credit", "api key", "unauthorized", "authentication")
    if any(marker in lowered for marker in fatal_markers):
        return ProviderFatalError(f"SerpAPI authentication/quota error: {message[:200]}")
    return ProviderError(f"SerpAPI error: {message[:200]}")
