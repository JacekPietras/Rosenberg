#!/usr/bin/env python3
"""Create a review document record from a Regesta Imperii record URL."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
from xml.etree import ElementTree


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from archive_anubis import ANUBIS_CHALLENGE_RE, solve_anubis


USER_AGENT = "Rosenberg research downloader/1.0"
REQUEST_TIMEOUT = 60
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent.parent
DOCUMENT_DIR = REPOSITORY_ROOT / "data" / "documents"
HOSTS = {"www.regesta-imperii.de", "regesta-imperii.de"}
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
MONTH_PREFIXES = ["jan", "feb", "mär", "apr", "mai", "jun", "jul", "aug", "sep", "okt", "nov", "dez"]
MONTH_ALIASES = {"jän": 1, "mar": 3, "mrz": 3}
GERMAN_DATE_RE = re.compile(r"(\d{4})(?:\s+([A-Za-zäÄ]{3,9})\.?(?:\s+(\d{1,2})\b)?)?")
CEI_LINK_RE = re.compile(r"(?:https?://[^\"'\s<>]+)?/cei/[\w.-]+/sources/[\w.-]+", re.I)


class Links(HTMLParser):
    """Find links from human-readable record pages to CEI resources."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        href = dict(attrs).get("href")
        if href:
            self.hrefs.append(href)


OPENER = build_opener(HTTPCookieProcessor(CookieJar()))


