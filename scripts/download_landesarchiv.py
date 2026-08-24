#!/usr/bin/env python3
"""Link or download digitized pages from a Landesarchiv permalink.

The archive's /plink/ URL is a catalogue permalink.  This script follows it to
the legacy viewer, discovers the page filenames and stores direct inline image
URLs from the viewer's own image endpoint.  By default only those URLs are
stored; use ``--mode download`` to also save the image files locally.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlencode, urljoin, urlsplit
from urllib.request import Request, build_opener


USER_AGENT = "Rosenberg research downloader/1.0"
REQUEST_TIMEOUT = 60
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
LETTER_DIR = REPOSITORY_ROOT / "data" / "letters"
IMAGE_DIR = REPOSITORY_ROOT / "data" / "images"
PLINK_RE = re.compile(r"/plink/\?(?:[^#]*&)?f=([^&#]+)", re.I)
ID_RE = re.compile(r"title=\"Id:\s*(\d+).*?AID:\s*([^\"\s]+)", re.I | re.S)
HIDDEN_RE = re.compile(
    r'<input\s+[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']',
    re.I,
)
IMAGE_SELECT_RE = re.compile(
    r'<select\s+[^>]*name=["\']originalBilddatei["\'][^>]*>(.*?)</select>',
    re.I | re.S,
)
OPTION_RE = re.compile(
    r'<option\s+[^>]*value=["\']([^"\']+)["\'][^>]*>', re.I
)
SCOPE_RE = re.compile(r"scopeid_besta=(\d+)", re.I)


def fetch(opener, url: str) -> tuple[str, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with opener.open(request, timeout=REQUEST_TIMEOUT) as response:
        content_type = response.headers.get_content_type()
        body = response.read()
        if content_type.startswith("text/") or "html" in content_type:
            return response.geturl(), body.decode(response.headers.get_content_charset() or "utf-8", "replace")
        return response.geturl(), body


def discover_viewer(opener, permalink: str) -> tuple[str, dict[str, str], list[str], str]:
    match = PLINK_RE.search(permalink)
    if not match:
        raise ValueError("URL does not look like a Landesarchiv /plink/?f=... permalink")

    landing_url, landing_html = fetch(opener, permalink)
    if not isinstance(landing_html, str):
        raise ValueError("The permalink did not return an HTML catalogue page")

    aid = match.group(1)
    record_id = None
    for found_id, found_aid in ID_RE.findall(landing_html):
        if html.unescape(found_aid).strip() == aid:
            record_id = found_id
            break
    if record_id is None:
        raise ValueError(f"No catalogue record with AID {aid} was found; it may have no digitized image")

    zoom_match = re.search(
        rf"bild_zoom/(?:zoom|thumbnails)\.php\?[^\"' ]*?id={re.escape(record_id)}[^\"' ]*",
        landing_html,
        re.I,
    )
    if not zoom_match:
        raise ValueError(f"Record {aid} has no image viewer link")
    zoom_path = html.unescape(zoom_match.group(0))
    if not zoom_path.startswith("../"):
        zoom_path = "../" + zoom_path
    zoom_url = urljoin(landing_url, zoom_path)
    viewer_url, viewer_html = fetch(opener, zoom_url)
    if not isinstance(viewer_html, str):
        raise ValueError("The image viewer did not return HTML")

    fields = dict(HIDDEN_RE.findall(viewer_html))
    fields.setdefault("id", record_id)
    fields.setdefault("aid", aid)
    image_select = IMAGE_SELECT_RE.search(viewer_html)
    page_names = list(dict.fromkeys(OPTION_RE.findall(image_select.group(1)))) if image_select else []
    if not page_names and fields.get("bilddatei"):
        page_names = [fields["bilddatei"]]
    if not page_names:
        raise ValueError(f"The viewer for {aid} contains no page filenames")
    scope_match = SCOPE_RE.search(viewer_html)
    if not scope_match:
        raise ValueError(f"The viewer for {aid} has no image scope identifier")
    return viewer_url, fields, page_names, scope_match.group(1)


def image_urls(viewer_url: str, fields: dict[str, str], page_names: list[str], scope_id: str) -> list[str]:
    endpoint = urljoin(viewer_url, "bild.php")
    urls = []
    for page_name in page_names:
        image_folder = fields.get("bildordner")
        if not image_folder:
            folder_match = re.match(r"(\d{2})_(\d{10})_", page_name)
            if not folder_match:
                raise ValueError(f"Cannot determine image folder for {page_name}")
            image_folder = (
                f"/data/bildcms/internetbilder/archiv_{int(folder_match.group(1))}/olf/"
                f"bestand_{int(scope_id):010d}/titlaufn_{folder_match.group(2)}/"
            )
        query = {
            "drehen": fields.get("drehen", ""),
            "zoom": "100",
            "gamma": "1",
            "jpegQualitaetZoombild": "60",
            "scopeid_besta": scope_id,
            "originalBilddatei": f"{image_folder}{page_name}",
        }
        urls.append(f"{endpoint}?{urlencode(query)}")
    return urls


def download_images(opener, image_paths: list[str], page_names: list[str], image_dir: Path) -> list[str]:
    image_dir.mkdir(parents=True, exist_ok=True)
    stored_paths = []
    for image_url, page_name in zip(image_paths, page_names):
        filename = Path(unquote(urlsplit(image_url).query.split("originalBilddatei=", 1)[-1])).name
        if not filename:
            filename = Path(page_name).name
        target = image_dir / filename
        request = Request(image_url, headers={"User-Agent": USER_AGENT})
        with opener.open(request, timeout=REQUEST_TIMEOUT) as response:
            contents = response.read()
        if not contents:
            raise ValueError(f"The archive returned an empty image for {page_name}")
        target.write_bytes(contents)
        stored_paths.append(target.relative_to(IMAGE_DIR).as_posix())
    return stored_paths


def update_letter_json(aid: str, image_paths: list[str], replace_images: bool = False) -> list[Path]:
    matches = []
    for path in sorted(LETTER_DIR.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for entry in document.get("entries", []):
            urls = entry.get("url", [])
            urls = [urls] if isinstance(urls, str) else urls
            if any(re.search(r"[?&]f=" + re.escape(aid) + r"(?:$|&)", str(url)) for url in urls):
                existing = entry.get("img", [])
                existing = [existing] if isinstance(existing, (str, dict)) else existing
                existing = [
                    value if isinstance(value, dict) else {"src": value, "seals": []}
                    for value in existing
                ]
                if replace_images:
                    entry["img"] = [{"src": value, "seals": []} for value in image_paths]
                else:
                    known = {value.get("src") for value in existing}
                    entry["img"] = existing + [
                        {"src": value, "seals": []}
                        for value in image_paths
                        if value not in known
                    ]
                matches.append((path, document))
    if not matches:
        raise ValueError(f"No letter JSON entry found for AID {aid}")
    paths = []
    for path, document in matches:
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Landesarchiv URL, for example https://www.landesarchiv-bw.de/plink/?f=4-1723539")
    parser.add_argument(
        "--mode",
        choices=("links", "download"),
        default="links",
        help="store direct archive URLs (default) or download files into data/images/",
    )
    parser.add_argument(
        "--image-dir",
        default="letters",
        help="subdirectory of data/images/ used with --mode download (default: letters)",
    )
    args = parser.parse_args()

    image_dir = (IMAGE_DIR / args.image_dir).resolve()
    if IMAGE_DIR not in image_dir.parents:
        parser.error("--image-dir must stay inside data/images/")

    opener = build_opener()
    try:
        viewer_url, fields, page_names, scope_id = discover_viewer(opener, args.url)
        image_paths = image_urls(viewer_url, fields, page_names, scope_id)
        if args.mode == "download":
            image_paths = download_images(opener, image_paths, page_names, image_dir)
        letter_paths = update_letter_json(fields["aid"], image_paths, replace_images=args.mode == "download")
        for letter_path in letter_paths:
            print(f"Updated letter JSON: {letter_path}")
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
