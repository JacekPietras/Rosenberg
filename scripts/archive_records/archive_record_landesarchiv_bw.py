#!/usr/bin/env python3
"""Create a review document record from a Landesarchiv BW permalink."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import Request, build_opener

USER_AGENT = "Rosenberg research downloader/1.0"
REQUEST_TIMEOUT = 60
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent.parent
DOCUMENT_DIR = REPOSITORY_ROOT / "data" / "documents"
MONTHS = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "maerz": 3,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}


PLINK_RE = re.compile(r"/plink/\?(?:[^#]*&)?f=([^&#]+)", re.I)
ID_RE = re.compile(r'title="Id:\s*(\d+).*?AID:\s*([^"\s]+)', re.I | re.S)
HIDDEN_RE = re.compile(
    r'<input\s+[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']',
    re.I,
)
IMAGE_SELECT_RE = re.compile(
    r'<select\s+[^>]*name=["\']originalBilddatei["\'][^>]*>(.*?)</select>',
    re.I | re.S,
)
OPTION_RE = re.compile(
    r'<option\s+[^>]*value=["\']([^"\']+)["\'][^>]*>\s*'
    r'(recto|verso|Bild\s*\d+)\s*</option>',
    re.I,
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


def discover_viewer(opener, permalink: str) -> tuple[str, str, dict[str, str], list[str], str]:
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

    # The permalink may resolve directly to a catalogue record without any
    # digitized images. In that case the landing page still provides enough
    # information to fetch its printable metadata page.
    bestand = parse_qs(urlsplit(landing_url).query).get("bestand", [None])[0]
    if not bestand:
        bestand_match = re.search(r"[?&]bestand=(\d+)", landing_html)
        bestand = bestand_match.group(1) if bestand_match else None
    if not bestand:
        raise ValueError(f"Could not determine the collection for archive ID {aid}")
    details_url = "https://www2.landesarchiv-bw.de/ofs21/olf/druckansicht.php?" + urlencode(
        {"id_titlaufn": record_id, "bestand": bestand}
    )

    zoom_match = re.search(
        rf"bild_zoom/(?:zoom|thumbnails)\.php\?[^\"' ]*?id={re.escape(record_id)}[^\"' ]*",
        landing_html,
        re.I,
    )
    if not zoom_match:
        return details_url, "", {}, [], ""
    zoom_path = html.unescape(zoom_match.group(0))
    # Some catalogue records link to the thumbnail-selection page instead of
    # the image viewer.  The thumbnail page does not contain the form fields
    # needed to construct the direct image URLs, but it uses the same
    # ``bestand`` and ``id`` parameters as zoom.php.
    zoom_path = re.sub(r"/thumbnails\.php(?=\?)", "/zoom.php", zoom_path, flags=re.I)
    if not zoom_path.startswith("../"):
        zoom_path = "../" + zoom_path
    zoom_url = urljoin(landing_url, zoom_path)
    viewer_url, fields, page_names, scope_id = read_viewer(opener, zoom_url, record_id, aid)
    details_url = urljoin(viewer_url, "../olf/druckansicht.php") + "?" + urlencode(
        {"id_titlaufn": fields["id"], "bestand": fields["bestand"]}
    )
    return details_url, viewer_url, fields, page_names, scope_id


def read_viewer(opener, zoom_url: str, record_id: str, aid: str) -> tuple[str, dict[str, str], list[str], str]:
    viewer_url, viewer_html = fetch(opener, zoom_url)
    if not isinstance(viewer_html, str):
        raise ValueError("The image viewer did not return HTML")

    fields = dict(HIDDEN_RE.findall(viewer_html))
    fields.setdefault("id", record_id)
    fields.setdefault("aid", aid)
    image_select = IMAGE_SELECT_RE.search(viewer_html)
    options = OPTION_RE.findall(image_select.group(1)) if image_select else []
    recto_verso = [value for value, label in options if label.casefold() in {"recto", "verso"}]
    selected_options = recto_verso or [value for value, _ in options]
    page_names = list(dict.fromkeys(selected_options))
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


def verify_permalink(opener, url: str, aid: str) -> str:
    """Return a usable canonical permalink, refusing the archive's dead-link page."""
    final_url, page = fetch(opener, url)
    if not isinstance(page, str):
        raise ValueError("The permalink did not return an HTML catalogue page")
    final = urlsplit(final_url)
    if final.hostname not in {"www.landesarchiv-bw.de", "landesarchiv-bw.de", "www2.landesarchiv-bw.de"}:
        raise ValueError(f"Permalink redirected outside Landesarchiv Baden-Württemberg: {final_url}")
    if "Zu dieser URL existiert" in page and "keine Ressource" in page:
        raise ValueError(f"Landesarchiv permalink {url} does not exist")
    found = {html.unescape(record_aid).strip() for _, record_aid in ID_RE.findall(page)}
    if aid not in found:
        raise ValueError(f"Landesarchiv page did not confirm archive ID {aid}; refusing to save {url}")
    # Keep the stable public permalink, but only after the archive has confirmed it.
    return f"https://www.landesarchiv-bw.de/plink/?{urlencode({'f': aid})}"


