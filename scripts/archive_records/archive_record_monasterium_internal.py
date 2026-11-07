"""Create a document record from Monasterium metadata as a fallback."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent.parent


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def node_text(node: ElementTree.Element | None) -> str:
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def first_node(root: ElementTree.Element, name: str) -> ElementTree.Element | None:
    return next((node for node in root.iter() if local_name(node.tag) == name.casefold()), None)


def parse_date(date_value: str) -> str:
    date_match = re.fullmatch(r"(\d{4})(\d{2})?(\d{2})?", date_value)
    if not date_match:
        raise ValueError(f"Unsupported Monasterium date value: {date_value!r}")
    year, month, day = date_match.groups()
    date = year
    if month and month != "00":
        date += f"-{month}"
        if day and day != "00":
            date += f"-{day}"

    return date


def create_record(root: ElementTree.Element, url: str, source_references=(), image_urls=()) -> tuple[Path, bool]:
    issued = first_node(root, "issued")
    date_node = first_node(issued, "date") if issued is not None else None
    range_node = first_node(issued, "dateRange") if issued is not None else None
    if date_node is not None:
        raw_date = date_node.get('value', '')
        if raw_date == '99999999':
            # Some edited collections use an unknown-date sentinel despite an
            # explicit historical date at the end of their abstract.
            abstract = node_text(first_node(root, 'abstract'))
            months = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']
            match = re.search(r'\b(\d{4})\.\s*(' + '|'.join(months) + r')\.?\s+(\d{1,2})\.\s*$', abstract)
            from datetime import date as calendar_date
            if match:
                date = calendar_date(int(match[1]), months.index(match[2]) + 1, int(match[3])).isoformat()
            else:
                full_months = {'jänner': 1, 'januar': 1, 'februar': 2, 'märz': 3,
                               'april': 4, 'mai': 5, 'juni': 6, 'juli': 7,
                               'august': 8, 'september': 9, 'oktober': 10,
                               'november': 11, 'dezember': 12}
                match = re.match(r'^(\d{4})\.\s*(\d{1,2})\.\s*(' + '|'.join(full_months) + r')\.', abstract, re.I)
                if not match:
                    raise ValueError('Unknown Monasterium date without an explicit date in the abstract')
                date = calendar_date(int(match[1]), full_months[match[3].casefold()], int(match[2])).isoformat()
        else:
            date = parse_date(raw_date)
    elif range_node is not None:
        start = parse_date(range_node.get("from", ""))
        end = parse_date(range_node.get("to", ""))
        if start > end:
            raise ValueError("Reversed Monasterium date range")
        if start == end:
            date = start
        elif start.endswith('-01-01') and end.endswith('-12-31'):
            date = f'{start[:4]}-{end[:4]}'
        else:
            date = f"{start}/{end}"
    else:
        raise ValueError("The Monasterium record has no supported issued date")

    abstract = node_text(first_node(root, "abstract"))
    identifier = first_node(root, "archidentifier")
    citation = node_text(identifier)
    idno = first_node(root, "idno")
    if idno is not None and node_text(idno):
        citation = f"{citation}, {node_text(idno)}" if citation else node_text(idno)
    if identifier is None:
        bibliography = node_text(first_node(root, 'bibl'))
        if bibliography:
            citation = f'{bibliography}, {citation}'
    if not abstract or not citation:
        raise ValueError("The Monasterium record has no abstract or archival citation")

    german = abstract
    seal = first_node(root, "sigillant")
    if seal is not None and node_text(seal):
        german += f"\n\nSiegler: {node_text(seal)}"
    seal_description = node_text(first_node(root, 'sealDesc'))
    if seal_description:
        german += f'\n\nSiegel: {seal_description}'
    entry: dict[str, object] = {"source": citation, "url": url, "german": german}
    if source_references:
        entry['source'] = list(dict.fromkeys([citation, *source_references]))
        entry['url'] = list(dict.fromkeys([url, *source_references]))
    graphics = [node.get("url", "").strip() for node in root.iter()
                if local_name(node.tag) == "graphic" and node.get("url", "").strip()]
    graphics = [image for image in graphics if urlsplit(image).scheme in {'http', 'https'} and urlsplit(image).netloc]
    graphics.extend(image_urls)
    if graphics:
        entry["img"] = [{"src": image} for image in dict.fromkeys(graphics)]
    record = {"date": date, "label": ["to review"], "entries": [entry]}

    from archive_record_storage import save_record
    return save_record(record, REPOSITORY_ROOT / "data" / "documents")
