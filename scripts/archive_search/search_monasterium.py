#!/usr/bin/env python3
"""Search Monasterium charters and optionally import supported results."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import ssl
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/archive_search'))
from search_results import ResultsStore
from search_retry import retry_get
sys.path.insert(0, str(ROOT / 'scripts/archive_records'))
from archive_record_storage import has_url

URL = 'https://www.monasterium.net/mom/search'
CACHE = ROOT / '.cache/archive_search/monasterium'


def open_search(request):
    # Some macOS Python installations have no configured CA bundle. Use the
    # system bundle only in that case, without overriding an explicit setting.
    paths = ssl.get_default_verify_paths()
    system_bundle = Path('/etc/ssl/cert.pem')
    if (sys.platform == 'darwin' and not paths.cafile and not paths.capath
            and 'SSL_CERT_FILE' not in os.environ and 'SSL_CERT_DIR' not in os.environ
            and system_bundle.is_file()):
        return urlopen(request, timeout=60, context=ssl.create_default_context(cafile=str(system_bundle)))
    return urlopen(request, timeout=60)


def read_search(request):
    with open_search(request) as response:
        return response.read().decode('utf-8', 'replace')


class Results(HTMLParser):
    def __init__(self, existence_only=False):
        super().__init__()
        self.existence_only = existence_only
        self.hits_depth = 0
        self.hits_text = []
        self.no_results = False
        self.search_form = False
        self.anchor = None
        self.rows = []
        self.seen = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form' and attrs.get('id') == 'search-form':
            self.search_form = True
        if tag == 'div' and 'hits' in attrs.get('class', '').split():
            self.hits_depth = 1
        elif self.hits_depth and tag == 'div':
            self.hits_depth += 1
        if tag == 'a' and not self.existence_only:
            url = urljoin(URL, attrs.get('href', ''))
            parsed = urlsplit(url)
            if (parsed.scheme == 'https' and parsed.hostname == 'www.monasterium.net'
                    and re.fullmatch(r'/mom/(?:[^/]+/){2,3}charter/?', parsed.path)):
                self.anchor = {'url': f'https://www.monasterium.net{parsed.path.rstrip("/")}', 'title': ''}

    def handle_data(self, data):
        if 'Sorry, no results were found for your search.' in data:
            self.no_results = True
        if self.hits_depth:
            self.hits_text.append(data)
        if self.anchor is not None:
            self.anchor['title'] += data

    def handle_endtag(self, tag):
        if tag == 'div' and self.hits_depth:
            self.hits_depth -= 1
        if tag == 'a' and self.anchor is not None:
            self.anchor['title'] = ' '.join(self.anchor['title'].split())
            if self.anchor['url'] not in self.seen:
                self.seen.add(self.anchor['url'])
                self.rows.append(self.anchor)
            self.anchor = None

    def total(self):
        text = ' '.join(' '.join(self.hits_text).split())
        match = re.search(r'Hits\s*([\d,\.]+)\s*to\s*([\d,\.]+)\s*of\s*([\d,\.]+)', text, re.I)
        if not match:
            if self.search_form and self.no_results and not self.rows:
                return 0
            raise ValueError('Could not read result count')
        return int(re.sub(r'[,\.]', '', match[3]))


class Client:
    def __init__(self, delay, cache):
        self.delay = delay
        self.cache = cache

    def wait(self):
        stamp = self.cache / 'last-request'
        previous = float(stamp.read_text()) if stamp.exists() else 0
        time.sleep(max(0, self.delay - (time.time() - previous)))
        stamp.write_text(str(time.time()))

    def cache_path(self, query):
        cache_key = f'and-quoted-v1\0{query}'
        return self.cache / (hashlib.sha256(cache_key.encode()).hexdigest() + '.json')

    def exists(self, query):
        path = self.cache_path(query)
        if path.exists():
            cached = json.loads(path.read_text())
            if cached.get('query') != query or len(cached['rows']) != cached['total']:
                raise ValueError('Invalid cached search')
            return cached['total'] > 0
        params = {
            'q': f'"{query}"', 'option': 'and', 'img': '', 'annotations': '',
            'sort': 'date', 'block': 1, 'categories': '', 'context': '',
        }
        self.wait()
        request = Request(URL + '?' + urlencode(params), headers={'User-Agent': 'Rosenberg archive research/1.0'})
        page = retry_get(lambda: read_search(request), self.delay, self.wait)
        result = Results(existence_only=True)
        result.feed(page)
        return result.total() > 0

    def search(self, query, limit):
        path = self.cache_path(query)
        if path.exists():
            cached = json.loads(path.read_text())
            if cached.get('query') != query or len(cached['rows']) != cached['total']:
                raise ValueError('Invalid cached search')
            print(f'Using cached search: {path}', file=sys.stderr)
            return cached['rows'][:limit], cached['total']
        rows = []
        seen = set()
        total = None
        block = 1
        while True:
            params = {
                'q': f'"{query}"',
                'option': 'and',
                'img': '',
                'annotations': '',
                'sort': 'date',
                'block': block,
                'categories': '',
                'context': '',
            }
            self.wait()
            request = Request(URL + '?' + urlencode(params), headers={'User-Agent': 'Rosenberg archive research/1.0'})
            page = retry_get(lambda: read_search(request), self.delay, self.wait)
            result = Results()
            result.feed(page)
            count = result.total()
            if total is not None and count != total:
                raise ValueError('Result count changed during pagination')
            total = count
            if not result.rows and len(rows) < total:
                raise ValueError('Empty results page before end')
            for row in result.rows:
                if row['url'] in seen:
                    raise ValueError('Duplicate result during pagination')
                seen.add(row['url'])
                rows.append(row)
            if len(rows) > total:
                raise ValueError('More results than reported')
            if len(rows) == total or (limit is not None and len(rows) >= limit):
                break
            block += 1
        if len(rows) == total:
            path.write_text(json.dumps({'query': query, 'total': total, 'rows': rows}, ensure_ascii=False, indent=2) + '\n')
        return rows[:limit], total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', help='phrase to search for')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--download', action='store_true', help='import records (default)')
    mode.add_argument('--list-only', action='store_true', help='list without downloading')
    mode.add_argument('--exists', action='store_true', help='print true or false without listing or importing results')
    parser.add_argument('--skip-existing', action='store_true')
    parser.add_argument('--results-file', type=Path, help='JSON file for verified existence results')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--delay', type=float, default=15, help='seconds between searches and imports (minimum 15)')
    parser.add_argument('--cache-dir', type=Path, default=CACHE)
    args = parser.parse_args()
    results = ResultsStore('monasterium', args.results_file)
    query = args.query.strip()
    if '.' in query:
        undotted = query.replace('.', '')
        if not args.exists:
            print(f'Skipping dotted query; use {undotted!r}', file=sys.stderr)
            return 0
        query = undotted
    if not query.strip():
        parser.error('query must not be empty')
    if not math.isfinite(args.delay) or args.delay < 15:
        parser.error('--delay must be at least 15 seconds')
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    with (args.cache_dir / 'session.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another Monasterium search is running; stopping', file=sys.stderr)
            return 1
        client = Client(args.delay, args.cache_dir)
        try:
            if not args.exists and results.get(query) is False:
                print('Skipping search: saved result is empty', file=sys.stderr)
                return 0
            if args.exists:
                print('true' if results.exists(query, lambda: client.exists(query)) else 'false')
                return 0
            rows, total = client.search(query, args.limit)
            results.record(query, total > 0)
            for i, row in enumerate(rows, 1):
                url = row['url']
                print(f'{i}. {row["title"]}\n   {url}', flush=True)
                if args.list_only:
                    continue
                if args.skip_existing and has_url(ROOT / 'data/documents', url):
                    print(f'Skipping existing URL: {url}', flush=True)
                    continue
                if not re.fullmatch(r'/mom/(?:[^/]+/){2,3}charter', urlsplit(url).path):
                    raise ValueError(f'The Monasterium importer does not support this collection URL: {url}; use --list-only')
                client.wait()
                proc = subprocess.run([sys.executable, str(ROOT / 'scripts/archive_records/archive_record_download.py'), url], cwd=ROOT)
                (client.cache / 'last-request').write_text(str(time.time()))
                if proc.returncode == 76:
                    client.cache_path(query).unlink(missing_ok=True)
                    print(f'Skipped unavailable charter: {url}', file=sys.stderr)
                    continue
                if proc.returncode:
                    raise RuntimeError(f'Downloader failed (exit {proc.returncode})')
            print(f'Listed {len(rows)} of {total} catalogue results' + (' (limited)' if len(rows) < total else ''), file=sys.stderr)
            return 0
        except HTTPError as exc:
            print(f'Error: {exc}; stopping', file=sys.stderr)
            return 75 if exc.code == 500 else 1
        except (OSError, ValueError, RuntimeError) as exc:
            print(f'Error: {exc}; stopping', file=sys.stderr)
            return 1


if __name__ == '__main__':
    raise SystemExit(main())
