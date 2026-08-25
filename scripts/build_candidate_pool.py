#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Make direct execution from the project root work without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fish_candidate_pipeline.config import load_config
from fish_candidate_pipeline.inputs import inspect_inputs
from fish_candidate_pipeline.pipeline import CandidatePoolBuilder
from fish_candidate_pipeline.providers import ProviderError, create_provider
from fish_candidate_pipeline.queries import generate_queries

LOGGER = logging.getLogger("candidate_pool.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build resumable per-fish candidate image URL pools.")
    parser.add_argument("--config", type=Path, default=Path("config/candidate_pool.yaml"))
    parser.add_argument("--taxonomy-path", type=Path)
    parser.add_argument("--photo-targets-path", type=Path)
    parser.add_argument("--photos-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--provider")
    parser.add_argument("--target-per-fish", type=int)
    parser.add_argument("--query-template", dest="query_templates", action="append")
    parser.add_argument("--max-results-per-query", type=int)
    parser.add_argument("--max-queries-per-fish", type=int)
    parser.add_argument("--oversample-factor", type=float)
    parser.add_argument("--provider-page-size", type=int)
    parser.add_argument("--workers", type=int)
    parser.add_argument("--http-timeout", type=float)
    parser.add_argument("--retry-count", type=int)
    parser.add_argument("--retry-backoff", type=float)
    parser.add_argument("--max-provider-requests", type=int)
    parser.add_argument("--processing-priority", choices=("coverage_first", "input_order"))
    parser.add_argument("--dedupe-mode", choices=("url", "url+phash"))
    parser.add_argument("--phash-threshold", type=int)
    parser.add_argument("--validation", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--max-image-bytes", type=int)
    parser.add_argument("--fish-ids", nargs="+")
    parser.add_argument("--all-taxonomy", action="store_true")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        if args.force and args.resume is False:
            LOGGER.warning("--force already disables loading existing per-fish candidates")
        config_path = args.config if args.config and args.config.is_file() else None
        if args.config and config_path is None and args.config != Path("config/candidate_pool.yaml"):
            raise ValueError(f"Config file not found: {args.config}")
        override_names = (
            "taxonomy_path", "photo_targets_path", "photos_dir", "output_dir", "provider",
            "target_per_fish", "query_templates", "max_results_per_query", "max_queries_per_fish",
            "oversample_factor", "provider_page_size", "workers", "http_timeout", "retry_count",
            "retry_backoff", "max_provider_requests", "processing_priority", "dedupe_mode",
            "phash_threshold", "validation", "max_image_bytes",
        )
        overrides = {name: getattr(args, name) for name in override_names}
        config = load_config(config_path, overrides)
        report = inspect_inputs(config.taxonomy_path, config.photo_targets_path, config.photos_dir)
        selected_ids = list(report.taxonomy) if args.all_taxonomy else list(report.target_fish_ids)
        if args.fish_ids:
            invalid_selected = sorted(set(args.fish_ids) - report.taxonomy.keys())
            if invalid_selected:
                raise ValueError(f"Unknown --fish-ids: {', '.join(invalid_selected)}")
            selected_ids = list(dict.fromkeys(args.fish_ids))
        fishes = [report.taxonomy[fish_id] for fish_id in selected_ids]
        _report_inputs(report, fishes)
        if args.dry_run:
            _report_plan(config, fishes)
            LOGGER.info("Dry run complete: no API calls and no candidate output writes were made")
            return 0
        provider = create_provider(
            config.provider,
            timeout=config.http_timeout,
            retry_count=config.retry_count,
            retry_backoff=config.retry_backoff,
            max_requests=config.max_provider_requests,
        )
        builder = CandidatePoolBuilder(config, provider)
        summaries = builder.build(
            fishes, resume=args.resume, force=args.force, missing_photos=report.missing_photos
        )
        failed = sum(summary.status == "failed" for summary in summaries)
        partial = sum(summary.status == "partial" for summary in summaries)
        not_started = sum(summary.status == "not_started" for summary in summaries)
        complete = len(summaries) - partial - failed - not_started
        LOGGER.info(
            "Run finished: %d complete, %d partial, %d failed, %d not started; provider HTTP attempts=%d",
            complete, partial, failed, not_started, getattr(provider, "request_count", 0),
        )
        if builder.halt_reason:
            return 3
        return 1 if failed else 0
    except (ValueError, OSError, ProviderError) as exc:
        LOGGER.error("%s", exc)
        return 2


def _report_inputs(report, fishes) -> None:
    LOGGER.info(
        "Inputs: %d taxonomy fish, %d target rows, %d unique target photos, %d target fish",
        len(report.taxonomy), report.target_row_count, len(report.unique_target_photos), len(report.target_fish_ids),
    )
    if report.duplicate_target_rows:
        LOGGER.warning("Duplicate photo-target rows ignored: %d", report.duplicate_target_rows)
    if report.missing_photos:
        LOGGER.warning("Missing referenced photos (%d): %s", len(report.missing_photos), ", ".join(report.missing_photos))
    LOGGER.info("Selected fish (%d): %s", len(fishes), ", ".join(fish.fish_id for fish in fishes))


def _report_plan(config, fishes) -> None:
    LOGGER.info("Configuration:\n%s", json.dumps(config.public_dict(), ensure_ascii=False, indent=2))
    for fish in fishes:
        queries = generate_queries(fish, config.query_templates)[: config.max_queries_per_fish]
        LOGGER.info(
            "%s %s | aliases=%s | queries=%s",
            fish.fish_id, fish.canonical_name, list(fish.aliases), json.dumps(queries, ensure_ascii=False),
        )


if __name__ == "__main__":
    raise SystemExit(main())
