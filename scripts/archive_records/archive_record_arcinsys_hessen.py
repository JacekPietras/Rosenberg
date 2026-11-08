#!/usr/bin/env python3
"""Create a review document record from an Arcinsys Hessen catalogue URL."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date as calendar_date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, urlopen


USER_AGENT = "Rosenberg research downloader/1.0"
REQUEST_TIMEOUT = 60
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent.parent
DOCUMENT_DIR = REPOSITORY_ROOT / "data" / "documents"
HOSTS = {"arcinsys.hessen.de"}
MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8, "september": 9,
    "oktober": 10, "november": 11, "dezember": 12,
}


class NonDatedCatalogEntry(ValueError):
    """An index entry that cannot be represented as a dated document."""


class Fields(HTMLParser):
    """Collect the label/value rows used on Arcinsys detail pages."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.label_depth = 0
        self.value_depth = 0
        self.current_label: list[str] = []
        self.current_value: list[str] = []
        self.fields: dict[str, list[str]] = {}
        self.in_label = False
        self.in_value = False
        self.in_highlighting_area = False
        self.in_row = False
        self.previous_label = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = set((dict(attrs).get("class") or "").split())
        if tag == "div" and "row" in classes:
            self.in_row = True
            self.current_label, self.current_value = [], []
            self.label_depth = self.value_depth = 0
            self.in_label = self.in_value = False
        elif tag == "span" and "d-none" in classes:
            self.in_label = True
            self.label_depth += 1
        elif tag == "div" and "highlightingArea" in classes:
            self.in_highlighting_area = True
            self.in_value = True
            self.value_depth += 1
        elif self.in_label:
            self.label_depth += 1
        elif self.in_value:
            self.value_depth += 1

    def handle_data(self, data: str) -> None:
        if self.in_label:
            self.current_label.append(data)
        elif self.in_value:
            self.current_value.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self.in_highlighting_area:
            self.in_highlighting_area = False
        if self.in_label:
            self.label_depth -= 1
            if self.label_depth <= 0:
                self.in_label = False
        elif self.in_value:
            self.value_depth -= 1
            if self.value_depth <= 0:
                self.in_value = False
                label = " ".join("".join(self.current_label).split()).rstrip(":")
                value = " ".join("".join(self.current_value).split())
                if label:
                    self.previous_label = label
                elif (self.previous_label.casefold().startswith("enthält")
                      or self.previous_label.casefold().startswith("includes")):
                    label = self.previous_label
                if label and value:
                    self.fields.setdefault(label, []).append(value)
        if tag == "div" and self.in_row:
            self.in_row = False