def iso_date(value: str) -> str:
    """Convert common Landesarchiv German date labels to the JSON ISO format."""
    value = value.strip()
    iso_match = re.search(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", value)
    if iso_match:
        return "-".join(iso_match.groups())
    german_day_first = re.search(
        r"(?<!\d)(\d{1,2})\.?\s+([A-Za-zÄÖÜäöüß]+)\.?\s+(\d{4})(?!\d)", value
    )
    if german_day_first:
        day, month, year = german_day_first.groups()
        month_number = MONTHS.get(month.casefold())
        if month_number:
            return f"{year}-{month_number:02d}-{int(day):02d}"
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


def leading_title_date(value: str) -> str | None:
    """Read a full date when the catalogue title begins with one."""
    match = re.match(
        r"^\s*(\d{4}\s+[A-Za-zÄÖÜäöüß]+\.?\s+\d{1,2})(?!\d)", value
    )
    return iso_date(match.group(1)) if match else None


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
                  has_viewer: bool = False, delay: float = 3) -> tuple[Path, bool]:
    from urllib.parse import parse_qs, urlsplit

    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {"www.landesarchiv-bw.de", "landesarchiv-bw.de"}:
        raise ValueError("Expected an https://www.landesarchiv-bw.de/plink/ URL")
    aid = parse_qs(parsed.query).get("f", [""])[0]
    if not aid:
        raise ValueError("The permalink has no f= archive identifier")

    opener = build_opener()
    url = verify_permalink(opener, url, aid)
    images = []
    if catalog_id:
        if not catalog_id.isdigit() or not bestand or not bestand.isdigit():
            raise ValueError("Catalog ID and Bestand must be numeric")
        details_url = "https://www2.landesarchiv-bw.de/ofs21/olf/druckansicht.php?" + urlencode(
            {"id_titlaufn": catalog_id, "bestand": bestand})
    else:
        discovered = discover_viewer(opener, url)
        details_url, viewer_url, fields, page_names, scope_id = discovered
        if page_names:
            images = image_urls(viewer_url, fields, page_names, scope_id)
    details = CatalogDetails()
    details.feed(fetch_page(details_url))
    if catalog_id and has_viewer:
        time.sleep(delay)
        zoom_url = "https://www2.landesarchiv-bw.de/ofs21/bild_zoom/zoom.php?" + urlencode(
            {"bestand": bestand, "id": catalog_id})
        viewer_url, viewer_fields, page_names, scope_id = read_viewer(build_opener(), zoom_url, catalog_id, aid)
        images = image_urls(viewer_url, viewer_fields, page_names, scope_id)
    source = details.fields.get("bestellsignatur")
    date_text = details.fields.get("laufzeit")
    german = details.fields.get("titel")
    if not source or not date_text or not german:
        raise ValueError(f"Could not find citation, date, or title for archive ID {aid}")
    source = " ".join(source.split())
    date = iso_date(date_text)
    if re.fullmatch(r"\d{4}", date):
        date = leading_title_date(german) or date
    siegler = details.fields.get("siegler")
    if siegler:
        german += f"\n\nSiegler: {siegler}"

    generated_entry: dict[str, object] = {"source": source, "url": url, "german": german}
    if images:
        generated_entry["img"] = [{"src": image_url} for image_url in images]

    DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
    from archive_record_storage import save_record
    record = {"date": date, "label": ["to review"], "entries": [generated_entry]}
    return save_record(record, DOCUMENT_DIR)



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Landesarchiv BW permalink")
    parser.add_argument("--catalog-id", help="legacy catalogue record ID")
    parser.add_argument("--bestand", help="legacy catalogue collection ID")
    parser.add_argument("--has-viewer", action="store_true", help="resolve the viewer linked in search results")
    parser.add_argument("--delay", type=float, default=3, help="seconds between catalogue and viewer requests")
    args = parser.parse_args()
    try:
        path, updated = create_record(args.url, args.catalog_id, args.bestand, args.has_viewer, args.delay)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if updated:
        print(f"Only updated existing file: {path.relative_to(REPOSITORY_ROOT)}")
    else:
        print(path.relative_to(REPOSITORY_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