def request_url(url: str) -> tuple[str, bytes]:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/xml,text/xml,text/html,*/*"},
    )
    try:
        with OPENER.open(request, timeout=REQUEST_TIMEOUT) as response:
            return response.geturl(), response.read()
    except HTTPError as exc:
        if exc.code != 403:
            raise
        return exc.geturl(), exc.read()


def fetch(url: str) -> tuple[str, bytes]:
    final_url, body = request_url(url)
    for _ in range(2):
        pass_url = solve_anubis(body, final_url)
        if pass_url is None:
            return final_url, body
        final_url, body = request_url(pass_url)
    if solve_anubis(body, final_url) is not None:
        raise ValueError("Could not pass the Regesta Imperii bot protection")
    return final_url, body


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def node_text(node: ElementTree.Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def find_text(root: ElementTree.Element, name: str, under: str | None = None) -> str:
    candidates = list(root.iter())
    if under:
        parents = [node for node in candidates if local_name(node.tag) == under.casefold()]
        candidates = [child for parent in parents for child in parent.iter()]
    for node in candidates:
        if local_name(node.tag) == name.casefold():
            text = node_text(node)
            if text:
                return text
    return ""


def first_element(root: ElementTree.Element, name: str) -> ElementTree.Element | None:
    return next((node for node in root.iter() if local_name(node.tag) == name.casefold()), None)


def parse_date(root: ElementTree.Element) -> str:
    for node in root.iter():
        if local_name(node.tag) != "daterange":
            continue
        start = node.get("from") or node.get("notBefore") or node.get("when")
        end = node.get("to") or node.get("notAfter") or start
        if start:
            start = normalize_date(start)
            end = normalize_date(end) if end else start
            return start if start == end else f"{start}/{end}"
    for name in ("date", "issuedate"):
        value = find_text(root, name)
        if value:
            match = re.search(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", value)
            if match:
                return normalize_date(match.group(0))
    raise ValueError("The Regesta Imperii record has no machine-readable date")


def normalize_date(value: str) -> str:
    match = re.fullmatch(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", value.strip())
    if not match:
        raise ValueError(f"Unsupported CEI date precision: {value!r}")
    year, month, day = match.groups()
    if month in {None, "00"}:
        return year
    if day in {None, "00"}:
        return f"{year}-{month}"
    return f"{year}-{month}-{day}"


def source_images(root: ElementTree.Element, base_url: str) -> list[str]:
    images: list[str] = []
    for node in root.iter():
        if local_name(node.tag) != "graphic":
            continue
        for key, value in node.attrib.items():
            if local_name(key) not in {"url", "href", "target", "src"} or not value.strip():
                continue
            image_url = urljoin(base_url, value.strip())
            images.append(image_url)
            break
    return list(dict.fromkeys(images))


def parse_cei(xml_bytes: bytes, page_url: str, entered_url: str) -> dict[str, object]:
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise ValueError("The Regesta Imperii CEI resource is not valid XML") from exc

    citation = find_text(root, "idno", under="head")
    if not citation:
        citation = find_text(root, "idno", under="bibl")
    abstract_node = first_element(root, "abstract")
    abstract = "\n\n".join(
        " ".join("".join(paragraph.itertext()).split())
        for paragraph in abstract_node.iter()
        if local_name(paragraph.tag) in {"p", "ab"} and node_text(paragraph)
    ) if abstract_node is not None else ""
    if not abstract and abstract_node is not None:
        abstract = node_text(abstract_node)
    if not citation or not abstract:
        raise ValueError("The CEI record has no citation or German abstract")

    urls = list(dict.fromkeys([entered_url, page_url]))
    images = source_images(root, page_url)
    entry: dict[str, object] = {
        "source": citation,
        "url": urls[0] if len(urls) == 1 else urls,
        "german": abstract,
    }
    if images:
        entry["img"] = [{"src": image_url} for image_url in images]
    place = find_text(root, "placename", under="issueplace")
    record: dict[str, object] = {"date": parse_date(root), "label": ["to review"], "entries": [entry]}
    if place:
        record["place"] = place
    return record


def strip_tags(fragment: str) -> str:
    fragment = re.sub(r"</?(?:p|br|div|li)\b[^>]*>", " ", fragment)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def month_number(name: str) -> int | None:
    prefix = name.casefold()[:3]
    if prefix in MONTH_ALIASES:
        return MONTH_ALIASES[prefix]
    return MONTH_PREFIXES.index(prefix) + 1 if prefix in MONTH_PREFIXES else None


def parse_german_date(text: str) -> str:
    dates = []
    for year, month, day in GERMAN_DATE_RE.findall(text.replace("[", "").replace("]", "")):
        value = year
        number = month_number(month) if month else None
        if number:
            value += f"-{number:02d}"
            if day:
                value += f"-{int(day):02d}"
        dates.append(value)
    if not dates:
        raise ValueError(f"No date found in Regesta Imperii page heading: {text!r}")
    start, end = min(dates), max(dates)
    return start if start == end else f"{start}/{end}"


def parse_html(page: bytes, entered_url: str) -> dict[str, object]:
    text = page.decode("utf-8", "replace")
    head = re.search(r'<div id="head">(.*?)<p class="actionlinks">', text, re.S)
    summary = re.search(r'<div id="summary">(.*?)</div>', text, re.S)
    if not head or not summary:
        raise ValueError("The Regesta Imperii page is not a single record page")
    citation_node = re.search(r'<p class="departement">\s*<strong>(.*?)</strong>', head.group(1), re.S)
    citation = strip_tags(citation_node.group(1)).split(" - ", 1)[-1] if citation_node else ""
    heading = re.search(r"<h3>(.*?)</h3>", head.group(1), re.S)
    paragraphs = [strip_tags(p) for p in re.findall(r"<p>(.*?)</p>", summary.group(1), re.S)]
    abstract = "\n\n".join(p for p in paragraphs if p)
    if not citation or not abstract or not heading:
        raise ValueError("The Regesta Imperii page has no citation, date or abstract")
    heading_text = strip_tags(heading.group(1))
    parts = urlsplit(entered_url)
    url = urlunsplit(parts._replace(query="", fragment="")) if "/regesten/" in parts.path else entered_url
    record: dict[str, object] = {
        "date": parse_german_date(heading_text),
        "label": ["to review"],
        "entries": [{"source": citation, "url": url, "german": abstract}],
    }
    place = heading_text.split(",", 1)[1].strip() if "," in heading_text else ""
    if not place and (summary_place := re.match(r"\(([^)]+)\)", abstract)):
        place = summary_place.group(1)
    if place:
        record["place"] = place
    return record


def canonical_url(url: str) -> str:
    match = UUID_RE.search(urlsplit(url).path)
    if not match:
        raise ValueError("No record id found in the Regesta Imperii URL")
    return f"https://www.regesta-imperii.de/id/{match.group(0).lower()}"


def resolve_cei(url: str) -> tuple[str, bytes]:
    page_url, page = fetch(url)
    content_start = page.lstrip()[:100].lower()
    if content_start.startswith(b"<?xml") or content_start.startswith(b"<cei"):
        return page_url, page

    text = page.decode("utf-8", "replace")
    candidates = list(dict.fromkeys(CEI_LINK_RE.findall(text)))
    link_parser = Links()
    link_parser.feed(text)
    candidates.extend(
        urljoin(page_url, href)
        for href in link_parser.hrefs
        if re.search(r"/cei/[\w.-]+/sources/[\w.-]+", href, re.I)
    )
    for candidate in dict.fromkeys(candidates):
        candidate_url = urljoin(page_url, candidate)
        try:
            return fetch(candidate_url)
        except (HTTPError, URLError):
            continue
    raise ValueError("The Regesta Imperii page did not expose an accessible CEI XML record")


def dated_document_paths(date: str) -> list[Path]:
    stem = re.sub(r"[^0-9-]+", "_", date)
    pattern = re.compile(rf"{re.escape(stem)}(?:_(\d+))?\.json$")
    paths = [path for path in DOCUMENT_DIR.glob(f"{stem}*.json") if pattern.fullmatch(path.name)]
    return sorted(paths, key=lambda path: (int(pattern.fullmatch(path.name).group(1) or 1), path.name))


def next_output_path(date: str, paths: list[Path]) -> Path:
    stem = re.sub(r"[^0-9-]+", "_", date)
    if not paths:
        return DOCUMENT_DIR / f"{stem}.json"
    suffixes = [int(match.group(1)) for path in paths if (match := re.fullmatch(rf"{re.escape(stem)}_(\d+)\.json", path.name))]
    return DOCUMENT_DIR / f"{stem}_{max(suffixes, default=1) + 1}.json"


def update_existing(path: Path, incoming: dict[str, object]) -> bool:
    document = json.loads(path.read_text(encoding="utf-8"))
    new_entry = incoming["entries"][0]
    for entry in document.get("entries", []):
        if not isinstance(entry, dict) or entry.get("source") != new_entry.get("source"):
            continue
        old_urls = entry.get("url", [])
        urls = [old_urls] if isinstance(old_urls, str) else list(old_urls)
        new_urls = new_entry["url"] if isinstance(new_entry["url"], list) else [new_entry["url"]]
        merged = list(dict.fromkeys(urls + new_urls))
        entry.update(new_entry)
        entry["url"] = merged[0] if len(merged) == 1 else merged
        labels = document.get("label", [])
        labels = [labels] if isinstance(labels, str) else list(labels)
        if "to review" not in labels:
            labels.append("to review")
        document["label"] = labels
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True
    return False


def create_record(url: str) -> tuple[Path, bool]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS:
        raise ValueError("Expected an https://www.regesta-imperii.de/ record URL")
    if not any(path in parsed.path for path in ("/regesten/", "/cei/", "/id/")):
        raise ValueError("Unsupported Regesta Imperii URL path")

    try:
        cei_url, cei_xml = resolve_cei(url)
        record = parse_cei(cei_xml, cei_url, url)
    except (HTTPError, ValueError):
        _, page = fetch(canonical_url(url))
        record = parse_html(page, url)
    from archive_record_storage import save_record
    return save_record(record, DOCUMENT_DIR)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Regesta Imperii record URL")
    args = parser.parse_args()
    try:
        path, updated = create_record(args.url)
    except (OSError, ValueError, HTTPError, URLError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if updated:
        print(f"Only updated existing file: {path.relative_to(REPOSITORY_ROOT)}")
    else:
        print(path.relative_to(REPOSITORY_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