class Signature(HTMLParser):
    """Read Arcinsys's current heading and paragraph signature layout."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.heading = False
        self.signature_heading = False
        self.paragraph = False
        self.parts: list[str] = []
        self.value = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h2":
            self.heading = True
            self.parts = []
        elif tag == "p" and self.signature_heading:
            self.paragraph = True
            self.parts = []

    def handle_data(self, data: str) -> None:
        if self.heading or self.paragraph:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        text = " ".join("".join(self.parts).split())
        if tag == "h2":
            self.heading = False
            self.signature_heading = text.casefold() == "vollständige signatur"
        elif tag == "p" and self.paragraph:
            self.paragraph = False
            self.signature_heading = False
            if text:
                self.value = text


class Images(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "img":
            src = dict(attrs).get("src")
            if src and "/thumbs/" in src:
                self.urls.append(src)


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        if "html" not in response.headers.get_content_type():
            raise ValueError("The URL did not return an HTML Arcinsys record")
        return response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")


def iso_date(value: str) -> str:
    value = html.unescape(value).strip()
    half_century = re.search(r"\b([12])\s*\.\s*Hälfte\s+(\d{1,2})\s*\.\s*Jh\.?\b", value, re.I)
    if half_century:
        half, century = map(int, half_century.groups())
        start = (century - 1) * 100 + (50 if half == 2 else 0)
        return f"{start}-{start + 50}"
    dotted = re.search(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(\d{4})(?!\d)", value)
    if dotted:
        day, month, year = map(int, dotted.groups())
        try:
            return calendar_date(year, month, day).isoformat()
        except ValueError as exc:
            raise ValueError(f"Invalid day-month-year date in Datierung: {value!r}") from exc
    match = re.search(r"(?<!\d)(\d{4})\s+([A-Za-zÄÖÜäöüß]+)(?:\s+(\d{1,2}))?", value)
    if match:
        year, month, day = match.groups()
        number = MONTHS.get(month.casefold())
        if number:
            result = f"{year}-{number:02d}"
            return result + (f"-{int(day):02d}" if day else "")
    match = re.search(r"(?<!\d)(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?(?!\d)", value)
    if match:
        return "-".join(part for part in match.groups() if part)
    raise ValueError(f"Could not determine the document date from Datierung: {value!r}")


def dated_paths(date: str) -> list[Path]:
    stem = re.sub(r"[^0-9-]+", "_", date)
    pattern = re.compile(rf"{re.escape(stem)}(?:_(\d+))?\.json$")
    return sorted((p for p in DOCUMENT_DIR.glob(f"{stem}*.json") if pattern.fullmatch(p.name)),
                  key=lambda p: (int(pattern.fullmatch(p.name).group(1) or 1), p.name))


def save_record(record: dict[str, object]) -> tuple[Path, bool]:
    from archive_record_storage import save_record as save
    return save(record, DOCUMENT_DIR)


def promote_existing_date(path: Path, date: str) -> Path:
    """Promote a matched year-only record when Arcinsys provides a full date."""
    document = json.loads(path.read_text(encoding="utf-8"))
    old_date = str(document.get("date", ""))
    if (not re.fullmatch(r"\d{4}", old_date)
            or not date.startswith(old_date + "-")
            or not re.fullmatch(rf"{old_date}(?:_\d+)?", path.stem)
            or len(document.get("entries", [])) != 1):
        return path
    target = path.with_name(f"{date}.json")
    if target.exists():
        return path
    document["date"] = date
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.unlink()
    return target


def create_record(url: str) -> tuple[Path, bool]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.path.rstrip("/") != "/arcinsys/showArchivalDescriptionDetails.action":
        raise ValueError("Expected an https://arcinsys.hessen.de/arcinsys/showArchivalDescriptionDetails.action URL")
    if not re.fullmatch(r"\d+", parse_qs(parsed.query).get("archivalDescriptionId", [""])[0]):
        raise ValueError("The URL has no archivalDescriptionId")

    page = fetch(url)
    fields = Fields()
    fields.feed(page)
    signature = Signature()
    signature.feed(page)
    source = signature.value
    date_value = next(iter(fields.fields.get("Datierung", [])), "")
    if not date_value:
        date_value = next(iter(fields.fields.get("Laufzeit", [])), "")
    title = next(iter(fields.fields.get("Titel", [])), "")
    short = next(iter(fields.fields.get("Kurzregest", [])), "")
    full = next(iter(fields.fields.get("(Voll-) Regest", [])), "")
    sealer = next(iter(fields.fields.get("Siegler", [])), "")
    included = [
        value
        for label, values in fields.fields.items()
        if label.casefold().startswith("enthält") or label.casefold().startswith("includes")
        for value in values
    ]
    if not date_value or date_value.strip().casefold() in {"ohne datum", "undatiert", "ohne datierung"}:
        raise NonDatedCatalogEntry("Arcinsys catalog entry has no document date")
    if not source or not date_value:
        raise ValueError("Arcinsys record has no full signature or Datierung")
    german_parts = [part for part in (short, full) if part]
    if not german_parts and title:
        german_parts.append(title)
    if sealer:
        german_parts.append(f"Siegler: {sealer}")
    if included:
        german_parts.append("Enthält: " + "\n".join(included))
    german = "\n\n".join(german_parts)
    images = Images()
    images.feed(page)
    entry: dict[str, object] = {"source": source, "url": url}
    if german:
        entry["german"] = german
    image_list = list(dict.fromkeys(
        urljoin(url, image).replace("/thumbs/", "/") for image in images.urls
    ))
    if image_list:
        entry["img"] = [{"src": image} for image in image_list]
    date = iso_date(date_value)
    record = {"date": date, "label": ["to review"], "entries": [entry]}
    DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
    path, updated = save_record(record)
    if updated:
        path = promote_existing_date(path, date)
    return path, updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Arcinsys Hessen archival description URL")
    args = parser.parse_args()
    try:
        path, updated = create_record(args.url)
    except NonDatedCatalogEntry as exc:
        print(f"Skipping non-document catalog entry: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Only updated existing file: {path.relative_to(REPOSITORY_ROOT)}" if updated else path.relative_to(REPOSITORY_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
