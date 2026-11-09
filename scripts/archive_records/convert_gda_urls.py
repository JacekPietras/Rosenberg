#!/usr/bin/env python3
"""Replace legacy GDA archive URLs with verified document permalinks.

Run without --apply to preview; use --apply to update document JSON files.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from archive_record_gda_bayern import DOCUMENT_DIR, USER_AGENT, fetch, document_permalink

PREFIX = 'https://www.gda.bayern.de/gvl/archive.xhtml?id='
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)


def archive_id(url):
    value = parse_qs(urlsplit(url).query).get('id', [''])[0]
    match = UUID.search(value)
    return match.group().lower() if match else None


def resolve(url):
    expected = archive_id(url)
    if not expected:
        raise ValueError('missing archive record ID')
    permalink = document_permalink(fetch(url))
    if not permalink:
        raise ValueError('page has no document permalink')
    request = Request(permalink, headers={'User-Agent': USER_AGENT})
    with urlopen(request, timeout=60) as response:
        actual = archive_id(response.geturl())
    if actual != expected:
        raise ValueError(f'permalink redirects to a different record ({actual})')
    return permalink


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='write changes to JSON files')
    parser.add_argument('--delay', type=float, default=0.5, help='seconds between record lookups')
    parser.add_argument('--limit', type=int, help='maximum number of distinct archive IDs to look up')
    parser.add_argument('--shards', type=int, default=1, help='split files among this many workers')
    parser.add_argument('--shard', type=int, default=0, help='worker index, starting at zero')
    args = parser.parse_args()
    if args.shards < 1 or not 0 <= args.shard < args.shards:
        parser.error('shard must be between zero and shards minus one')
    cache = {}
    failures = 0
    changed = 0
    for index, path in enumerate(sorted(DOCUMENT_DIR.glob('*.json'))):
        if index % args.shards != args.shard:
            continue
        original = path.read_text(encoding='utf-8')
        data = json.loads(original)
        replacements = {}
        for entry in data.get('entries', []):
            urls = entry.get('url', [])
            for url in [urls] if isinstance(urls, str) else urls:
                if not isinstance(url, str) or not url.startswith(PREFIX):
                    continue
                key = archive_id(url) or url
                if key not in cache:
                    if args.limit is not None and len(cache) >= args.limit:
                        continue
                    try:
                        cache[key] = resolve(url)
                    except (OSError, ValueError) as exc:
                        cache[key] = None
                        failures += 1
                        print(f'{path.name}: {url}: {exc}', file=sys.stderr)
                    time.sleep(max(0, args.delay))
                if cache[key]:
                    replacements[url] = cache[key]
        if replacements:
            result = original
            for old, new in replacements.items():
                result = result.replace(json.dumps(old, ensure_ascii=False), json.dumps(new, ensure_ascii=False))
            json.loads(result)
            if args.apply:
                path.write_text(result, encoding='utf-8')
            changed += len(replacements)
            for old, new in replacements.items():
                print(f'{path.name}: {old} -> {new}', flush=True)
    print(f'{"Updated" if args.apply else "Would update"} {changed} URLs; {failures} lookup failures.', file=sys.stderr)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
