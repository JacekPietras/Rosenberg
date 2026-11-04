#!/usr/bin/env python3
"""Create a review document record from an Arcinsys Hessen catalogue URL."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, urlopen


USER_AGENT = "Rosenberg research downloader/1.0"
REQUEST_TIMEOUT = 60
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DOCUMENT_DIR = REPOSITORY_ROOT / "data" / "documents"
HOSTS = {"arcinsys.hessen.de"}
MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8, "september": 9,
    "oktober": 10, "november": 11, "dezember": 12,
}


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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = set((dict(attrs).get("class") or "").split())
        if tag == "div" and "row" in classes:
            self.current_label, self.current_value = [], []
            self.label_depth = self.value_depth = 0
            self.in_label = self.in_value = False
        elif tag == "span" and "d-none" in classes:
            self.in_label = True
            self.label_depth += 1
        elif tag == "div" and "highlightingArea" in classes:
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
                if label and value:
                    self.fields.setdefault(label, []).append(value)


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


def as_list(value: object) -> list:
    return value if isinstance(value, list) else [value] if value else []


def matching_texts(entry: dict) -> set[str]:
    return {" ".join(value.split()) for key in ("german", "latin", "summary")
            if isinstance((value := entry.get(key)), str) and value.strip()}


def save_record(record: dict[str, object], skip_existing: bool = False) -> tuple[Path, bool]:
    date = str(record["date"])
    paths = dated_paths(date)
    incoming = record["entries"][0]
    # First find an existing citation on this date, even when it is in an array.
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        for entry in document.get("entries", []):
            if isinstance(entry, dict) and incoming.get("source") in as_list(entry.get("source")):
                if skip_existing:
                    return path, True
                # Preserve any other citations and links on a previously merged entry.
                for key, value in incoming.items():
                    if key not in ("source", "url"):
                        entry[key] = value
                labels = as_list(document.get("label"))
                if "to review" not in labels:
                    labels.append("to review")
                document["label"] = labels
                path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                return path, True
    # Exact content can identify the same document even if date precision differs.
    texts = matching_texts(incoming)
    if texts:
        for path in sorted(DOCUMENT_DIR.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            for entry in document.get("entries", []):
                if not isinstance(entry, dict) or not texts.intersection(matching_texts(entry)):
                    continue
                for key in ("source", "url"):
                    old = as_list(entry.get(key))
                    for value in as_list(incoming.get(key)):
                        if value not in old:
                            old.append(value)
                    if old:
                        entry[key] = old[0] if len(old) == 1 else old
                path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                return path, True
    stem = re.sub(r"[^0-9-]+", "_", date)
    suffixes = [int(m.group(1)) for p in paths if (m := re.fullmatch(rf"{re.escape(stem)}_(\d+)\.json", p.name))]
    path = DOCUMENT_DIR / (f"{stem}_{max(suffixes, default=1) + 1}.json" if paths else f"{stem}.json")
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, False


def create_record(url: str, skip_existing: bool = False) -> tuple[Path, bool]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.path.rstrip("/") != "/arcinsys/showArchivalDescriptionDetails.action":
        raise ValueError("Expected an https://arcinsys.hessen.de/arcinsys/showArchivalDescriptionDetails.action URL")
    if not re.fullmatch(r"\d+", parse_qs(parsed.query).get("archivalDescriptionId", [""])[0]):
        raise ValueError("The URL has no archivalDescriptionId")

    page = fetch(url)
    fields = Fields()
    fields.feed(page)
    signature = re.search(r"<h2>\s*Vollständige Signatur\s*</h2>\s*<p>(.*?)</p>", page, re.S | re.I)
    source = " ".join(html.unescape(re.sub(r"<[^>]+>", "", signature.group(1))).split()) if signature else ""
    date_value = next(iter(fields.fields.get("Datierung", [])), "")
    short = next(iter(fields.fields.get("Kurzregest", [])), "")
    full = next(iter(fields.fields.get("(Voll-) Regest", [])), "")
    sealer = next(iter(fields.fields.get("Siegler", [])), "")
    if not source or not date_value:
        raise ValueError("Arcinsys record has no full signature or Datierung")
    german_parts = [part for part in (short, full) if part]
    if sealer:
        german_parts.append(f"Siegler: {sealer}")
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
    record = {"date": iso_date(date_value), "label": ["to review"], "entries": [entry]}
    DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
    return save_record(record, skip_existing=skip_existing)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Arcinsys Hessen archival description URL")
    parser.add_argument("--skip-existing", action="store_true", help="leave existing entries with the same source unchanged")
    args = parser.parse_args()
    try:
        path, updated = create_record(args.url, skip_existing=args.skip_existing)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if updated and args.skip_existing:
        print(f"Existing or merged file: {path.relative_to(REPOSITORY_ROOT)}")
        return 0
    print(f"Only updated existing file: {path.relative_to(REPOSITORY_ROOT)}" if updated else path.relative_to(REPOSITORY_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
