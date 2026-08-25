# Fish candidate-pool pipeline

This pipeline builds URL-and-metadata-only image candidate pools. It does not modify `Photos/`, retain externally downloaded images, or implement any website, annotation, database, or deployment functionality.

## Setup

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-candidate-pool.txt
```

## Environment

The SerpAPI provider reads its key only from the environment:

```bash
export SERPAPI_API_KEY="your-key-here"
```

`.env.example` is a credential-free template. The CLI deliberately does not parse `.env`; if desired, load it through your shell before running the command. Never commit a populated `.env`.

## Commands

Validate the CSVs, inspect `Photos/`, and print the complete query plan without API calls or output writes:

```bash
python scripts/build_candidate_pool.py --dry-run
```

Run one small pool:

```bash
python scripts/build_candidate_pool.py \
  --fish-ids fish_001 \
  --target-per-fish 10
```

Run all fish referenced by `photo_targets.csv` (the default selection):

```bash
python scripts/build_candidate_pool.py \
  --target-per-fish 100 \
  --resume
```

Increase existing pools without discarding accepted records:

```bash
python scripts/build_candidate_pool.py \
  --target-per-fish 200 \
  --resume
```

Search every taxonomy row, including fish with no reference photo:

```bash
python scripts/build_candidate_pool.py --all-taxonomy --target-per-fish 100
```

Rebuild selected pools explicitly:

```bash
python scripts/build_candidate_pool.py --fish-ids fish_001 --force
```

Use pHash near-duplicate filtering or skip network image validation:

```bash
python scripts/build_candidate_pool.py --dedupe-mode url+phash --phash-threshold 6
python scripts/build_candidate_pool.py --no-validation
```

`url+phash` still fetches candidate image bytes because hashing requires them. Bytes are held only in memory and discarded; no external image is written to disk.

## Configuration

Defaults live in `config/candidate_pool.yaml`. CLI flags override YAML values. Configurable fields include all input/output paths, provider, target size, query templates, per-query/query-count limits, oversampling, page size, workers, timeouts, retries/backoff, validation, and deduplication settings.

The default query strategy searches each canonical name exactly as written and each alias only as `"{alias} 魚"`. The default `retry_count: 1` means one retry after the initial attempt, for at most two HTTP attempts. `max_provider_requests: 50` is a hard per-process SerpAPI HTTP-attempt cap, including retries; HTTP 429 and authentication/quota failures stop the full run immediately after saving progress.

`processing_priority: coverage_first` uses two phases. While any selected fish has no candidates and no search progress, only those untouched fish are processed, using one canonical-name query page each. After every selected fish has search progress, later resume runs fill partial pools toward the configured target. Use `--processing-priority input_order` only when sequentially completing pools is explicitly desired.

Additional taxonomy columns can be used in templates without code changes. For example, after adding a real `english_name` CSV column, add `"{english_name} fish"` to `query_templates`. Missing or blank optional fields expand to blank; no scientific names are fabricated.

The finite search ceiling is the smaller of `target_per_fish × oversample_factor` and the combined per-query limits. Collection stops when the usable target is reached or that ceiling/query pagination is exhausted.

## Outputs and resume behavior

The CLI writes:

```text
Candidate_Pool/
├── manifest.json
├── summary.csv
├── candidates.csv
├── by_fish/<fish_id>.json
└── logs/search_log.jsonl
```

Each fish JSON contains its candidate records and per-query pagination offsets. Writes use temporary files followed by atomic replacement, and progress is saved after every result batch. `--resume` is enabled by default; `--no-resume` starts selected pools from scratch, while `--force` is the explicit rebuild option.

Candidate IDs are deterministic SHA-256-derived identifiers based on `fish_id` plus the normalized direct image URL. Deduplication is intentionally per fish, so one external image may occur under multiple fish IDs.

## Tests

```bash
pytest -q
```

Tests use the fake provider and stubbed validation only. They never call SerpAPI or the public internet.

## Operational limitations

- Search results are candidates, not verified labels; a human still needs to assess relevance and rights.
- External URLs can expire or change after validation.
- MIME headers are advisory; Pillow decoding is used when validation is enabled.
- SerpAPI Google Images pagination is fetched in provider pages and cached in-process. API quota, rate limits, and provider terms remain the operator's responsibility.
- pHash catches visually similar images but can produce false positives or miss crops/major edits; tune the Hamming-distance threshold for the dataset.
