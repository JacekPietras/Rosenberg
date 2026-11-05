#!/usr/bin/env python3
"""Create a review document record from an Archive NRW catalogue URL."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
from xml.etree import ElementTree


USER_AGENT = "Rosenberg research downloader/1.0"
REQUEST_TIMEOUT = 60
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DOCUMENT_DIR = REPOSITORY_ROOT / "data" / "documents"
HOSTS = {"www.archive.nrw.de", "archive.nrw.de"}
OPENER = build_opener(HTTPCookieProcessor(CookieJar()))
ANUBIS_CHALLENGE_RE = re.compile(
    r'<script id="anubis_challenge" type="application/json">(.*?)</script>', re.S
)
ANUBIS_PASS_PATH = "/.within.website/x/cmd/anubis/api/pass-challenge"


class TextOnly(HTMLParser):
    """Extract readable text from short HTML catalog descriptions."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "p", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li"}:
            self.parts.append("\n")


def request(url: str) -> tuple[str, bytes]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,application/xml,text/html,*/*"})
    try:
        with OPENER.open(req, timeout=REQUEST_TIMEOUT) as response:
            return response.geturl(), response.read()
    except HTTPError as exc:
        if exc.code != 403:
            raise
        return exc.geturl(), exc.read()


def solve_anubis(page: bytes, page_url: str) -> str | None:
    match = ANUBIS_CHALLENGE_RE.search(page.decode("utf-8", "replace"))
    if not match:
        return None
    challenge = json.loads(match.group(1))
    rules = challenge["rules"]
    if rules.get("algorithm") not in {"fast", "slow", "preact"}:
        raise ValueError(f"Unsupported Archive NRW bot challenge: {rules.get('algorithm')!r}")
    prefix = "0" * int(rules["difficulty"])
    seed = challenge["challenge"]["randomData"].encode()
    started = time.monotonic()
    nonce = 0
    while True:
        digest = hashlib.sha256(seed + str(nonce).encode()).hexdigest()
        if digest.startswith(prefix):
            break
        nonce += 1
    elapsed = max(int((time.monotonic() - started) * 1000), 1)
    parts = urlsplit(page_url)
    query = urlencode({
        "id": challenge["challenge"]["id"], "response": digest, "nonce": nonce,
        "redir": page_url, "elapsedTime": elapsed,
    })
    return f"{parts.scheme}://{parts.netloc}{ANUBIS_PASS_PATH}?{query}"


def fetch(url: str) -> tuple[str, bytes]:
    final_url, body = request(url)
    for _ in range(2):
        pass_url = solve_anubis(body, final_url)
        if pass_url is None:
            return final_url, body
        final_url, body = request(pass_url)
    if solve_anubis(body, final_url):
        raise ValueError("Could not pass Archive NRW bot protection")
    return final_url, body


def normalize_date(raw: str) -> str:
    """Keep the catalog's year precision while removing EAD uncertainty brackets."""
    value = raw.strip().strip("[]() ")
    years = re.findall(r"(?<!\d)(\d{4})(?!\d)", value)
    if not years:
        raise ValueError(f"Could not determine a document date from unitDate: {raw!r}")
    years = list(dict.fromkeys(years))
    return years[0] if len(years) == 1 else f"{years[0]}-{years[-1]}"


def description_text(value: object) -> str:
    if isinstance(value, list):
        value = "\n".join(str(part) for part in value if part)
    if not isinstance(value, str) or not value.strip():
        return ""
    parser = TextOnly()
    parser.feed(value.replace("<@nxt@ />", "\n"))
    text = "".join(parser.parts)
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())


def image_urls(mets_url: str) -> list[str]:
    _, body = fetch(mets_url)
    root = ElementTree.fromstring(body)
    ns = {"mets": "http://www.loc.gov/METS/", "xlink": "http://www.w3.org/1999/xlink"}
    images: list[str] = []
    for location in root.findall(".//mets:fileGrp[@USE='DEFAULT']/mets:file/mets:FLocat", ns):
        source = location.get(f"{{{ns['xlink']}}}href")
        if source and source.lower().endswith((".jp2", ".jpg", ".jpeg", ".png")):
            images.append(source.rstrip("/") + "/full/max/0/default.jpg")
    return list(dict.fromkeys(images))


def dated_paths(date: str) -> list[Path]:
    stem = re.sub(r"[^0-9-]+", "_", date)
    pattern = re.compile(rf"{re.escape(stem)}(?:_(\d+))?\.json$")
    return sorted((p for p in DOCUMENT_DIR.glob(f"{stem}*.json") if pattern.fullmatch(p.name)),
                  key=lambda p: (int(pattern.fullmatch(p.name).group(1) or 1), p.name))


def save_record(record: dict[str, object]) -> tuple[Path, bool]:
    from downloader_storage import save_record as save
    return save(record, DOCUMENT_DIR)


def create_record(url: str) -> tuple[Path, bool]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.path.rstrip("/") != "/archivsuche":
        raise ValueError("Expected an https://www.archive.nrw.de/archivsuche record URL")
    node_id = parse_qs(parsed.query).get("link", [""])[0]
    if not re.fullmatch(r"VERZEICHNUNGSEINHEIT-Vz_[0-9a-f-]+", node_id, re.I):
        raise ValueError("The URL must identify a VERZEICHNUNGSEINHEIT record")
    api_url = "https://www.archive.nrw.de/sufservice/api/listContextByNodeId?" + urlencode({"nodeId": node_id})
    _, body = fetch(api_url)
    try:
        selected = json.loads(body)["selectedNode"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("Archive NRW did not return a selected catalog record") from exc
    if selected.get("type", {}).get("value") != "VERZEICHNUNGSEINHEIT":
        raise ValueError("The Archive NRW link did not resolve to a record unit")

    date = normalize_date(str(selected.get("unitDate") or ""))
    signature = str(selected.get("signatur") or "").strip()
    fonds = str(selected.get("bestaendeId") or selected.get("bestandSignature") or "").strip()
    archive = str(selected.get("corpName") or "Landesarchiv NRW").strip()
    division = archive.replace("Landesarchiv NRW ", "")
    source_parts = [division]
    if fonds:
        source_parts.append(fonds)
    if signature:
        source_parts.append(f"Nr. {signature}")
    source = ", ".join(source_parts)

    abstract_parts = [str(selected.get("title") or "").strip()]
    abstract = description_text(selected.get("abstrakt"))
    if abstract:
        abstract_parts.append(abstract)
    note = description_text(selected.get("note"))
    if note:
        abstract_parts.append(note)
    physical = description_text(selected.get("physicalDescriptionContent"))
    if physical:
        abstract_parts.append(physical)
    german = "\n\n".join(part for part in abstract_parts if part)
    entry: dict[str, object] = {"source": source, "url": url, "german": german}
    mets_links = selected.get("daogrpDaolocHrefs") or []
    images: list[str] = []
    for viewer in mets_links:
        match = re.search(r"[?&]tx_dlf\[id\]=([^&]+)", str(viewer))
        if match:
            from urllib.parse import unquote
            mets_url = unquote(match.group(1))
            try:
                images.extend(image_urls(mets_url))
            except (HTTPError, URLError, ElementTree.ParseError, ValueError):
                continue
    if images:
        entry["img"] = [{"src": image} for image in dict.fromkeys(images)]
    return save_record({"date": date, "label": ["to review"], "entries": [entry]})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Archive NRW record URL")
    args = parser.parse_args()
    try:
        path, updated = create_record(args.url)
    except (OSError, ValueError, HTTPError, URLError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Only updated existing file: {path.relative_to(REPOSITORY_ROOT)}" if updated else path.relative_to(REPOSITORY_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
