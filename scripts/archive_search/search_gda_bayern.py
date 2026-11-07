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
sys.path.insert(0, str(ROOT / 'scripts/archive_search'))
from search_results import ResultsStore
from search_retry import retry_get
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


class Pagination(HTMLParser):
    def __init__(self, html, next_page):
        super().__init__()
        self.next_page = next_page
        self.action = None
        self.anchor = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('title') == f'Zur Seite {self.next_page}':
            self.anchor = {'id': attrs.get('id'), 'text': ''}

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor['text'] += data

    def handle_endtag(self, tag):
        if tag == 'a' and self.anchor is not None:
            if self.anchor['id'] and self.action is None:
                self.action = self.anchor['id']
            self.anchor = None


def parse_response(body, expected_total=None):
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
    elif not summary and expected_total is not None:
        total = expected_total
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
        def read():
            with self.opener.open(Request(URL, data=data, headers=headers), timeout=60) as response:
                return response.read().decode('utf-8', 'replace')
        return retry_get(read, self.delay, self.wait) if data is None else read()

    def search(self, phrase, limit=None, exists=False):
        path = self.cache_dir / (hashlib.sha256(phrase.encode()).hexdigest() + '.json')
        if path.exists():
            cached = json.loads(path.read_text())
            rows, total = cached['rows'], cached['total']
            if cached.get('query') != phrase or len(rows) != total:
                raise ValueError('Invalid cached search')
            print(f'Using cached search: {path}', file=sys.stderr)
        else:
            csp_nonce = None
            for attempt in range(2):
                page = self.request()
                form = SearchForm(); form.feed(page)
                nonce = re.search(r'<script[^>]+nonce="([^"]+)"', page)
                if not nonce or not form.fields.get('jakarta.faces.ViewState'):
                    raise ValueError('Catalogue search state or CSP nonce is missing')
                csp_nonce = nonce[1]
                fields = dict(form.fields)
                fields.update({'primefaces.nonce': nonce[1], 'searchForm': 'searchForm',
                    'searchForm:searchTerm_input': f'"{phrase}"', 'searchForm:valuesRecordPerpage': '100',
                    'jakarta.faces.partial.ajax': 'true', 'jakarta.faces.behavior.event': 'action',
                    'jakarta.faces.partial.event': 'click', 'jakarta.faces.source': 'searchForm:searchButton',
                    'jakarta.faces.partial.execute': 'searchForm', 'jakarta.faces.partial.render': RENDER,
                    'searchForm:searchButton': 'searchForm:searchButton'})
                body = self.request(urlencode(fields).encode())
                if not exists:
                    # Preserve raw responses for offline diagnosis.
                    path.with_suffix('.xml').write_text(body)
                try:
                    rows, total, updates = parse_response(body)
                    response_nonce = re.search(r"PrimeFaces\.csp\.init\('([^']+)'\)", body)
                    if response_nonce:
                        csp_nonce = response_nonce[1]
                    break
                except ValueError as exc:
                    if attempt or 'Incomplete catalogue response' not in str(exc):
                        raise
                    print('Incomplete catalogue response; refreshing search state and retrying once', file=sys.stderr)
            if exists:
                yield None, total
                return
            seen = {row['url'] for row in rows}
            if len(seen) != len(rows):
                raise ValueError('Catalogue returned duplicate results on the first page')
            if len(rows) > total:
                raise ValueError('Catalogue returned more results than reported')
            view_state = updates.get('j_id1:jakarta.faces.ViewState:0')
            current_page = 1
            while len(rows) < total and (limit is None or len(rows) < limit):
                pagination = Pagination(updates.get('pagingTopForm', ''), current_page + 1)
                if not pagination.action:
                    raise ValueError(f'Catalogue did not provide a link to page {current_page + 1}')
                if not view_state:
                    raise ValueError('Catalogue pagination state is missing')
                source = pagination.action
                fields = {
                    'pagingTopForm': 'pagingTopForm',
                    source: source,
                    'jakarta.faces.partial.ajax': 'true',
                    'jakarta.faces.source': source,
                    'jakarta.faces.partial.execute': 'pagingTopForm',
                    'jakarta.faces.partial.render': 'pagingTopForm docResultPanel pagingTopFormBottom',
                    'jakarta.faces.behavior.event': 'action',
                    'jakarta.faces.partial.event': 'click',
                    'primefaces.nonce': csp_nonce,
                    'jakarta.faces.ViewState': view_state,
                }
                for attempt in range(2):
                    body = self.request(urlencode(fields).encode())
                    path.with_suffix('.xml').write_text(body)
                    try:
                        page_rows, page_total, updates = parse_response(body, total)
                        response_nonce = re.search(r"PrimeFaces\.csp\.init\('([^']+)'\)", body)
                        if response_nonce:
                            csp_nonce = response_nonce[1]
                        break
                    except ValueError as exc:
                        if attempt or 'Incomplete catalogue response' not in str(exc):
                            raise
                        print(f'Incomplete catalogue response on page {current_page + 1}; retrying once', file=sys.stderr)
                if page_total != total:
                    raise ValueError('Catalogue result count changed during pagination')
                if not page_rows:
                    raise ValueError(f'Catalogue returned an empty page before page {current_page + 1}')
                for row in page_rows:
                    if row['url'] in seen:
                        raise ValueError('Catalogue returned a duplicate result during pagination')
                    seen.add(row['url'])
                    rows.append(row)
                if len(rows) > total:
                    raise ValueError('Catalogue returned more results than reported')
                current_page += 1
                view_state = updates.get('j_id1:jakarta.faces.ViewState:0')
            if len(rows) == total:
                path.write_text(json.dumps({'query': phrase, 'total': total, 'rows': rows}, ensure_ascii=False, indent=2) + '\n')
                path.with_suffix('.xml').unlink(missing_ok=True)
        if exists:
            yield None, total
            return
        for row in rows[:limit]:
            yield row, total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', help='consecutive phrase to find in catalogue descriptions')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--download', action='store_true', help='download archival records (default)')
    mode.add_argument('--list-only', action='store_true', help='list without downloading')
    mode.add_argument('--exists', action='store_true', help='print true or false without listing or importing')
    parser.add_argument('--skip-existing', action='store_true')
    parser.add_argument('--results-file', type=Path, help='JSON file for verified existence results')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--delay', type=float, default=15, help='seconds between requests (minimum/default 15)')
    parser.add_argument('--cache-dir', type=Path, default=CACHE)
    args = parser.parse_args()
    results = ResultsStore('gda_bayern', args.results_file)
    phrase = args.query.strip()
    if phrase.startswith('"') and phrase.endswith('"'):
        phrase = phrase[1:-1].strip()
    if '.' in phrase:
        undotted = phrase.replace('.', '')
        if not args.exists:
            print(f'Skipping dotted query; use {undotted!r}', file=sys.stderr)
            return 0
        phrase = undotted
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
        if not args.exists and results.get(phrase) is False:
            print('Skipping search: saved result is empty', file=sys.stderr)
            return 0
        if args.exists:
            found = results.exists(phrase, lambda: next(client.search(phrase, exists=True))[1] > 0)
            print('true' if found else 'false')
            return 0
        for row, total in client.search(phrase, args.limit):
            if count == 0:
                results.record(phrase, True)
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
        if count == 0:
            results.record(phrase, False)
        print(f'Listed {count} of {total} catalogue results' + (' (limited)' if count < total else ''), file=sys.stderr)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Error after {count} results: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
