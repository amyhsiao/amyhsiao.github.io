#!/usr/bin/env python3
"""Mirror a small, frequently used set of candidate thumbnails.

The default is a dry-run. With --download it writes files locally; with
--supabase it uploads them to the public candidate-images bucket. A service
role key is required for uploads and is read only from the environment.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def extension(content_type: str, url: str) -> str:
    value = mimetypes.guess_extension(content_type.split(";")[0].strip()) or Path(url.split("?")[0]).suffix
    return value if value in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else ".jpg"


def upload(url: str, path: str, payload: bytes, content_type: str, key: str) -> None:
    request = urllib.request.Request(
        f"{url.rstrip('/')}/storage/v1/object/candidate-images/{path}",
        data=payload,
        method="POST",
        headers={"Authorization": f"Bearer {key}", "apikey": key, "Content-Type": content_type, "x-upsert": "true"},
    )
    with urllib.request.urlopen(request, timeout=30):
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit-per-fish", type=int, default=2)
    parser.add_argument("--output", type=Path, default=ROOT / "mvp_site" / "assets" / "candidate-thumbnails")
    parser.add_argument("--download", action="store_true", help="download to the local output directory")
    parser.add_argument("--supabase", action="store_true", help="upload to Supabase Storage")
    args = parser.parse_args()
    if args.limit_per_fish < 1 or not (args.download or args.supabase):
        parser.error("請指定 --download 或 --supabase，且 --limit-per-fish 至少為 1")
    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if args.supabase and (not supabase_url or not service_key):
        parser.error("Supabase 上傳需要 SUPABASE_URL 與 SUPABASE_SERVICE_ROLE_KEY 環境變數")

    manifest = []
    for source in sorted((ROOT / "mvp_site" / "data" / "candidates").glob("fish_*.json")):
        payload = json.loads(source.read_text(encoding="utf-8"))
        for candidate in payload.get("candidates", [])[: args.limit_per_fish]:
            source_url = candidate.get("thumbnail_url") or candidate.get("image_url")
            if not source_url:
                continue
            request = urllib.request.Request(source_url, headers={"User-Agent": "FishImageMirror/1.0"})
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    data = response.read()
                    content_type = response.headers.get("Content-Type", "image/jpeg")
            except Exception as error:  # noqa: BLE001 - continue with other candidates
                print(f"WARNING: {candidate.get('candidate_id')}: {error}")
                continue
            safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(candidate["candidate_id"]))
            relative = f"{source.stem}/{safe_id}{extension(content_type, source_url)}"
            if args.download:
                destination = args.output / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            if args.supabase:
                upload(supabase_url, relative, data, content_type, service_key)
                candidate["thumbnail_url"] = f"{supabase_url.rstrip('/')}/storage/v1/object/public/candidate-images/{relative}"
            manifest.append({"candidate_id": candidate["candidate_id"], "path": relative, "source_url": source_url})
        if args.supabase:
            source.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_manifest = args.output / "manifest.json" if args.download else ROOT / "Candidate_Pool" / "mirrored_candidate_images.json"
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Mirrored {len(manifest)} candidate thumbnails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
