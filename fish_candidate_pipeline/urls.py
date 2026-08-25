from __future__ import annotations

import hashlib
import posixpath
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
}


def normalize_url(url: str) -> str:
    """Return a conservative canonical form suitable for URL-level deduplication."""
    url = url.strip()
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    scheme = parts.scheme.lower()
    hostname = (parts.hostname or "").lower()
    if not scheme or not hostname:
        return url
    try:
        port = parts.port
    except ValueError:
        return url
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    path = parts.path or "/"
    normalized_path = posixpath.normpath(path)
    if path.endswith("/") and not normalized_path.endswith("/"):
        normalized_path += "/"
    if not normalized_path.startswith("/"):
        normalized_path = "/" + normalized_path
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in TRACKING_PARAMETERS:
            continue
        query.append((key, value))
    query.sort()
    return urlunsplit((scheme, netloc, normalized_path, urlencode(query, doseq=True), ""))


def candidate_id(fish_id: str, image_url: str) -> str:
    stable = f"{fish_id}\n{normalize_url(image_url)}".encode("utf-8")
    return "cand_" + hashlib.sha256(stable).hexdigest()[:24]
