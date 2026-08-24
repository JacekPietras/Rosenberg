#!/usr/bin/env python3
"""Download image URLs from letter JSON files when the local cache is missing.

The JSON remains unchanged: the viewer derives the cache filename from each
image URL and falls back to that URL when the local file is unavailable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import Request, build_opener


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
LETTER_DIR = REPOSITORY_ROOT / "data" / "letters"
IMAGE_DIR = REPOSITORY_ROOT / "data" / "images" / "letters"
REQUEST_TIMEOUT = 60
USER_AGENT = "Rosenberg research image cache/1.0"
IMAGE_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}


def cache_name(image_url: str) -> str:
    parts = urlsplit(image_url)
    original = parse_qs(parts.query).get("originalBilddatei", [""])[0]
    name = Path(unquote(original or parts.path)).name
    if not name or Path(name).suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError(f"cannot determine an image filename from {image_url}")
    return name


def image_urls() -> list[str]:
    urls = set()
    for path in sorted(LETTER_DIR.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for entry in document.get("entries", []):
            values = entry.get("img", [])
            values = [values] if isinstance(values, (str, dict)) else values
            urls.update(
                image_url
                for value in values
                for image_url in [value.get("src") if isinstance(value, dict) else value]
                if isinstance(image_url, str) and image_url.startswith(("http://", "https://"))
            )
    return sorted(urls)


def main() -> int:
    opener = build_opener()
    downloaded = 0
    skipped = 0
    failures = 0
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for image_url in image_urls():
        try:
            target = IMAGE_DIR / cache_name(image_url)
            if target.exists() and target.stat().st_size:
                skipped += 1
                continue
            request = Request(image_url, headers={"User-Agent": USER_AGENT})
            with opener.open(request, timeout=REQUEST_TIMEOUT) as response:
                contents = response.read()
            if not contents:
                raise ValueError("the server returned an empty response")
            target.write_bytes(contents)
            downloaded += 1
            print(f"Downloaded {target.relative_to(REPOSITORY_ROOT)}")
        except Exception as error:
            failures += 1
            print(f"Error: {image_url}: {error}", file=sys.stderr)
    print(f"Image cache: {downloaded} downloaded, {skipped} already present, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
