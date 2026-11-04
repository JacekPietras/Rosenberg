#!/usr/bin/env python3
"""Route a Monasterium charter to the downloader for its archival repository."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, build_opener
from xml.etree import ElementTree

from downloader_landesarchiv import create_record as create_landesarchiv_record
from downloader_gda_bayern import create_record as create_gda_record


USER_AGENT = "Rosenberg research downloader/1.0"
REQUEST_TIMEOUT = 60
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
HOSTS = {"www.monasterium.net", "monasterium.net"}
GDA_RECORDS = {
    ("DE-StAAm", "EnsdorfOSB", "135"):
        "https://www.gda.bayern.de/gvl/archive.xhtml?id=Vz++++++3FB2B7FD-5E3D-45EC-935C-576C03BEBA06",
}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def archival_permalink(root: ElementTree.Element) -> str:
    for node in root.iter():
        if local_name(node.tag) == "archidentifier":
            for ref in node.iter():
                if local_name(ref.tag) == "ref" and ref.get("target"):
                    target = urlsplit(ref.get("target", "").strip())
                    if target.hostname not in {"www.landesarchiv-bw.de", "landesarchiv-bw.de"}:
                        raise ValueError("The Monasterium archival reference is not a Landesarchiv BW permalink")
                    return urlunsplit(target._replace(scheme="https"))
    raise ValueError("The Monasterium CEI record has no archival permalink")


def node_text(node: ElementTree.Element | None) -> str:
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def first_node(root: ElementTree.Element, name: str) -> ElementTree.Element | None:
    return next((node for node in root.iter() if local_name(node.tag) == name.casefold()), None)


def create_monasterium_record(root: ElementTree.Element, url: str) -> tuple[Path, bool]:
    date_node = first_node(root, "date")
    date_value = date_node.get("value", "") if date_node is not None else ""
    date_match = re.fullmatch(r"(\d{4})(\d{2})?(\d{2})?", date_value)
    if not date_match:
        raise ValueError(f"Unsupported Monasterium date value: {date_value!r}")
    year, month, day = date_match.groups()
    date = year
    if month and month != "00":
        date += f"-{month}"
        if day and day != "00":
            date += f"-{day}"

    abstract = node_text(first_node(root, "abstract"))
    identifier = first_node(root, "archidentifier")
    citation = node_text(identifier)
    idno = first_node(root, "idno")
    if idno is not None and node_text(idno):
        citation = f"{citation}, {node_text(idno)}" if citation else node_text(idno)
    if not abstract or not citation:
        raise ValueError("The Monasterium record has no abstract or archival citation")

    german = abstract
    seal = first_node(root, "sigillant")
    if seal is not None and node_text(seal):
        german += f"\n\nSiegler: {node_text(seal)}"
    entry: dict[str, object] = {"source": citation, "url": url, "german": german}
    graphics = [node.get("url", "").strip() for node in root.iter()
                if local_name(node.tag) == "graphic" and node.get("url", "").strip()]
    if graphics:
        entry["img"] = [{"src": image} for image in dict.fromkeys(graphics)]
    record = {"date": date, "label": ["to review"], "entries": [entry]}

    document_dir = REPOSITORY_ROOT / "data" / "documents"
    document_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^0-9-]+", "_", date)
    pattern = re.compile(rf"{re.escape(stem)}(?:_(\d+))?\.json$")
    paths = sorted((p for p in document_dir.glob(f"{stem}*.json") if pattern.fullmatch(p.name)),
                   key=lambda p: (int(pattern.fullmatch(p.name).group(1) or 1), p.name))
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        for old_entry in document.get("entries", []):
            if isinstance(old_entry, dict) and old_entry.get("source") == citation:
                old_entry.update(entry)
                labels = document.get("label", [])
                labels = [labels] if isinstance(labels, str) else list(labels)
                if "to review" not in labels:
                    labels.append("to review")
                document["label"] = labels
                path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                return path, True
    suffixes = [int(m.group(1)) for p in paths if (m := re.fullmatch(rf"{re.escape(stem)}_(\d+)\.json", p.name))]
    output = document_dir / (f"{stem}_{max(suffixes, default=1) + 1}.json" if paths else f"{stem}.json")
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output, False


def monasterium_metadata_url(parsed) -> str:
    match = re.fullmatch(r"/mom/([^/]+)/([^/]+)/([^/]+)/charter/?", parsed.path)
    if not match:
        raise ValueError("Expected a Monasterium charter page URL")
    archive, fonds, charter_id = match.groups()
    return (
        "https://www.monasterium.net/mom/atom/GET/metadata.charter.public/"
        f"{archive}/{fonds}/{charter_id}.cei.xml"
    )


def fetch_cei(url: str) -> bytes:
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/xml,text/xml,*/*",
        "Referer": "https://www.monasterium.net/",
    })
    with build_opener().open(request, timeout=REQUEST_TIMEOUT) as response:
        payload = response.read()
    # Monasterium can append Cloudflare scripts and an incomplete HTML wrapper
    # inside its CEI response. Remove those additions and repair the open body.
    payload = re.sub(rb"<script(?:\s[^>]*)?>.*?</script>\s*</body>", b"", payload, flags=re.S)
    payload = re.sub(rb"<back\b.*?</back>", b"", payload, flags=re.S)
    payload = re.sub(rb"</chDesc>\s*</text>", b"</chDesc></body></text>", payload)
    end = payload.find(b"</atom:entry>")
    return payload[:end + len(b"</atom:entry>")] if end >= 0 else payload


def add_monasterium_url(path: Path, monasterium_url: str, archive_url: str) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    for entry in document.get("entries", []):
        if not isinstance(entry, dict):
            continue
        old_urls = entry.get("url", [])
        old_urls = [old_urls] if isinstance(old_urls, str) else list(old_urls)
        if archive_url not in old_urls:
            continue
        entry["url"] = list(dict.fromkeys([monasterium_url, archive_url, *old_urls]))
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    raise ValueError(f"The Landesarchiv downloader did not save an entry for {archive_url}")


def create_record(url: str) -> tuple[Path, bool]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS:
        raise ValueError("Expected an https://www.monasterium.net/mom/.../charter URL")
    metadata_url = monasterium_metadata_url(parsed)
    match = re.fullmatch(r"/mom/([^/]+)/([^/]+)/([^/]+)/charter/?", parsed.path)
    assert match is not None
    gda_url = GDA_RECORDS.get(match.groups())
    if gda_url:
        path, updated = create_gda_record(gda_url)
        add_monasterium_url(path, url, gda_url)
        return path, updated
    try:
        root = ElementTree.fromstring(fetch_cei(metadata_url))
    except ElementTree.ParseError as exc:
        raise ValueError("Monasterium did not return a usable CEI record") from exc

    try:
        archive_url = archival_permalink(root)
    except ValueError:
        return create_monasterium_record(root, url)
    path, updated = create_landesarchiv_record(archive_url)
    add_monasterium_url(path, url, archive_url)
    return path, updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Monasterium charter page URL")
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
