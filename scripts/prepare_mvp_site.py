#!/usr/bin/env python3
"""Prepare static data and reference images for the local fish-labeling MVP."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageOps, UnidentifiedImageError


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAXONOMY = ROOT / "Fish_Map" / "fish_taxonomy.csv"
DEFAULT_TARGETS = ROOT / "Fish_Map" / "photo_targets.csv"
DEFAULT_MANIFEST = ROOT / "Candidate_Pool" / "manifest.json"
DEFAULT_POOLS = ROOT / "Candidate_Pool" / "by_fish"
DEFAULT_PHOTOS = ROOT / "Photos"
DEFAULT_OUTPUT = ROOT / "mvp_site"
USABLE_VALIDATION_STATUSES = {"ok", "valid", "accepted", "passed", "success"}


@dataclass
class PreparationSummary:
    reference_photos_processed: int = 0
    fish_ids_available: int = 0
    labeling_targets_created: int = 0
    targets_skipped: int = 0
    usable_candidate_pools: int = 0
    candidate_images_indexed: int = 0


def parse_aliases(raw: str | list[str] | None) -> list[str]:
    if isinstance(raw, list):
        values = raw
    else:
        values = (raw or "").split("|")
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def stable_target_id(filename: str, fish_id: str) -> str:
    digest = hashlib.sha256(f"{filename}\0{fish_id}".encode("utf-8")).hexdigest()[:20]
    return f"target_{digest}"


def reference_output_name(filename: str) -> str:
    path = Path(filename)
    safe_stem = "".join(c if c.isalnum() or c in "-_.~" else "_" for c in path.stem)
    digest = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:8]
    return f"{safe_stem}-{digest}.webp"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        # Some source CSVs are exported with a UTF-8 BOM.  Normalize headers
        # so the preparation step works for both BOM and plain UTF-8 files.
        reader.fieldnames = [field.lstrip("\ufeff") for field in (reader.fieldnames or [])]
        return [
            {key.lstrip("\ufeff"): value for key, value in row.items()}
            for row in reader
        ]


def load_taxonomy(path: Path) -> dict[str, dict[str, Any]]:
    taxonomy: dict[str, dict[str, Any]] = {}
    for row in read_csv(path):
        fish_id = (row.get("fish_id") or "").strip()
        name = (row.get("canonical_name") or "").strip()
        if fish_id and name:
            taxonomy[fish_id] = {
                "fish_id": fish_id,
                "canonical_name": name,
                "aliases": parse_aliases(row.get("aliases")),
            }
    return taxonomy


def is_usable_candidate(candidate: dict[str, Any]) -> bool:
    if not candidate.get("candidate_id"):
        return False
    if not (candidate.get("image_url") or candidate.get("thumbnail_url")):
        return False
    status = candidate.get("validation_status")
    return status is None or str(status).strip().lower() in USABLE_VALIDATION_STATUSES


def lightweight_pool(payload: dict[str, Any], taxonomy_entry: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    seen_ids: set[str] = set()
    for candidate in payload.get("candidates", []):
        if not isinstance(candidate, dict) or not is_usable_candidate(candidate):
            continue
        candidate_id = str(candidate["candidate_id"])
        if candidate_id in seen_ids:
            continue
        seen_ids.add(candidate_id)
        candidates.append(
            {
                "candidate_id": candidate_id,
                "image_url": candidate.get("image_url") or "",
                "thumbnail_url": candidate.get("thumbnail_url") or "",
                "source_page_url": candidate.get("source_page_url") or "",
                "source_domain": candidate.get("source_domain") or "",
            }
        )
    return {
        "schema_version": 1,
        "fish_id": taxonomy_entry["fish_id"],
        "canonical_name": taxonomy_entry["canonical_name"],
        "aliases": taxonomy_entry["aliases"],
        "pool_updated_at": payload.get("updated_at"),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def optimize_reference(source: Path, destination: Path, max_dimension: int, quality: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original)
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        # Passing no EXIF/ICC arguments intentionally strips camera, GPS, and device metadata.
        image.save(destination, "WEBP", quality=quality, method=6)


def dataset_id_for(manifest: dict[str, Any], tasks: Iterable[dict[str, Any]], pools: dict[str, dict[str, Any]]) -> str:
    identity = {
        "manifest_generated_at": manifest.get("generated_at"),
        "tasks": [(task["target_id"], task["reference_filename"]) for task in tasks],
        "pools": [(fish_id, pool["candidate_count"]) for fish_id, pool in sorted(pools.items())],
    }
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"fish-mvp-{digest}"


def prepare_site(
    *,
    taxonomy_path: Path = DEFAULT_TAXONOMY,
    targets_path: Path = DEFAULT_TARGETS,
    manifest_path: Path = DEFAULT_MANIFEST,
    pools_dir: Path = DEFAULT_POOLS,
    photos_dir: Path = DEFAULT_PHOTOS,
    output_dir: Path = DEFAULT_OUTPUT,
    max_image_dimension: int = 1600,
    webp_quality: int = 80,
    warn=print,
) -> PreparationSummary:
    summary = PreparationSummary()
    taxonomy = load_taxonomy(taxonomy_path)
    summary.fish_ids_available = len(taxonomy)
    target_rows = read_csv(targets_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    candidate_dir = output_dir / "data" / "candidates"
    reference_dir = output_dir / "assets" / "reference"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    reference_dir.mkdir(parents=True, exist_ok=True)

    pool_cache: dict[str, dict[str, Any] | None] = {}
    prepared_pools: dict[str, dict[str, Any]] = {}
    processed_photos: dict[str, str | None] = {}
    tasks: list[dict[str, Any]] = []

    def get_pool(fish_id: str) -> dict[str, Any] | None:
        if fish_id in pool_cache:
            return pool_cache[fish_id]
        path = pools_dir / f"{fish_id}.json"
        if not path.is_file():
            pool_cache[fish_id] = None
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("fish_id") != fish_id:
                raise ValueError(f"fish_id is {payload.get('fish_id')!r}")
            pool = lightweight_pool(payload, taxonomy[fish_id])
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            warn(f"WARNING: unusable Candidate Pool {path}: {exc}")
            pool = None
        pool_cache[fish_id] = pool
        return pool

    for row in target_rows:
        filename = (row.get("filename") or "").strip()
        fish_id = (row.get("fish_id") or "").strip()
        reason = ""
        if not filename or not fish_id:
            reason = "missing filename or fish_id"
        elif fish_id not in taxonomy:
            reason = f"unknown taxonomy fish_id {fish_id}"
        elif not (photos_dir / filename).is_file():
            reason = f"reference photo not found: {filename}"
        else:
            pool = get_pool(fish_id)
            if pool is None:
                reason = f"Candidate Pool missing or invalid: {fish_id}"
            elif not pool["candidates"]:
                reason = f"Candidate Pool has no usable candidates: {fish_id}"
        if reason:
            summary.targets_skipped += 1
            warn(f"WARNING: skipped target {filename or '<blank>'} / {fish_id or '<blank>'}: {reason}")
            continue

        if filename not in processed_photos:
            output_name = reference_output_name(filename)
            try:
                optimize_reference(
                    photos_dir / filename,
                    reference_dir / output_name,
                    max_image_dimension,
                    webp_quality,
                )
                processed_photos[filename] = output_name
                summary.reference_photos_processed += 1
            except (OSError, UnidentifiedImageError, ValueError) as exc:
                processed_photos[filename] = None
                warn(f"WARNING: could not process reference photo {filename}: {exc}")
        output_name = processed_photos[filename]
        if output_name is None:
            summary.targets_skipped += 1
            continue

        taxonomy_entry = taxonomy[fish_id]
        pool = pool_cache[fish_id]
        assert pool is not None
        prepared_pools[fish_id] = pool
        tasks.append(
            {
                "target_id": stable_target_id(filename, fish_id),
                "fish_id": fish_id,
                "canonical_name": taxonomy_entry["canonical_name"],
                "aliases": taxonomy_entry["aliases"],
                "reference_image": f"assets/reference/{output_name}",
                "reference_filename": filename,
                "candidate_file": f"data/candidates/{fish_id}.json",
                "candidate_count": pool["candidate_count"],
            }
        )

    for fish_id, pool in prepared_pools.items():
        (candidate_dir / f"{fish_id}.json").write_text(
            json.dumps(pool, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    summary.labeling_targets_created = len(tasks)
    summary.usable_candidate_pools = len(prepared_pools)
    summary.candidate_images_indexed = sum(pool["candidate_count"] for pool in prepared_pools.values())
    dataset_id = dataset_id_for(manifest, tasks, prepared_pools)
    index = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "source_manifest_generated_at": manifest.get("generated_at"),
        "task_count": len(tasks),
        "fish_pool_count": len(prepared_pools),
        "candidate_count": summary.candidate_images_indexed,
        "tasks": tasks,
    }
    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    (output_dir / "data" / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    parser.add_argument("--photo-targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-pools", type=Path, default=DEFAULT_POOLS)
    parser.add_argument("--photos", type=Path, default=DEFAULT_PHOTOS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-image-dimension", type=int, default=1600)
    parser.add_argument("--webp-quality", type=int, default=80)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_image_dimension < 1:
        raise SystemExit("--max-image-dimension must be positive")
    if not 1 <= args.webp_quality <= 100:
        raise SystemExit("--webp-quality must be between 1 and 100")
    try:
        summary = prepare_site(
            taxonomy_path=args.taxonomy,
            targets_path=args.photo_targets,
            manifest_path=args.manifest,
            pools_dir=args.candidate_pools,
            photos_dir=args.photos,
            output_dir=args.output,
            max_image_dimension=args.max_image_dimension,
            webp_quality=args.webp_quality,
        )
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"ERROR: preparation failed: {exc}", file=sys.stderr)
        return 1
    print("\nPreparation complete")
    print(f"Reference photos processed: {summary.reference_photos_processed}")
    print(f"Fish IDs available: {summary.fish_ids_available}")
    print(f"Labeling targets created: {summary.labeling_targets_created}")
    print(f"Targets skipped: {summary.targets_skipped}")
    print(f"Usable fish Candidate Pools: {summary.usable_candidate_pools}")
    print(f"Candidate images indexed: {summary.candidate_images_indexed:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
