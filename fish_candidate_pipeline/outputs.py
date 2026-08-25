from __future__ import annotations

import csv
import json
import os
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .models import Candidate, Fish, FishSummary


SCHEMA_VERSION = 1
LOGGER = logging.getLogger(__name__)


class OutputStore:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.by_fish_dir = output_dir / "by_fish"
        self.logs_dir = output_dir / "logs"

    def initialize(self) -> None:
        self.by_fish_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def fish_path(self, fish_id: str) -> Path:
        return self.by_fish_dir / f"{fish_id}.json"

    def load_fish(self, fish_id: str) -> tuple[list[Candidate], dict[str, int]]:
        path = self.fish_path(fish_id)
        if not path.is_file():
            return [], {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            raw_candidates, progress = payload, {}
        elif isinstance(payload, dict):
            raw_candidates = payload.get("candidates", [])
            progress = payload.get("search_progress", {})
        else:
            raise ValueError(f"Invalid candidate file structure: {path}")
        if not isinstance(raw_candidates, list):
            raise ValueError(f"Invalid candidates array in {path}")
        if not isinstance(progress, dict):
            raise ValueError(f"Invalid search_progress object in {path}")
        candidates = [Candidate.from_dict(item) for item in raw_candidates if isinstance(item, dict)]
        clean_progress = {
            str(key): int(value) for key, value in progress.items()
            if isinstance(value, int) and value >= 0
        }
        return candidates, clean_progress

    def save_fish(
        self,
        fish: Fish,
        candidates: list[Candidate],
        progress: dict[str, int],
        summary: FishSummary,
    ) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "fish_id": fish.fish_id,
            "canonical_name": fish.canonical_name,
            "aliases": list(fish.aliases),
            "updated_at": _now(),
            "search_progress": progress,
            "summary": summary.to_dict(),
            "candidates": [candidate.to_dict() for candidate in candidates],
        }
        _atomic_text(self.fish_path(fish.fish_id), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    def load_all(self) -> tuple[list[FishSummary], list[Candidate]]:
        """Load every durable per-fish file so subset runs preserve aggregate indexes."""
        summaries: list[FishSummary] = []
        candidates: list[Candidate] = []
        for path in sorted(self.by_fish_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("root is not an object")
                summary_data = payload.get("summary", {})
                raw_candidates = payload.get("candidates", [])
                if not isinstance(summary_data, dict) or not isinstance(raw_candidates, list):
                    raise ValueError("summary is not an object or candidates is not an array")
                allowed = FishSummary.__dataclass_fields__.keys()
                summaries.append(FishSummary(**{key: summary_data.get(key) for key in allowed}))
                candidates.extend(
                    Candidate.from_dict(item)
                    for item in raw_candidates
                    if isinstance(item, dict)
                )
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                LOGGER.error("Skipping unreadable per-fish output %s: %s", path, exc)
        return summaries, candidates

    def append_log(self, event: dict[str, Any]) -> None:
        event = {"timestamp": _now(), **event}
        with (self.logs_dir / "search_log.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def write_aggregate(
        self,
        summaries: Iterable[FishSummary],
        candidates: Iterable[Candidate],
        config: dict[str, Any],
        missing_photos: Iterable[str],
    ) -> None:
        summaries = list(summaries)
        candidates = list(candidates)
        self._write_csv(self.output_dir / "summary.csv", [item.to_dict() for item in summaries], list(FishSummary.__dataclass_fields__))
        candidate_fields = list(Candidate.__dataclass_fields__)
        self._write_csv(self.output_dir / "candidates.csv", [item.to_dict() for item in candidates], candidate_fields)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": _now(),
            "fish_count": len(summaries),
            "candidate_count": len(candidates),
            "config": config,
            "missing_photos": list(missing_photos),
            "fish_files": {item.fish_id: f"by_fish/{item.fish_id}.json" for item in summaries},
        }
        _atomic_text(self.output_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)


def _atomic_text(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _now() -> str:
    return datetime.now(UTC).isoformat()
