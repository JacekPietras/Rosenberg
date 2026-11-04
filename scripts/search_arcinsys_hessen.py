#!/usr/bin/env python3
"""List Arcinsys Hessen search results and optionally download their records."""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener


BASE = 'https://arcinsys.hessen.de/arcinsys/'
ROOT = Path(__file__).resolve().parent.parent
COLUMNS = ['columnKeyItemType', 'columnKeySignatur', 'columnKeyBezeichnung',
           'columnKeyLaufzeit', 'columnKeyInfoIcons', 'columnKeyPreviewImage', 'columnKeyActions']


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.execution = None
        self.csrf = None
        self.in_form = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form' and a.get('id') == 'simpleSearchForm':
            self.in_form = True
        if self.in_form and tag == 'input' and a.get('name') == 'executionId':
            self.execution = a.get('value')
        if tag == 'meta' and a.get('name') == '_csrf':
            self.csrf = a.get('content')

    def handle_endtag(self, tag):
        if tag == 'form':
            self.in_form = False


class Client:
    def __init__(self, delay):
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.delay = delay
        self.last_request = None

    def request(self, url, data=None):
        if self.last_request is not None:
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        request = Request(url, data=data, headers={'User-Agent': 'Rosenberg archive research/1.0',
                                                   'X-Requested-With': 'XMLHttpRequest'})
        try:
            with self.opener.open(request, timeout=60) as response:
                return response.url, response.read().decode('utf-8', 'replace')
        except HTTPError as exc:
            if exc.code in (403, 429, 503):
                raise RuntimeError(f'Archive returned HTTP {exc.code}; stopping. Retry-After: {exc.headers.get("Retry-After", "not provided")}') from exc
            raise

    def search(self, query, limit=None):
        _, page = self.request(urljoin(BASE, 'simpleSearch.action'))
        form = FormParser(); form.feed(page)
        if not form.execution:
            raise ValueError('Could not find the Arcinsys search form execution ID')
        params = {'executionId': form.execution, 'filter.searchTerm': query,
                  'filter.selectedSearchArea': 'ALL_ARCHIVES'}
        _, page = self.request(urljoin(BASE, 'simpleSearch_search.action?') + urlencode(params))
        if 'Ihre Suche hat keine Treffer erzielt.' in page or 'Your search returned no results' in page:
            return
        form = FormParser(); form.feed(page)
        match = re.search(r'data-query-table-data-url="([^"]+)', page)
        if not match or not form.csrf:
            raise ValueError('Search did not return the expected results page')
        import html
        table_url = urljoin(BASE, html.unescape(match.group(1)))
        tree_match = re.search(r'data-tree-data-url="([^"]+)', page)
        if not tree_match:
            raise ValueError('Search result tree is missing')
        _, body = self.request(urljoin(BASE, html.unescape(tree_match.group(1))) + '&id=')
        tree = json.loads(body)
        if not tree or not tree[0].get('id'):
            raise ValueError('Search result tree has no root')
        table_url += '&' + urlencode({'nodeId': tree[0]['id']})
        columns = [{'data': n, 'name': n, 'searchable': True, 'orderable': False,
                    'search': {'value': '', 'regex': False}} for n in COLUMNS]
        start = 0
        total = None
        seen = set()
        while True:
            state = {'draw': start // 100 + 1, 'start': start, 'length': 100,
                     'columns': columns, 'order': [], 'search': {'value': '', 'regex': False},
                     'selectedRowIdsPerPage': []}
            payload = urlencode({'tableStateJson': json.dumps(state), '_csrf': form.csrf}).encode()
            _, body = self.request(table_url, payload)
            try:
                result = json.loads(body)
                rows, count = result['data'], result['recordsFiltered']
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError('Arcinsys did not return a valid result page') from exc
            if not isinstance(count, int) or not isinstance(rows, list):
                raise ValueError('Invalid Arcinsys result count or rows')
            if total is not None and total != count:
                raise ValueError('Arcinsys result count changed during pagination; results may be incomplete')
            total = count
            if not rows and start < total:
                raise ValueError('Arcinsys returned an empty page before the end of the results')
            for row in rows:
                row_id = row.get('DT_RowId', '')
                if row_id in seen or not row_id:
                    raise ValueError('Arcinsys returned a duplicate or unidentified result')
                seen.add(row_id)
                yield row, total
                if limit is not None and len(seen) >= limit:
                    return
            start += len(rows)
            if start >= total:
                return


def record_url(row):
    for action in row.get('columnKeyActions', []):
        if action.get('key') == 'rowActionKeyShowItem' and action.get('additionalParameters', {}).get('itemPrefix') == 'v':
            ident = str(action.get('detailId', ''))
            if ident.isdigit():
                return urljoin(BASE, 'showArchivalDescriptionDetails.action?') + urlencode({'archivalDescriptionId': ident})
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('query', help='consecutive phrase to find in catalogue descriptions')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--download', action='store_true', help='download archival records (default)')
    mode.add_argument('--list-only', action='store_true', help='list results without downloading')
    p.add_argument('--limit', type=int, help='maximum number of search results to list')
    p.add_argument('--delay', type=float, default=3, help='seconds between requests and downloads (minimum 1; default 3)')
    args = p.parse_args()
    if args.delay < 1 or not args.delay < float('inf'):
        p.error('--delay must be at least 1 second')
    if args.limit is not None and args.limit < 1:
        p.error('--limit must be positive')
    phrase = args.query.strip()
    if phrase.startswith('"') and phrase.endswith('"'):
        phrase = phrase[1:-1].strip()
    if len(phrase) < 2 or '"' in phrase:
        p.error('supply a phrase of at least two characters without embedded double quotes')
    client = Client(args.delay)
    count = 0
    total = 0
    try:
        for row, total in client.search(f'"{phrase}"', args.limit):
            url = record_url(row)
            count += 1
            print(f'{count}. {row.get("columnKeySignatur", "")} | {row.get("columnKeyLaufzeit", "")} | {row.get("columnKeyBezeichnung", "")}\n   {url or "No archival record URL"}', flush=True)
            if not args.list_only and url:
                time.sleep(max(0, args.delay - (time.monotonic() - client.last_request)))
                client.last_request = time.monotonic()
                print(f'Downloading {url}', flush=True)
                proc = subprocess.run([sys.executable, str(ROOT / 'scripts/downloader_universal.py'), url, '--skip-existing'], cwd=ROOT)
                if proc.returncode:
                    raise RuntimeError(f'Downloader failed for {url}; stopping (exit {proc.returncode})')
        print(f'Listed {count} of {total} catalogue results'
              + (' (limited)' if count < total else ''), file=sys.stderr)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Error after {count} results: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
