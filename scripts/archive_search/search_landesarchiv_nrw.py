#!/usr/bin/env python3
"""Search Archive NRW by keyword and optionally import supported records."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import html
import json
import math
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/archive_search'))
from search_results import ResultsStore
from search_retry import retry_get
sys.path.insert(0, str(ROOT / 'scripts/archive_records'))
import archive_record_nrw as nrw
from archive_record_storage import has_url

BASE = 'https://www.archive.nrw.de/'
CACHE = ROOT / '.cache/archive_search/landesarchiv_nrw'


class Client:
    def __init__(self, delay, cache):
        self.delay, self.cache = delay, cache
        nrw.request = self.request

    def request(self, url):
        stamp = self.cache / 'last-request'
        last = float(stamp.read_text()) if stamp.exists() else 0
        time.sleep(max(0, self.delay - (time.time() - last)))
        stamp.write_text(str(time.time()))
        req = Request(url, headers={'User-Agent': nrw.USER_AGENT, 'Accept': 'application/json,application/xml,text/html,*/*'})
        try:
            def read():
                with nrw.OPENER.open(req, timeout=nrw.REQUEST_TIMEOUT) as response:
                    return response.geturl(), response.read()
            return retry_get(read, self.delay, lambda: stamp.write_text(str(time.time())))
        except HTTPError as exc:
            body = exc.read()
            if exc.code == 403 and nrw.ANUBIS_CHALLENGE_RE.search(body.decode('utf-8', 'replace')):
                return exc.geturl(), body
            raise RuntimeError(f'HTTP {exc.code}; Retry-After: {exc.headers.get("Retry-After", "not provided")}') from exc

    def search(self, query, limit, exists=False):
        path = self.cache / (hashlib.sha256(query.encode()).hexdigest() + '.json')
        if path.exists():
            data = json.loads(path.read_text())
            if data.get('query') != query or len(data['rows']) != data['total']:
                raise ValueError('Invalid cached search')
            print(f'Using cached search: {path}', file=sys.stderr)
            return data['rows'][:limit], data.get('reported_total', data['total'])
        rows, seen, total, page = [], set(), None, 0
        complete = False
        while True:
            url = BASE + 'sufservice/api/search?' + urlencode({'keyword': query, 'page': page, 'size': 1 if exists else 20})
            _, body = nrw.fetch(url)
            result = json.loads(body)
            batch, count = result['searchResult'], result['hits']
            if not isinstance(batch, list) or not isinstance(count, int) or count < 0:
                raise ValueError('Invalid search response')
            if exists:
                return [], count
            if total is not None and total != count:
                raise ValueError('Result count changed during pagination')
            total = count
            for row in batch:
                node = row.get('nodeid')
                if not isinstance(node, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', node):
                    print(f'Skipping result with missing or invalid ID on page {page}', file=sys.stderr)
                    continue
                if node in seen:
                    print(f'Skipping duplicate result ID {node!r} on page {page}', file=sys.stderr)
                    continue
                seen.add(node)
                rows.append(row)
            if limit is not None and len(rows) >= limit:
                break
            if (page + 1) * 20 >= total:
                complete = True
                break
            if not batch:
                raise ValueError('Empty page before end of results')
            page += 1
        if complete:
            path.write_text(json.dumps({'query': query, 'total': len(rows),
                                        'reported_total': total, 'rows': rows}, ensure_ascii=False) + '\n')
        return rows[:limit], total


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('query', help='keyword search (words may match separately)')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--download', action='store_true', help='import supported records (default)')
    mode.add_argument('--list-only', action='store_true', help='list without importing')
    mode.add_argument('--exists', action='store_true', help='print true or false without listing or importing')
    p.add_argument('--skip-existing', action='store_true')
    p.add_argument('--results-file', type=Path, help='JSON file for verified existence results')
    p.add_argument('--limit', type=int)
    p.add_argument('--delay', type=float, default=15, help='minimum seconds between requests (default 15)')
    p.add_argument('--cache-dir', type=Path, default=CACHE)
    args = p.parse_args()
    results = ResultsStore('landesarchiv_nrw', args.results_file)
    if not args.query.strip(): p.error('query must not be empty')
    query = args.query.strip()
    if '.' in query:
        undotted = query.replace('.', '')
        if not args.exists:
            print(f'Skipping dotted query; use {undotted!r}', file=sys.stderr)
            return 0
        query = undotted
    if not math.isfinite(args.delay) or args.delay < 15: p.error('--delay must be at least 15 seconds')
    if args.limit is not None and args.limit < 1: p.error('--limit must be positive')
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    with (args.cache_dir / 'session.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another Archive NRW search is running; stopping', file=sys.stderr); return 1
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
                node = row['nodeid']
                url = BASE + 'archivsuche?' + urlencode({'link': node})
                title = ' '.join(nrw.description_text(html.unescape(str(row.get('title') or ''))).split())
                if len(title) > 240: title = title[:237] + '...'
                print(f'{i}. {row.get("archivName") or ""} | {row.get("signatur") or ""} | {row.get("laufzeit") or ""} | {title}\n   {url}', flush=True)
                if args.list_only: continue
                if not re.fullmatch(r'VERZEICH(?:NUNG|UNG)SEINHEIT-[A-Za-z0-9_-]+', node, re.I):
                    print('Skipping: record type or ID is not supported by the NRW importer', flush=True); continue
                if args.skip_existing and has_url(ROOT / 'data/documents', url):
                    print(f'Skipping existing URL: {url}', flush=True); continue
                try:
                    path, updated = nrw.create_record(url)
                except (OSError, HTTPError, URLError, RuntimeError, ValueError) as exc:
                    print(f'Skipping record that could not be imported: {exc}', file=sys.stderr, flush=True)
                    continue
                print(f'{"Updated" if updated else "Created"}: {path.relative_to(ROOT)}', flush=True)
            print(f'Listed {len(rows)} of {total} catalogue results' + (' (limited)' if len(rows) < total else ''), file=sys.stderr)
            return 0
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            print(f'Error: {exc}; stopping', file=sys.stderr); return 1


if __name__ == '__main__':
    raise SystemExit(main())
