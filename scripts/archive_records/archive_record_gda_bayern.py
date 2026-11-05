#!/usr/bin/env python3
"""Create a review document record from a GDA Bayern archive URL."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree


USER_AGENT = "Rosenberg research downloader/1.0"
REQUEST_TIMEOUT = 60
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent.parent
DOCUMENT_DIR = REPOSITORY_ROOT / "data" / "documents"
GDA_HOSTS = {"www.gda.bayern.de", "gda.bayern.de"}


class RecordFields(HTMLParser):
    """Collect labeled catalog fields from the GDA record table."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fields: dict[str, list[str]] = {}
        self.current_label: str | None = None
        self.current_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "td":
            self.current_label = dict(attrs).get("data-label")
            if self.current_label:
                self.fields.setdefault(self.current_label.rstrip(":"), [])
                self.current_parts = []

    def handle_data(self, data: str) -> None:
        if self.current_label:
            self.current_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td":
            if self.current_label:
                self.fields[self.current_label.rstrip(":")].append(''.join(self.current_parts))
            self.current_label = None


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        if "html" not in response.headers.get_content_type():
            raise ValueError("The URL did not return an HTML archive record")
        return response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")


def image_urls(page: str, record_url: str) -> list[str]:
    """Read the record's METS file list and return its IIIF image URLs."""
    mets_ids = list(dict.fromkeys(re.findall(r"/gvl/mets/([0-9a-f]{8}-[0-9a-f-]{27})", page, re.I)))
    urls: list[str] = []
    for mets_id in mets_ids:
        mets_url = urljoin(record_url, f"/gvl/mets/{mets_id}")
        request = Request(mets_url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            root = ElementTree.fromstring(response.read())
        ns = {"mets": "http://www.loc.gov/METS/", "xlink": "http://www.w3.org/1999/xlink"}
        for location in root.findall(".//mets:fileGrp/mets:file/mets:FLocat", ns):
            href = location.get(f"{{{ns['xlink']}}}href")
            if href and "/digitalisat/iiif/" in href:
                urls.append(href.rstrip("/") + "/full/max/0/default.jpg")
    return list(dict.fromkeys(urls))


def field_values(parser: RecordFields, label: str) -> list[str]:
    return ["".join(parts).strip() for parts in parser.fields.get(label, []) if "".join(parts).strip()]


def strip_rtf(value: str) -> str:
    """Convert the basic RTF used by the catalog's Betreff field to plain text."""
    value = re.sub(r"\{\\fonttbl.*?\}\s*", "", value, flags=re.S)
    value = re.sub(r"\{\\rtf1.*?\\pard", "", value, count=1, flags=re.S)
    value = re.sub(r"\\'[0-9a-fA-F]{2}", lambda m: bytes([int(m.group(0)[2:], 16)]).decode("cp1252"), value)
    value = re.sub(r"\\(?:par|line)\b ?", "\n", value)
    value = re.sub(r"\\u(-?\d+)\??", lambda m: chr(int(m.group(1)) % 65536), value)
    value = re.sub(r"\\'[0-9a-fA-F]{2}", "", value)
    value = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", value)
    value = re.sub(r"\\[^a-zA-Z]", "", value)
    value = value.replace("{", "").replace("}", "")
    return "\n".join(line.strip() for line in value.splitlines() if line.strip())


def iso_date(laufzeit: str) -> str:
    """Convert the catalog's common German date forms to ISO precision."""
    value = laufzeit.strip()
    months = 'Januar Februar März April Mai Juni Juli August September Oktober November Dezember'.split()
    for month, name in enumerate(months, 1):
        value = re.sub(rf'\b(\d{{4}})\s+{name}\s+(\d{{1,2}})\b',
                       lambda m: f'{m[2]}.{month}.{m[1]}', value, flags=re.I)
    dates = re.findall(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(\d{4})(?!\d)", value)
    if len(dates) == 1:
        day, month, year = dates[0]
        return f"{year}-{int(month):02d}-{int(day):02d}"
    if len(dates) == 2:
        return f"{iso_date('.'.join(dates[0]))}/{iso_date('.'.join(dates[1]))}"
    years = re.findall(r"(?<!\d)(\d{4})(?!\d)", value)
    if len(years) == 1:
        return years[0]
    if len(years) == 2:
        return f"{years[0]}-{years[1]}"
    raise ValueError(f"Could not determine the document date from Laufzeit: {laufzeit!r}")


def dated_document_paths(date: str) -> list[Path]:
    stem = re.sub(r"[^0-9-]+", "_", date)
    pattern = re.compile(rf"{re.escape(stem)}(?:_(\d+))?\.json$")
    paths = [path for path in DOCUMENT_DIR.glob(f"{stem}*.json") if pattern.fullmatch(path.name)]
    return sorted(
        paths,
        key=lambda path: (int(pattern.fullmatch(path.name).group(1) or 1), path.name),
    )


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


def create_record(url: str) -> tuple[Path, bool]:
    from urllib.parse import urlsplit

    parsed_url = urlsplit(url)
    if parsed_url.scheme != "https" or parsed_url.hostname not in GDA_HOSTS or not parsed_url.path.startswith("/gvl/"):
        raise ValueError("Expected an https://www.gda.bayern.de/gvl/ archive record URL")

    page = fetch(url)
    parser = RecordFields()
    parser.feed(page)
    laufzeit = field_values(parser, "Laufzeit")
    citations = field_values(parser, "Bestellsignatur")
    subjects = field_values(parser, "Betreff")
    if not laufzeit:
        raise ValueError("The GDA page has no Laufzeit field")
    if not citations:
        raise ValueError("The GDA page has no Bestellsignatur field")

    german = strip_rtf(subjects[0]) if subjects else ""
    date = iso_date(laufzeit[0])
    generated_entry: dict[str, object] = {"source": citations[0], "url": url}
    if german:
        generated_entry["german"] = german
    images = image_urls(page, url)
    if images:
        generated_entry["img"] = [{"src": image_url} for image_url in images]

    from archive_record_storage import save_record
    record = {"date": date, "label": ["to review"], "entries": [generated_entry]}
    return save_record(record, DOCUMENT_DIR)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="GDA Bayern archive record URL")
    args = parser.parse_args()
    try:
        path, updated = create_record(args.url)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if updated:
        print(f"Only updated existing file: {path.relative_to(REPOSITORY_ROOT)}")
    else:
        print(path.relative_to(REPOSITORY_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
