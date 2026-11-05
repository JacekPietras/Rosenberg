"""Create a document record from Monasterium metadata as a fallback."""

from __future__ import annotations

import json
import re
from pathlib import Path
from xml.etree import ElementTree


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent.parent


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def node_text(node: ElementTree.Element | None) -> str:
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def first_node(root: ElementTree.Element, name: str) -> ElementTree.Element | None:
    return next((node for node in root.iter() if local_name(node.tag) == name.casefold()), None)


def create_record(root: ElementTree.Element, url: str) -> tuple[Path, bool]:
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

    from archive_record_storage import save_record
    return save_record(record, REPOSITORY_ROOT / "data" / "documents")
