"""Preserve existing document entries while adding downloaded metadata."""
from __future__ import annotations

import json
import re
from pathlib import Path


def values(value):
    return value if isinstance(value, list) else [value] if value else []


def texts(entry):
    return {' '.join(value.split()) for key in ('german', 'latin', 'summary')
            if isinstance((value := entry.get(key)), str) and value.strip()}


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
        elif key not in entry or entry[key] in (None, '', []):
            entry[key] = new


def save_record(record, document_dir: Path):
    document_dir.mkdir(parents=True, exist_ok=True)
    date = str(record['date'])
    stem = re.sub(r'[^0-9-]+', '_', date)
    pattern = re.compile(rf'{re.escape(stem)}(?:_(\d+))?\.json$')
    paths = sorted((p for p in document_dir.glob(f'{stem}*.json') if pattern.fullmatch(p.name)),
                   key=lambda p: (int(pattern.fullmatch(p.name).group(1) or 1), p.name))
    incoming = record['entries'][0]
    incoming_sources = set(values(incoming.get('source')))
    incoming_texts = texts(incoming)
    # Check citations first, followed by exact text across all document dates.
    for by_source, candidates in ((True, paths), (False, sorted(document_dir.glob('*.json')))):
        if by_source and not incoming_sources or not by_source and not incoming_texts:
            continue
        for path in candidates:
            document = json.loads(path.read_text(encoding='utf-8'))
            for entry in document.get('entries', []):
                if not isinstance(entry, dict):
                    continue
                match = bool(incoming_sources.intersection(values(entry.get('source')))) if by_source else bool(incoming_texts.intersection(texts(entry)))
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
    for path in document_dir.glob('*.json'):
        document = json.loads(path.read_text(encoding='utf-8'))
        for entry in document.get('entries', []):
            if isinstance(entry, dict) and url in values(entry.get('url')):
                return True
    return False
