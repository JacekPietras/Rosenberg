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
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[2]
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
            with nrw.OPENER.open(req, timeout=nrw.REQUEST_TIMEOUT) as response:
                return response.geturl(), response.read()
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
            return data['rows'][:limit], data['total']
        rows, seen, total, page = [], set(), None, 0
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
                if not isinstance(node, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', node) or node in seen:
                    raise ValueError('Missing, invalid, or duplicate result ID')
                seen.add(node)
                rows.append(row)
            if len(rows) > total:
                raise ValueError('Received more results than reported')
            if len(rows) == total or (limit is not None and len(rows) >= limit):
                break
            if not batch:
                raise ValueError('Empty page before end of results')
            page += 1
        if len(rows) == total:
            path.write_text(json.dumps({'query': query, 'total': total, 'rows': rows}, ensure_ascii=False) + '\n')
        return rows[:limit], total


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('query', help='keyword search (words may match separately)')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--download', action='store_true', help='import supported records (default)')
    mode.add_argument('--list-only', action='store_true', help='list without importing')
    mode.add_argument('--exists', action='store_true', help='print true or false without listing or importing')
    p.add_argument('--skip-existing', action='store_true')
    p.add_argument('--limit', type=int)
    p.add_argument('--delay', type=float, default=15, help='minimum seconds between requests (default 15)')
    p.add_argument('--cache-dir', type=Path, default=CACHE)
    args = p.parse_args()
    if not args.query.strip(): p.error('query must not be empty')
    if not math.isfinite(args.delay) or args.delay < 15: p.error('--delay must be at least 15 seconds')
    if args.limit is not None and args.limit < 1: p.error('--limit must be positive')
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    with (args.cache_dir / 'session.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another Archive NRW search is running; stopping', file=sys.stderr); return 1
        client = Client(args.delay, args.cache_dir)
        try:
            rows, total = client.search(args.query.strip(), 1 if args.exists else args.limit, exists=args.exists)
            if args.exists:
                print('true' if total else 'false')
                return 0
            for i, row in enumerate(rows, 1):
                node = row['nodeid']
                url = BASE + 'archivsuche?' + urlencode({'link': node})
                title = ' '.join(nrw.description_text(html.unescape(str(row.get('title') or ''))).split())
                if len(title) > 240: title = title[:237] + '...'
                print(f'{i}. {row.get("archivName") or ""} | {row.get("signatur") or ""} | {row.get("laufzeit") or ""} | {title}\n   {url}', flush=True)
                if args.list_only: continue
                if not re.fullmatch(r'VERZEICHNUNGSEINHEIT-Vz_[0-9a-f-]+', node, re.I):
                    print('Skipping: record type or ID is not supported by the NRW importer', flush=True); continue
                if args.skip_existing and has_url(ROOT / 'data/documents', url):
                    print(f'Skipping existing URL: {url}', flush=True); continue
                path, updated = nrw.create_record(url)
                print(f'{"Updated" if updated else "Created"}: {path.relative_to(ROOT)}', flush=True)
            print(f'Listed {len(rows)} of {total} catalogue results' + (' (limited)' if len(rows) < total else ''), file=sys.stderr)
            return 0
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            print(f'Error: {exc}; stopping without retry', file=sys.stderr); return 1


if __name__ == '__main__':
    raise SystemExit(main())
