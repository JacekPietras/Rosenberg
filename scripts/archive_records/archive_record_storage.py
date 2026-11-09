"""Preserve existing document entries while adding downloaded metadata."""
from __future__ import annotations

import calendar
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


def values(value):
    return value if isinstance(value, list) else [value] if value else []


def normalized_url(url):
    """Normalize known alternate forms of the same archive record URL."""
    parts = urlsplit(url)
    if parts.hostname == 'www.gda.bayern.de' and parts.path in {
            '/gvl/archive.jsf', '/gvl/archive.xhtml'}:
        query = tuple(sorted((key, value) for key, value in parse_qsl(parts.query)
                             if key != 'parent_id'))
        return parts.scheme, parts.netloc, '/gvl/archive.xhtml', query
    return url


SPECIAL_PART = re.compile(
    r'(?:^|\n+)(Aussteller|Empfänger|Siegel|Siegler|Siegelbeschreibung|Besiegelung/Beglaubigung|Zeugen|Laufzeit|Enthält-/Darin-Vermerke|Vermerke|Enthält(?:\s+u\.\s*a\.)?|Umfang|Format|Formalbeschreibung)\s*:\s*',
    re.M | re.I,
)


def normalized(text):
    return ' '.join(text.split())


def text_parts(text):
    matches = list(SPECIAL_PART.finditer(text))
    main = text[:matches[0].start()].strip() if matches else text.strip()
    parts = [(match[1], text[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)].strip())
             for i, match in enumerate(matches)]
    return main, parts


def merge_text(old, new):
    old_main, old_parts = text_parts(old)
    new_main, new_parts = text_parts(new)
    if not normalized(old_main) or normalized(old_main) != normalized(new_main):
        return old
    main = max((old_main, new_main), key=len)
    parts = []
    for label, content in old_parts + new_parts:
        if not content:
            continue
        for i, (known_label, known_content) in enumerate(parts):
            if label.casefold() != known_label.casefold():
                continue
            if normalized(content) in normalized(known_content):
                break
            if normalized(known_content) in normalized(content):
                parts[i] = (known_label, content)
                break
        else:
            parts.append((label, content))
    return main + ''.join(f'\n\n{label}: {content}' for label, content in parts)


def texts(entry):
    return {normalized(main) for key in ('german', 'latin', 'summary')
            if isinstance((value := entry.get(key)), str)
            and (main := text_parts(value)[0]).strip()}


def date_span(value):
    """Return inclusive date bounds for a supported document date."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if '--' in value or '/' in value:
        separator = '--' if '--' in value else '/'
        start, end = value.split(separator, 1)
        start_span, end_span = date_span(start), date_span(end)
        if start_span and end_span:
            return start_span[0], end_span[1]
        return None
    year_range = re.fullmatch(r'(\d{4})-(\d{4})', value)
    if year_range:
        return date(int(year_range[1]), 1, 1), date(int(year_range[2]), 12, 31)
    match = re.fullmatch(r'(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?', value)
    if not match:
        return None
    year, month, day = match.groups()
    year = int(year)
    if month is None:
        return date(year, 1, 1), date(year, 12, 31)
    month = int(month)
    if month < 1 or month > 12:
        return None
    if day is None:
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    try:
        exact = date(year, month, int(day))
    except ValueError:
        return None
    return exact, exact


def compatible_dates(existing, incoming):
    if existing == incoming:
        return True
    existing_span, incoming_span = date_span(existing), date_span(incoming)
    return bool(existing_span and incoming_span
                and existing_span[0] <= incoming_span[1]
                and incoming_span[0] <= existing_span[1])


def merge_entry(entry, incoming, transcribed=False):
    for key, new in incoming.items():
        if not new:
            continue
        if key in ('source', 'url'):
            items = list(values(entry.get(key)))
            for value in values(new):
                if value not in items:
                    items.append(value)
            if items:
                entry[key] = items[0] if len(items) == 1 else items
        elif key == 'img':
            old = list(values(entry.get('img')))
            known = {item.get('src') if isinstance(item, dict) else item for item in old}
            for item in values(new):
                src = item.get('src') if isinstance(item, dict) else item
                if src and src not in known:
                    old.append(item)
                    known.add(src)
            if old:
                entry['img'] = old
        elif key in ('german', 'latin') and transcribed:
            continue
        elif key in ('german', 'latin', 'summary') and isinstance(entry.get(key), str) and isinstance(new, str):
            entry[key] = merge_text(entry[key], new)
        elif key not in entry or entry[key] in (None, '', []):
            entry[key] = new


def save_record(record, document_dir: Path):
    document_dir.mkdir(parents=True, exist_ok=True)
    date = str(record['date'])
    # Range endpoints belong in document metadata; filenames use the beginning.
    date = re.split(r'/|--', date, maxsplit=1)[0]
    if re.fullmatch(r'\d{4}-\d{4}', date):
        date = date[:4]
    date_start = re.match(r'^(\d{4}-\d{2}-\d{2})(?:_|$)', date)
    if date_start:
        date = date_start.group(1)
    stem = re.sub(r'[^0-9-]+', '_', date)
    pattern = re.compile(rf'{re.escape(stem)}(?:_(\d+))?\.json$')
    paths = sorted((p for p in document_dir.glob(f'{stem}*.json') if pattern.fullmatch(p.name)),
                   key=lambda p: (int(pattern.fullmatch(p.name).group(1) or 1), p.name))
    incoming = record['entries'][0]
    incoming_sources = set(values(incoming.get('source')))
    incoming_urls = {normalized_url(url) for url in values(incoming.get('url'))}
    incoming_texts = texts(incoming)
    # Check citations first, then main text without catalog metadata sections.
    for by_source, candidates in ((True, paths), (False, sorted(document_dir.glob('*.json')))):
        if by_source and not (incoming_sources or incoming_urls) or not by_source and not incoming_texts:
            continue
        for path in candidates:
            document = json.loads(path.read_text(encoding='utf-8'))
            for entry in document.get('entries', []):
                if not isinstance(entry, dict):
                    continue
                existing_urls = {normalized_url(url) for url in values(entry.get('url'))}
                match = bool(incoming_sources.intersection(values(entry.get('source'))) or incoming_urls.intersection(existing_urls)) if by_source else bool(incoming_texts.intersection(texts(entry)))
                if not by_source and not compatible_dates(document.get('date'), record.get('date')):
                    match = False
                if not match:
                    continue
                before = json.dumps(document, ensure_ascii=False, sort_keys=True)
                merge_entry(entry, incoming, document.get('transcribed') is True)
                if json.dumps(document, ensure_ascii=False, sort_keys=True) != before:
                    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                return path, True
    suffixes = [int(m.group(1)) for p in paths if (m := pattern.fullmatch(p.name)) and m.group(1)]
    output = document_dir / (f'{stem}_{max(suffixes, default=1) + 1}.json' if paths else f'{stem}.json')
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return output, False


def has_url(document_dir: Path, url: str) -> bool:
    wanted = normalized_url(url)
    for path in document_dir.glob('*.json'):
        document = json.loads(path.read_text(encoding='utf-8'))
        for entry in document.get('entries', []):
            if isinstance(entry, dict) and wanted in {
                    normalized_url(existing) for existing in values(entry.get('url'))}:
                return True
    return False


def has_source(document_dir: Path, source: str) -> bool:
    """Return whether an entry already has this exact archival citation."""
    for path in document_dir.glob('*.json'):
        document = json.loads(path.read_text(encoding='utf-8'))
        for entry in document.get('entries', []):
            if isinstance(entry, dict) and source in values(entry.get('source')):
                return True
    return False
