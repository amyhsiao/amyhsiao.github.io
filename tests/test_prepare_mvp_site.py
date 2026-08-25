from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from PIL import Image


SCRIPT = Path(__file__).parents[1] / "scripts" / "prepare_mvp_site.py"
SPEC = importlib.util.spec_from_file_location("prepare_mvp_site", SCRIPT)
assert SPEC and SPEC.loader
prepare = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = prepare
SPEC.loader.exec_module(prepare)


def write_fixture(root: Path) -> dict[str, Path]:
    fish_map = root / "Fish_Map"
    pools = root / "Candidate_Pool" / "by_fish"
    photos = root / "Photos"
    output = root / "mvp_site"
    fish_map.mkdir(parents=True)
    pools.mkdir(parents=True)
    photos.mkdir()
    (fish_map / "fish_taxonomy.csv").write_text(
        "fish_id,canonical_name,aliases\nfish_001,甲魚,甲\nfish_002,乙魚,\n",
        encoding="utf-8",
    )
    (fish_map / "photo_targets.csv").write_text(
        "filename,fish_id\nshared.jpg,fish_001\nshared.jpg,fish_002\nother.jpg,fish_001\nmissing.jpg,fish_001\n",
        encoding="utf-8",
    )
    Image.new("RGB", (2000, 1000), "red").save(photos / "shared.jpg", exif=b"Exif\x00\x00test")
    Image.new("RGB", (120, 80), "blue").save(photos / "other.jpg")
    original_hash = hashlib.sha256((photos / "shared.jpg").read_bytes()).hexdigest()
    for fish_id, name in [("fish_001", "甲魚"), ("fish_002", "乙魚")]:
        candidates = [
            {
                "candidate_id": f"upstream-{fish_id}",
                "image_url": f"https://example.test/{fish_id}.jpg",
                "thumbnail_url": "",
                "source_page_url": "https://example.test/source",
                "source_domain": "example.test",
                "validation_status": "ok",
            },
            {
                "candidate_id": f"invalid-{fish_id}",
                "image_url": "https://example.test/bad.jpg",
                "validation_status": "invalid",
            },
        ]
        (pools / f"{fish_id}.json").write_text(
            json.dumps({"fish_id": fish_id, "canonical_name": name, "aliases": [], "updated_at": "now", "candidates": candidates}),
            encoding="utf-8",
        )
    manifest = root / "Candidate_Pool" / "manifest.json"
    manifest.write_text(json.dumps({"generated_at": "2026-01-01T00:00:00Z"}), encoding="utf-8")
    return {
        "taxonomy": fish_map / "fish_taxonomy.csv",
        "targets": fish_map / "photo_targets.csv",
        "manifest": manifest,
        "pools": pools,
        "photos": photos,
        "output": output,
        "original_hash": original_hash,
    }


def test_preparation_handles_multi_target_multi_photo_and_missing(tmp_path: Path) -> None:
    paths = write_fixture(tmp_path)
    warnings: list[str] = []
    summary = prepare.prepare_site(
        taxonomy_path=paths["taxonomy"], targets_path=paths["targets"], manifest_path=paths["manifest"],
        pools_dir=paths["pools"], photos_dir=paths["photos"], output_dir=paths["output"],
        max_image_dimension=300, webp_quality=75, warn=warnings.append,
    )
    index = json.loads((paths["output"] / "data/index.json").read_text(encoding="utf-8"))
    assert summary.reference_photos_processed == 2
    assert summary.labeling_targets_created == 3
    assert summary.targets_skipped == 1
    assert len({task["target_id"] for task in index["tasks"]}) == 3
    assert sum(task["reference_filename"] == "shared.jpg" for task in index["tasks"]) == 2
    assert sum(task["fish_id"] == "fish_001" for task in index["tasks"]) == 2
    assert any("missing.jpg" in warning for warning in warnings)


def test_candidate_ids_unchanged_and_photos_optimized_without_source_mutation(tmp_path: Path) -> None:
    paths = write_fixture(tmp_path)
    prepare.prepare_site(
        taxonomy_path=paths["taxonomy"], targets_path=paths["targets"], manifest_path=paths["manifest"],
        pools_dir=paths["pools"], photos_dir=paths["photos"], output_dir=paths["output"],
        max_image_dimension=300, webp_quality=75, warn=lambda _message: None,
    )
    pool = json.loads((paths["output"] / "data/candidates/fish_001.json").read_text(encoding="utf-8"))
    assert [candidate["candidate_id"] for candidate in pool["candidates"]] == ["upstream-fish_001"]
    assert hashlib.sha256((paths["photos"] / "shared.jpg").read_bytes()).hexdigest() == paths["original_hash"]
    references = list((paths["output"] / "assets/reference").glob("*.webp"))
    assert len(references) == 2
    with Image.open(next(path for path in references if path.name.startswith("shared"))) as image:
        assert max(image.size) == 300
        assert not image.getexif()
    with Image.open(next(path for path in references if path.name.startswith("other"))) as image:
        assert image.size == (120, 80)  # no upscaling
