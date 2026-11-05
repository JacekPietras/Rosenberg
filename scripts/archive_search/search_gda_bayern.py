#!/usr/bin/env python3
"""Search the Bavarian archive catalogue for an exact phrase, caching complete searches."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import http.cookiejar
import json
import math
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/archive_records'))
from archive_record_gda_resolver import SearchForm
from archive_record_storage import has_url

URL = 'https://www.gda.bayern.de/gvl/search.xhtml'
CACHE = ROOT / '.cache/archive_search/gda_bayern'
RENDER = 'pagingTopForm docResultPanel docsMessagePanel pagingTopFormBottom searchResultHeader toolsBarForm'


class Results(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'a' and re.fullmatch(r'searchEntry:\d+:docForm:searchDocumentLink', a.get('id', '')):
            self.row = {'url': urljoin(URL, a['href']).split('#')[0], 'title': ''}

    def handle_data(self, data):
        if self.row is not None:
            self.row['title'] += data

    def handle_endtag(self, tag):
        if tag == 'a' and self.row is not None:
            self.row['title'] = ' '.join(self.row['title'].split())
            self.rows.append(self.row)
            self.row = None


def parse_response(body):
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ValueError('Incomplete catalogue response; stopping without retry') from exc
    if root.tag != 'partial-response' or root.find('error') is not None:
        raise ValueError('Catalogue returned an error response')
    updates = {node.attrib['id']: node.text or '' for node in root.findall('./changes/update')}
    content = updates.get('docResultPanel', '')
    result = Results(); result.feed(content)
    summary = updates.get('docsMessagePanel', '')
    match = re.search(r'([\d.]+)\s+Datens(?:atz|ätze) gefunden', summary)
    if match:
        total = int(match[1].replace('.', ''))
    elif 'Suche lieferte kein Ergebnis' in summary:
        total = 0
    else:
        raise ValueError('Catalogue result count is missing')
    return result.rows, total, updates


class Client:
    def __init__(self, delay=15, cache_dir=CACHE):
        self.delay = delay
        self.cache_dir = Path(cache_dir)
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.last_request = None

    def wait(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.cache_dir / 'last-request'
        # Persist spacing across sequential invocations as well as within this run.
        previous = float(stamp.read_text()) if stamp.exists() else 0
        time.sleep(max(0, self.delay - (time.time() - previous)))
        stamp.write_text(str(time.time()))
        self.last_request = time.monotonic()

    def request(self, data=None):
        self.wait()
        headers = {'User-Agent': 'Rosenberg archive research/1.0'}
        if data is not None:
            headers['Faces-Request'] = 'partial/ajax'
        with self.opener.open(Request(URL, data=data, headers=headers), timeout=60) as response:
            return response.read().decode('utf-8', 'replace')

    def search(self, phrase, limit=None):
        path = self.cache_dir / (hashlib.sha256(phrase.encode()).hexdigest() + '.json')
        if path.exists():
            cached = json.loads(path.read_text())
            rows, total = cached['rows'], cached['total']
            if cached.get('query') != phrase or len(rows) != total:
                raise ValueError('Invalid cached search')
            print(f'Using cached search: {path}', file=sys.stderr)
        else:
            if path.with_suffix('.xml').exists():
                raise ValueError(f'An earlier raw response is cached beside {path}; inspect it before explicitly removing it to retry')
            page = self.request()
            form = SearchForm(); form.feed(page)
            nonce = re.search(r'<script[^>]+nonce="([^"]+)"', page)
            if not nonce or not form.fields.get('jakarta.faces.ViewState'):
                raise ValueError('Catalogue search state or CSP nonce is missing')
            fields = dict(form.fields)
            fields.update({'primefaces.nonce': nonce[1], 'searchForm': 'searchForm',
                'searchForm:searchTerm_input': f'"{phrase}"', 'searchForm:valuesRecordPerpage': '100',
                'jakarta.faces.partial.ajax': 'true', 'jakarta.faces.behavior.event': 'action',
                'jakarta.faces.partial.event': 'click', 'jakarta.faces.source': 'searchForm:searchButton',
                'jakarta.faces.partial.execute': 'searchForm', 'jakarta.faces.partial.render': RENDER,
                'searchForm:searchButton': 'searchForm:searchButton'})
            body = self.request(urlencode(fields).encode())
            # Preserve raw responses even when parsing fails, for offline diagnosis.
            path.with_suffix('.xml').write_text(body)
            rows, total, updates = parse_response(body)
            if len(rows) != total:
                raise ValueError(f'Catalogue returned {len(rows)} of {total} results; pagination is not yet supported. Narrow the phrase; response cached for inspection')
            if len({row['url'] for row in rows}) != total:
                raise ValueError('Catalogue returned duplicate results')
            path.write_text(json.dumps({'query': phrase, 'total': total, 'rows': rows}, ensure_ascii=False, indent=2) + '\n')
        for row in rows[:limit]:
            yield row, total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', help='consecutive phrase to find in catalogue descriptions')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--download', action='store_true', help='download archival records (default)')
    mode.add_argument('--list-only', action='store_true', help='list without downloading')
    parser.add_argument('--skip-existing', action='store_true')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--delay', type=float, default=15, help='seconds between requests (minimum/default 15)')
    parser.add_argument('--cache-dir', type=Path, default=CACHE)
    args = parser.parse_args()
    phrase = args.query.strip()
    if phrase.startswith('"') and phrase.endswith('"'):
        phrase = phrase[1:-1].strip()
    if len(phrase) < 2 or '"' in phrase:
        parser.error('supply a phrase of at least two characters without embedded double quotes')
    if not math.isfinite(args.delay) or args.delay < 15:
        parser.error('--delay must be at least 15 seconds')
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    client = Client(args.delay, args.cache_dir)
    count = total = 0
    client.cache_dir.mkdir(parents=True, exist_ok=True)
    lock = (client.cache_dir / 'session.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('Another Bavarian archive search is running; stopping', file=sys.stderr)
        return 1
    try:
        for row, total in client.search(phrase, args.limit):
            count += 1
            url = row['url']
            print(f'{count}. {row["title"]}\n   {url}', flush=True)
            if not args.list_only:
                if args.skip_existing and has_url(ROOT / 'data/documents', url):
                    print(f'Skipping existing URL: {url}', flush=True)
                    continue
                client.wait()
                proc = subprocess.run([sys.executable, str(ROOT / 'scripts/archive_records/archive_record_download.py'), url], cwd=ROOT)
                (client.cache_dir / 'last-request').write_text(str(time.time()))
                if proc.returncode:
                    raise RuntimeError(f'Downloader failed for {url}; stopping (exit {proc.returncode})')
        print(f'Listed {count} of {total} catalogue results' + (' (limited)' if count < total else ''), file=sys.stderr)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Error after {count} results: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
