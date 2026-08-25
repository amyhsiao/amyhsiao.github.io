from __future__ import annotations

from collections.abc import Iterable

from .models import Fish


DEFAULT_QUERY_TEMPLATES = (
    "{canonical_name}",
    "{alias} 魚",
)


def generate_queries(fish: Fish, templates: Iterable[str]) -> list[str]:
    """Expand templates, omitting alias templates when aliases are unavailable."""
    queries: list[str] = []
    seen: set[str] = set()
    base = {"fish_id": fish.fish_id, "canonical_name": fish.canonical_name, **fish.extra_names}
    for template in templates:
        aliases: tuple[str | None, ...] = fish.aliases if "{alias}" in template else (None,)
        for alias in aliases:
            values = {**base, "alias": alias or ""}
            try:
                query = template.format_map(_BlankMissing(values)).strip()
            except (ValueError, KeyError) as exc:
                raise ValueError(f"Invalid query template {template!r}: {exc}") from exc
            query = " ".join(query.split())
            if query and query not in seen:
                seen.add(query)
                queries.append(query)
    return queries


class _BlankMissing(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""
