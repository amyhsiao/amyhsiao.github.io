from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from .models import Fish

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class InputReport:
    taxonomy: dict[str, Fish]
    target_fish_ids: tuple[str, ...]
    unique_target_photos: tuple[str, ...]
    target_row_count: int
    duplicate_target_rows: int
    missing_photos: tuple[str, ...]


def parse_aliases(raw: str | None) -> tuple[str, ...]:
    seen: set[str] = set()
    aliases: list[str] = []
    for value in (raw or "").split("|"):
        alias = value.strip()
        if alias and alias not in seen:
            seen.add(alias)
            aliases.append(alias)
    return tuple(aliases)


def _read_csv(path: Path, required: set[str]) -> tuple[list[dict[str, str]], list[str]]:
    if not path.is_file():
        raise ValueError(f"CSV file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        missing = required - set(columns)
        if missing:
            raise ValueError(f"{path} is missing required columns: {', '.join(sorted(missing))}")
        return [dict(row) for row in reader], columns


def load_taxonomy(path: Path) -> dict[str, Fish]:
    rows, columns = _read_csv(path, {"fish_id", "canonical_name", "aliases"})
    taxonomy: dict[str, Fish] = {}
    conflicting_duplicates: set[str] = set()
    exact_duplicate_count = 0
    for line_number, row in enumerate(rows, start=2):
        fish_id = (row.get("fish_id") or "").strip()
        canonical = (row.get("canonical_name") or "").strip()
        if not fish_id or not canonical:
            raise ValueError(f"{path}:{line_number}: fish_id and canonical_name must not be blank")
        extras = {
            key: (row.get(key) or "").strip()
            for key in columns
            if key not in {"fish_id", "canonical_name", "aliases"} and (row.get(key) or "").strip()
        }
        fish = Fish(fish_id, canonical, parse_aliases(row.get("aliases")), extras)
        if fish_id in taxonomy:
            if taxonomy[fish_id] == fish:
                exact_duplicate_count += 1
            else:
                conflicting_duplicates.add(fish_id)
            continue
        taxonomy[fish_id] = fish
    if conflicting_duplicates:
        raise ValueError(f"Conflicting duplicate fish_id rows in {path}: {', '.join(sorted(conflicting_duplicates))}")
    if exact_duplicate_count:
        LOGGER.warning("Ignored %d exact duplicate taxonomy rows in %s", exact_duplicate_count, path)
    return taxonomy


def inspect_inputs(taxonomy_path: Path, targets_path: Path, photos_dir: Path) -> InputReport:
    taxonomy = load_taxonomy(taxonomy_path)
    rows, _ = _read_csv(targets_path, {"filename", "fish_id"})
    seen_rows: set[tuple[str, str]] = set()
    fish_ids: list[str] = []
    fish_seen: set[str] = set()
    filenames: list[str] = []
    filename_seen: set[str] = set()
    duplicate_rows = 0
    for line_number, row in enumerate(rows, start=2):
        filename = (row.get("filename") or "").strip()
        fish_id = (row.get("fish_id") or "").strip()
        if not filename or not fish_id:
            raise ValueError(f"{targets_path}:{line_number}: filename and fish_id must not be blank")
        pair = (filename, fish_id)
        if pair in seen_rows:
            duplicate_rows += 1
            continue
        seen_rows.add(pair)
        if fish_id not in fish_seen:
            fish_seen.add(fish_id)
            fish_ids.append(fish_id)
        if filename not in filename_seen:
            filename_seen.add(filename)
            filenames.append(filename)
    invalid = sorted(set(fish_ids) - taxonomy.keys())
    if invalid:
        raise ValueError(
            f"photo targets reference fish IDs absent from {taxonomy_path}: {', '.join(invalid)}"
        )
    missing_photos = tuple(name for name in filenames if not (photos_dir / name).is_file())
    if missing_photos:
        LOGGER.warning("%d of %d referenced photos are missing from %s", len(missing_photos), len(filenames), photos_dir)
    return InputReport(
        taxonomy=taxonomy,
        target_fish_ids=tuple(fish_ids),
        unique_target_photos=tuple(filenames),
        target_row_count=len(rows),
        duplicate_target_rows=duplicate_rows,
        missing_photos=missing_photos,
    )
