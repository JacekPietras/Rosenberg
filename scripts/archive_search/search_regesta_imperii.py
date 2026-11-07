#!/usr/bin/env python3
"""Search Regesta Imperii using its quick search and optionally import records."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import re
import sys
import time
import uuid
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/archive_search'))
from search_results import ResultsStore
from search_retry import retry_get
sys.path.insert(0, str(ROOT / 'scripts/archive_records'))
import archive_record_regesta_imperii as ri
from archive_record_storage import has_url

URL = 'https://www.regesta-imperii.de/regesten/suche.html'
CACHE = ROOT / '.cache/archive_search/regesta_imperii'

class Form(HTMLParser):
    def __init__(self):
        super().__init__(); self.active = False; self.fields = {}; self.action = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form' and a.get('id') == 'quicksearchform':
            self.active = True; self.action = a.get('action')
        if self.active and tag == 'input' and a.get('name'):
            self.fields[a['name']] = a.get('value', '')
    def handle_endtag(self, tag):
        if tag == 'form' and self.active: self.active = False

class Results(HTMLParser):
    def __init__(self):
        super().__init__(); self.heading = False; self.current = None; self.rows = []; self.pages = {}; self.text = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'h4': self.heading = True
        if tag == 'a':
            href = a.get('href', '')
            q = parse_qs(urlsplit(href).query)
            page = q.get('tx_hisodat_sources[@widget_0][currentPage]', [])
            if page and page[0].isdigit(): self.pages[int(page[0])] = href
            if self.heading and '/regesten/suche/result/nr/' in href:
                self.current = {'url': href.split('?')[0], 'title': ''}
    def handle_data(self, data):
        self.text.append(data)
        if self.current is not None: self.current['title'] += data
    def handle_endtag(self, tag):
        if tag == 'a' and self.current is not None:
            self.current['title'] = ' '.join(self.current['title'].split()); self.rows.append(self.current); self.current = None
        if tag == 'h4': self.heading = False

class Client:
    def __init__(self, delay, cache):
        self.delay = delay; self.cache = cache
        ri.request_url = self.request_url
    def wait(self):
        stamp = self.cache / 'last-request'
        previous = float(stamp.read_text()) if stamp.exists() else 0
        time.sleep(max(0, self.delay - (time.time() - previous)))
        stamp.write_text(str(time.time()))
    def request_url(self, url):
        self.wait()
        req = Request(url, headers={'User-Agent': ri.USER_AGENT, 'Accept': 'application/xml,text/xml,text/html,*/*'})
        try:
            def read():
                with ri.OPENER.open(req, timeout=60) as response:
                    return response.geturl(), response.read()
            return retry_get(read, self.delay, self.wait)
        except HTTPError as exc:
            body = exc.read()
            if exc.code == 403 and ri.ANUBIS_CHALLENGE_RE.search(body.decode('utf-8', 'replace')):
                return exc.geturl(), body
            raise RuntimeError(f'HTTP {exc.code}; Retry-After: {exc.headers.get("Retry-After", "not provided")}') from exc
    def post(self, action, fields):
        boundary = '----Rosenberg' + uuid.uuid4().hex
        body = b''.join((f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n').encode() for k, v in fields.items()) + f'--{boundary}--\r\n'.encode()
        self.wait()
        req = Request(action, data=body, headers={'User-Agent': ri.USER_AGENT, 'Content-Type': 'multipart/form-data; boundary=' + boundary})
        with ri.OPENER.open(req, timeout=60) as resp: return resp.read()
    def search(self, query, limit, exists=False):
        path = self.cache / (hashlib.sha256(query.encode()).hexdigest() + '.json')
        if path.exists():
            data = json.loads(path.read_text()); print(f'Using cached search: {path}', file=sys.stderr)
            available = data.get('available', data.get('total'))
            if (data.get('query') != query or not isinstance(data.get('rows'), list)
                    or not isinstance(data.get('total'), int)
                    or not isinstance(available, int) or available < 0
                    or available > data['total'] or len(data['rows']) != available):
                raise ValueError('Invalid cached search')
            return data['rows'][:limit], data['total']
        _, page = ri.fetch(URL)
        form = Form(); form.feed(page.decode('utf-8', 'replace'))
        if not form.action or 'tx_hisodat_sources[__trustedProperties]' not in form.fields: raise ValueError('Search form missing')
        action = urljoin(URL, form.action)
        if urlsplit(action).hostname not in ri.HOSTS: raise ValueError('Unexpected search form host')
        form.fields['tx_hisodat_sources[searchstring]'] = query
        page = self.post(action, form.fields)
        rows = []; seen = set(); number = 1; total = None; available = None
        while True:
            result = Results(); result.feed(page.decode('utf-8', 'replace'))
            plain = ' '.join(' '.join(result.text).split())
            match = re.search(
                r'Ihre Suche (?:hat\s+([\d.]+)\s+Treffer ergeben|'
                r'erzielte\s+([\d.]+)\s+Treffer)', plain)
            if not match:
                if re.search(r'Nichts gefunden!', plain, re.IGNORECASE):
                    count = 0
                else:
                    raise ValueError('Could not read the result count; stopping')
            else:
                count = int((match[1] or match[2]).replace('.', ''))
            selected = re.search(r'ausgewählt wurden die\s+([\d.]+)\s+relevantesten Regesten', plain)
            page_count = min(count, int(selected[1].replace('.', ''))) if selected else count
            if exists: return [], count
            if total is not None and count != total: raise ValueError('Result count changed')
            if available is not None and page_count != available:
                raise ValueError('Available result count changed')
            total = count; available = page_count
            for row in result.rows:
                if row['url'] in seen: raise ValueError('Duplicate result')
                seen.add(row['url']); rows.append(row)
            if len(rows) >= available or (limit and len(rows) >= limit): break
            next_url = result.pages.get(number + 1)
            if not next_url or not result.rows: raise ValueError('Missing results or pagination link')
            next_url = urljoin(URL, next_url)
            if urlsplit(next_url).hostname not in ri.HOSTS: raise ValueError('Unexpected pagination host')
            _, page = ri.fetch(next_url); number += 1
        if len(rows) > available: raise ValueError('Too many results')
        if len(rows) == available:
            path.write_text(json.dumps({'query': query, 'total': total, 'available': available, 'rows': rows}, ensure_ascii=False, indent=2) + '\n')
        return rows[:limit], total

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', help='quick-search terms (the site combines terms with AND)')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--download', action='store_true', help='download matching records (default)')
    mode.add_argument('--list-only', action='store_true', help='list without downloading')
    mode.add_argument('--exists', action='store_true', help='print true or false without listing or importing')
    parser.add_argument('--skip-existing', action='store_true')
    parser.add_argument('--results-file', type=Path, help='JSON file for verified existence results')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--delay', type=float, default=15, help='minimum seconds between requests (default 15)')
    parser.add_argument('--cache-dir', type=Path, default=CACHE)
    args = parser.parse_args()
    results = ResultsStore('regesta_imperii', args.results_file)
    if not args.query.strip(): parser.error('query must not be empty')
    query = args.query.strip()
    if '.' in query:
        undotted = query.replace('.', '')
        if not args.exists:
            print(f'Skipping dotted query; use {undotted!r}', file=sys.stderr)
            return 0
        query = undotted
    if not math.isfinite(args.delay) or args.delay < 15: parser.error('--delay must be at least 15 seconds')
    if args.limit is not None and args.limit < 1: parser.error('--limit must be positive')
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    with (args.cache_dir / 'session.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another Regesta Imperii search is running; stopping', file=sys.stderr); return 1
        client = Client(args.delay, args.cache_dir)
        try:
            if not args.exists and results.get(query) is False:
                print('Skipping search: saved result is empty', file=sys.stderr)
                return 0
            if args.exists:
                found = results.exists(query, lambda: client.search(query, 1, exists=True)[1] > 0)
                print('true' if found else 'false')
                return 0
            rows, total = client.search(query, args.limit)
            results.record(query, total > 0)
            for i, row in enumerate(rows, 1):
                url = row['url']; print(f'{i}. {row["title"]}\n   {url}', flush=True)
                if args.list_only: continue
                if args.skip_existing and has_url(ROOT / 'data/documents', url):
                    print(f'Skipping existing URL: {url}'); continue
                try:
                    path, updated = ri.create_record(url)
                except HTTPError as exc:
                    if exc.code != 404:
                        raise
                    print(f'Skipping unavailable record (HTTP 404): {url}', file=sys.stderr)
                    continue
                except RuntimeError as exc:
                    if not str(exc).startswith('HTTP 404;'):
                        raise
                    print(f'Skipping unavailable record (HTTP 404): {url}', file=sys.stderr)
                    continue
                print(f'{"Updated" if updated else "Created"}: {path.relative_to(ROOT)}', flush=True)
            print(f'Listed {len(rows)} of {total} catalogue results' + (' (limited)' if len(rows) < total else ''), file=sys.stderr)
            return 0
        except (OSError, ValueError, RuntimeError, HTTPError) as exc:
            print(f'Error: {exc}; stopping', file=sys.stderr); return 1

if __name__ == '__main__':
    raise SystemExit(main())
