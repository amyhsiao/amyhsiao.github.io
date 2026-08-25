from __future__ import annotations

import io
import math
import random
import time
from dataclasses import dataclass

import requests
from PIL import Image, UnidentifiedImageError


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    status: str
    http_status: int | None = None
    content_type: str | None = None
    width: int | None = None
    height: int | None = None
    phash: str | None = None
    error: str | None = None


class ImageValidator:
    def __init__(
        self,
        timeout: float,
        retry_count: int,
        retry_backoff: float,
        max_image_bytes: int,
        user_agent: str,
        compute_phash: bool,
    ) -> None:
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_backoff = retry_backoff
        self.max_image_bytes = max_image_bytes
        self.user_agent = user_agent
        self.compute_phash = compute_phash

    def validate(self, url: str) -> ValidationResult:
        last_error: Exception | None = None
        # requests' read timeout applies between socket reads, so a server that
        # slowly trickles bytes could otherwise keep a worker occupied forever.
        deadline = time.monotonic() + self.timeout * (self.retry_count + 1)
        for attempt in range(self.retry_count + 1):
            if time.monotonic() >= deadline:
                return ValidationResult(False, "download_timeout", error="Total image download deadline exceeded")
            try:
                with requests.get(
                    url,
                    timeout=self.timeout,
                    headers={"User-Agent": self.user_agent, "Accept": "image/*"},
                    stream=True,
                    allow_redirects=True,
                ) as response:
                    if response.status_code != 200:
                        if response.status_code in {429, 500, 502, 503, 504} and attempt < self.retry_count:
                            self._backoff(attempt)
                            continue
                        return ValidationResult(False, "http_error", response.status_code, error=f"HTTP {response.status_code}")
                    declared_length = _to_int(response.headers.get("Content-Length"))
                    content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower() or None
                    if declared_length is not None and declared_length > self.max_image_bytes:
                        return ValidationResult(False, "too_large", 200, content_type, error="Content-Length exceeds limit")
                    data = bytearray()
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if time.monotonic() >= deadline:
                            return ValidationResult(
                                False, "download_timeout", 200, content_type,
                                error="Total image download deadline exceeded",
                            )
                        if chunk:
                            data.extend(chunk)
                        if len(data) > self.max_image_bytes:
                            return ValidationResult(False, "too_large", 200, content_type, error="Downloaded image exceeds limit")
                    if not data:
                        return ValidationResult(False, "empty", 200, content_type, error="Empty response")
                try:
                    with Image.open(io.BytesIO(data)) as image:
                        image.load()
                        width, height = image.size
                        if width <= 0 or height <= 0:
                            return ValidationResult(False, "invalid_image", 200, content_type, error="Invalid dimensions")
                        phash = None
                        phash_error = None
                        if self.compute_phash:
                            try:
                                phash = perceptual_hash(image)
                            except Exception as exc:  # A pHash failure must not discard an otherwise valid image.
                                phash_error = f"pHash failed: {type(exc).__name__}: {exc}"
                        return ValidationResult(True, "ok", 200, content_type, width, height, phash, phash_error)
                except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
                    return ValidationResult(False, "not_image", 200, content_type, error=str(exc))
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if attempt < self.retry_count:
                    self._backoff(attempt)
                    continue
            except requests.RequestException as exc:
                return ValidationResult(False, "request_error", error=str(exc))
        return ValidationResult(False, "network_error", error=str(last_error))

    def _backoff(self, attempt: int) -> None:
        time.sleep(self.retry_backoff * (2**attempt) + random.uniform(0, 0.1))


def perceptual_hash(image: Image.Image, hash_size: int = 8, highfreq_factor: int = 4) -> str:
    """Compute a standard low-frequency DCT pHash without retaining image data."""
    size = hash_size * highfreq_factor
    grayscale = image.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    pixels = list(grayscale.getdata())
    cosines = [[math.cos(math.pi * (2 * x + 1) * u / (2 * size)) for x in range(size)] for u in range(hash_size)]
    low: list[float] = []
    for v in range(hash_size):
        for u in range(hash_size):
            total = 0.0
            for y in range(size):
                row = y * size
                cy = cosines[v][y]
                total += cy * sum(pixels[row + x] * cosines[u][x] for x in range(size))
            low.append(total)
    comparison = sorted(low[1:])[len(low[1:]) // 2]
    bits = 0
    for value in low:
        bits = (bits << 1) | int(value > comparison)
    return f"{bits:0{hash_size * hash_size // 4}x}"


def phash_distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _to_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None
