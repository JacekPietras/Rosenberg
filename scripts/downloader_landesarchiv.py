#!/usr/bin/env python3
"""Create a review document record from a Landesarchiv BW permalink."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import Request, build_opener

from download_landesarchiv import discover_viewer, read_viewer, image_urls as archive_image_urls


USER_AGENT = "Rosenberg research downloader/1.0"
REQUEST_TIMEOUT = 60
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DOCUMENT_DIR = REPOSITORY_ROOT / "data" / "documents"
MONTHS = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}


class CatalogDetails(HTMLParser):
    """Collect labeled metadata fields from the archive's details page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_cell = False
        self.cell: list[str] = []
        self.cells: list[str] = []
        self.fields: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.cells = []
        elif tag == "td":
            self.in_cell = True
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_cell:
            value = " ".join("".join(self.cell).split())
            self.cells.append(value)
            self.in_cell = False
        elif tag == "tr":
            if len(self.cells) >= 2 and self.cells[0]:
                label = self.cells[0].casefold().rstrip(":")
                self.fields[label] = self.cells[1]
            self.cells = []


def fetch_page(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with build_opener().open(request, timeout=REQUEST_TIMEOUT) as response:
        if "html" not in response.headers.get_content_type():
            raise ValueError("The permalink did not return an HTML catalogue page")
        return response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")


def iso_date(value: str) -> str:
    """Convert common Landesarchiv German date labels to the JSON ISO format."""
    value = value.strip()
    iso_match = re.search(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", value)
    if iso_match:
        return "-".join(iso_match.groups())
    german_match = re.search(
        r"(?<!\d)(\d{4})\s+([A-Za-zÄÖÜäöüß]+)\s+(\d{1,2})(?!\d)", value
    )
    if german_match:
        year, month, day = german_match.groups()
        month_number = MONTHS.get(month.casefold())
        if month_number:
            return f"{year}-{month_number:02d}-{int(day):02d}"
    year_match = re.search(r"(?<!\d)(\d{4})(?!\d)", value)
    if year_match:
        return year_match.group(1)
    raise ValueError(f"Could not determine the document date from catalogue label: {value!r}")


def dated_document_paths(date: str) -> list[Path]:
    stem = re.sub(r"[^0-9-]+", "_", date)
    pattern = re.compile(rf"{re.escape(stem)}(?:_(\d+))?\.json$")
    paths = [path for path in DOCUMENT_DIR.glob(f"{stem}*.json") if pattern.fullmatch(path.name)]
    return sorted(paths, key=lambda path: (int(pattern.fullmatch(path.name).group(1) or 1), path.name))


def next_output_path(date: str, existing_paths: list[Path]) -> Path:
    stem = re.sub(r"[^0-9-]+", "_", date)
    if not existing_paths:
        return DOCUMENT_DIR / f"{stem}.json"
    pattern = re.compile(rf"{re.escape(stem)}(?:_(\d+))?\.json$")
    suffixes = [
        int(match.group(1))
        for path in existing_paths
        if (match := pattern.fullmatch(path.name)) and match.group(1)
    ]
    return DOCUMENT_DIR / f"{stem}_{max(suffixes, default=1) + 1}.json"


def update_existing(path: Path, source: str, generated_entry: dict[str, object]) -> bool:
    document = json.loads(path.read_text(encoding="utf-8"))
    for entry in document.get("entries", []):
        if not isinstance(entry, dict) or entry.get("source") != source:
            continue
        entry["url"] = generated_entry["url"]
        if "german" in generated_entry:
            entry["german"] = generated_entry["german"]
        elif document.get("transcribed") is not True:
            entry.pop("german", None)
        if "img" in generated_entry:
            entry["img"] = generated_entry["img"]
        else:
            entry.pop("img", None)
        labels = document.get("label", [])
        labels = [labels] if isinstance(labels, str) else list(labels)
        if "to review" not in labels:
            labels.append("to review")
        document["label"] = labels
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True
    return False


def create_record(url: str, catalog_id: str | None = None, bestand: str | None = None,
                  skip_existing: bool = False, has_viewer: bool = False, delay: float = 3) -> tuple[Path, bool]:
    from urllib.parse import parse_qs, urlsplit

    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {"www.landesarchiv-bw.de", "landesarchiv-bw.de"}:
        raise ValueError("Expected an https://www.landesarchiv-bw.de/plink/ URL")
    aid = parse_qs(parsed.query).get("f", [""])[0]
    if not aid:
        raise ValueError("The permalink has no f= archive identifier")

    images = []
    if catalog_id:
        if not catalog_id.isdigit() or not bestand or not bestand.isdigit():
            raise ValueError("Catalog ID and Bestand must be numeric")
        details_url = "https://www2.landesarchiv-bw.de/ofs21/olf/druckansicht.php?" + urlencode(
            {"id_titlaufn": catalog_id, "bestand": bestand})
    else:
        opener = build_opener()
        viewer_url, fields, page_names, scope_id = discover_viewer(opener, url)
        details_url = urljoin(viewer_url, "../olf/druckansicht.php") + "?" + urlencode(
            {"id_titlaufn": fields["id"], "bestand": fields["bestand"]})
        images = archive_image_urls(viewer_url, fields, page_names, scope_id)
    details = CatalogDetails()
    details.feed(fetch_page(details_url))
    if catalog_id and has_viewer:
        time.sleep(delay)
        zoom_url = "https://www2.landesarchiv-bw.de/ofs21/bild_zoom/zoom.php?" + urlencode(
            {"bestand": bestand, "id": catalog_id})
        viewer_url, viewer_fields, page_names, scope_id = read_viewer(build_opener(), zoom_url, catalog_id, aid)
        images = archive_image_urls(viewer_url, viewer_fields, page_names, scope_id)
    source = details.fields.get("bestellsignatur")
    date_text = details.fields.get("laufzeit")
    german = details.fields.get("titel")
    if not source or not date_text or not german:
        raise ValueError(f"Could not find citation, date, or title for archive ID {aid}")
    source = " ".join(source.split())
    date = iso_date(date_text)
    siegler = details.fields.get("siegler")
    if siegler:
        german += f"\n\nSiegler: {siegler}"

    generated_entry: dict[str, object] = {"source": source, "url": url, "german": german}
    if images:
        generated_entry["img"] = [{"src": image_url} for image_url in images]

    DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
    from downloader_arcinsys_hessen import save_record
    record = {"date": date, "label": ["to review"], "entries": [generated_entry]}
    path, existing = save_record(record, skip_existing=skip_existing)
    if existing and images:
        document = json.loads(path.read_text(encoding="utf-8"))
        for entry in document.get("entries", []):
            sources = entry.get("source", [])
            sources = sources if isinstance(sources, list) else [sources]
            if source not in sources:
                continue
            current = entry.get("img", [])
            current = current if isinstance(current, list) else [current]
            known = {item.get("src") for item in current if isinstance(item, dict)}
            for image in images:
                if image not in known:
                    current.append({"src": image})
                    known.add(image)
            entry["img"] = current
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            break
    return path, existing



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Landesarchiv BW permalink")
    parser.add_argument("--catalog-id", help="legacy catalogue record ID")
    parser.add_argument("--bestand", help="legacy catalogue collection ID")
    parser.add_argument("--skip-existing", action="store_true", help="preserve existing source entries")
    parser.add_argument("--has-viewer", action="store_true", help="resolve the viewer linked in search results")
    parser.add_argument("--delay", type=float, default=3, help="seconds between catalogue and viewer requests")
    args = parser.parse_args()
    try:
        path, updated = create_record(args.url, args.catalog_id, args.bestand, args.skip_existing, args.has_viewer, args.delay)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if updated and args.skip_existing:
        print(f"Existing or merged file: {path.relative_to(REPOSITORY_ROOT)}")
    elif updated:
        print(f"Only updated existing file: {path.relative_to(REPOSITORY_ROOT)}")
    else:
        print(path.relative_to(REPOSITORY_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
