"""Create a document record from Monasterium metadata as a fallback."""

from __future__ import annotations

import json
import re
from pathlib import Path
from xml.etree import ElementTree


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


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


