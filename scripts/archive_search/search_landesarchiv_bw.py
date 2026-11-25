#!/usr/bin/env python3
"""Search the Landesarchiv Baden-Württemberg catalogue for an exact phrase."""
from __future__ import annotations

import argparse
import http.cookiejar
import hashlib
import json
import re
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / 'scripts/archive_search'))
from search_results import ResultsStore, search_delay
from search_retry import retry_get, retry_http_500
sys.path.insert(0, str(ROOT / "scripts" / "archive_records"))
from archive_record_storage import has_source, has_url, read_document, values
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener

CACHE = ROOT / '.cache/archive_search/landesarchiv_bw'

BASE = 'https://www2.landesarchiv-bw.de/ofs21/'


def has_result_url(document_dir, result_id):
    """Match a search result against stored catalogue URLs without fetching it."""
    for path in document_dir.glob('*.json'):
        document = read_document(path)
        for entry in document.get('entries', []):
            if not isinstance(entry, dict):
                continue
            for url in values(entry.get('url')):
                if not isinstance(url, str):
                    continue
                parts = urlsplit(url)
                query = parse_qs(parts.query)
                if parts.hostname in ('www.landesarchiv-bw.de', 'landesarchiv-bw.de') and parts.path.rstrip('/') == '/plink':
                    if any(re.fullmatch(r'\d+-' + re.escape(result_id), aid) for aid in query.get('f', [])):
                        return True
                if parts.hostname == 'www2.landesarchiv-bw.de' and parts.path == '/ofs21/olf/druckansicht.php':
                    if result_id in query.get('id_titlaufn', []):
                        return True
    return False


class SearchPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_article = False
        self.in_signature = False
        self.signature = []
        self.row = None
        self.rows = []
        self.in_pagination = False
        self.pagination = []
        self.pagination_action = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form' and a.get('name') == 'uebergabe':
            self.in_pagination = True
            self.pagination_action = a.get('action')
        elif tag == 'input' and self.in_pagination and a.get('name'):
            self.pagination.append((a['name'], a.get('value', '')))
        if tag == 'article':
            self.in_article = True
            self.row = {'id': None, 'signature': '', 'bestand': None, 'date': '', 'has_viewer': False}
            self.signature = []
        if not self.in_article:
            return
        title = a.get('title', '')
        match = re.match(r'Id:\s*(\d+)', title)
        if tag == 'td' and match:
            self.row['id'] = match.group(1)
        elif tag == 'td' and 'Formulartyp' in title:
            self.row['date'] = title.split('/')[0]
        elif tag == 'b' and self.row['id'] and not self.row['signature']:
            self.in_signature = True
        elif tag == 'a' and 'bild_zoom/' in a.get('href', ''):
            self.row['has_viewer'] = True
        elif tag == 'a' and 'struktur.php?' in a.get('href', ''):
            query = parse_qs(urlsplit(a['href']).query)
            if query.get('sprungId', [''])[0] == self.row['id']:
                self.row['bestand'] = query.get('bestand', [''])[0]

    def handle_data(self, data):
        if self.in_signature:
            self.signature.append(data)

    def handle_endtag(self, tag):
        if tag == 'form' and self.in_pagination:
            self.in_pagination = False
        if tag == 'b' and self.in_signature:
            self.in_signature = False
            self.row['signature'] = ' '.join(''.join(self.signature).split())
        if tag == 'article' and self.in_article:
            self.in_article = False
            if self.row['id']:
                self.rows.append(self.row)


class Canonical(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.url = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'link' and 'canonical' in a.get('rel', '').lower().split():
            self.url = a.get('href')


class Client:
    def __init__(self, delay, cache_dir=CACHE):
        self.cache_dir = Path(cache_dir)
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.delay = delay
        self.last_request = None
        self.current_page = 1

    def wait(self):
        if self.last_request is not None:
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()

    def request(self, url, data=None):
        self.wait()
        req = Request(url, data=data, headers={'User-Agent': 'Rosenberg archive research/1.0'})
        try:
            def read():
                with self.opener.open(req, timeout=60) as response:
                    return response.read().decode(response.headers.get_content_charset() or 'utf-8', 'replace')
            return retry_http_500(lambda: retry_get(read, self.delay, self.wait) if data is None else read(), self.wait)
        except HTTPError as exc:
            if exc.code in (403, 429, 503):
                raise RuntimeError(f'Archive returned HTTP {exc.code}; stopping. Retry-After: {exc.headers.get("Retry-After", "not provided")}') from exc
            raise

    def search(self, phrase, limit=None, exists=False, skip_pages=0):
        path = self.cache_dir / (hashlib.sha256(phrase.encode()).hexdigest() + '.json')
        if path.exists():
            cached = json.loads(path.read_text(encoding='utf-8'))
            if cached.get('query') != phrase or not isinstance(cached.get('rows'), list) or cached.get('total') != len(cached['rows']):
                raise ValueError('Invalid cached search')
            print(f'Using cached search: {path}', file=sys.stderr)
            total = cached['total']
            if exists:
                yield None, total
                return
            if skip_pages and skip_pages * 30 >= total:
                raise ValueError(f'Cannot skip {skip_pages} pages: catalogue reports {total} hits')
            rows = cached['rows'][skip_pages * 30:]
            for index, row in enumerate(rows[:limit], start=skip_pages * 30):
                self.current_page = index // 30 + 1
                yield row, total
            return
        rows = []
        for row, total in self._search(phrase, limit, exists, skip_pages):
            if not exists and not skip_pages:
                rows.append(row.copy())
                if len(rows) == total:
                    self._save_search(path, phrase, rows)
            yield row, total
        if not exists and not skip_pages and not rows:
            self._save_search(path, phrase, rows)

    def _save_search(self, path, phrase, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'query': phrase, 'total': len(rows), 'rows': rows}, ensure_ascii=False) + '\n', encoding='utf-8')

    def _search(self, phrase, limit=None, exists=False, skip_pages=0):
        self.request(BASE + 'home.php')
        params = {'sortierung': 'archivort asc, klassifi_bestand asc, bereich asc, klassifi asc',
                  'trefferausgabe': '30', 'sucheAusgangspunkt': '../index', 'suchMaschine': 'lucene',
                  'logik': 'und', 'suche': f'"{phrase}"', 'archive[]': 'alle'}
        html = self.request(BASE + 'suche/ergebnis1.php', urlencode(params).encode())
        page_number = 0
        seen = set()
        total = None
        previous_end = 0
        while True:
            page = SearchPage(); page.feed(html)
            hidden = dict(page.pagination)
            try:
                count = int(hidden['treffer'])
            except (KeyError, ValueError) as exc:
                raise ValueError('Could not read the catalogue result count') from exc
            if exists:
                yield None, count
                return
            if total is not None and count != total:
                raise ValueError('Result count changed during pagination')
            total = count
            if not total:
                return
            try:
                end = int(hidden['bisTreffer'])
            except (KeyError, ValueError) as exc:
                raise ValueError('Could not read the catalogue page range') from exc
            if skip_pages and page_number == skip_pages and end != min((skip_pages + 1) * 30, total):
                raise ValueError(f'Catalogue did not return requested page {page_number + 1}')
            if not previous_end < end <= total:
                raise ValueError('Invalid catalogue page range')
            previous_end = end
            if not page.rows:
                raise ValueError('Catalogue returned an empty page before the end')
            if page_number == 0 and skip_pages:
                if skip_pages * 30 >= total:
                    raise ValueError(f'Cannot skip {skip_pages} pages: catalogue reports {total} hits')
                if not page.pagination_action:
                    raise ValueError('Catalogue did not provide a pagination form')
                page_number = skip_pages
                self.current_page = page_number + 1
                fields = [(k, str(page_number) if k == 'trefferseite' else v) for k, v in page.pagination]
                print(f'Skipping to catalogue page {self.current_page}', file=sys.stderr, flush=True)
                html = self.request(urljoin(BASE + 'suche/', page.pagination_action), urlencode(fields).encode())
                continue
            print(f'Catalogue page {page_number + 1}: results through {end} of {total}',
                  file=sys.stderr, flush=True)
            for row in page.rows:
                if row['id'] in seen:
                    raise ValueError('Catalogue returned a duplicate result during pagination')
                seen.add(row['id'])
                yield row, total
                if limit is not None and len(seen) >= limit:
                    return
            if end == total:
                return
            if not page.pagination_action:
                raise ValueError('Catalogue did not provide a pagination form')
            page_number += 1
            self.current_page = page_number + 1
            fields = [(k, str(page_number) if k == 'trefferseite' else v) for k, v in page.pagination]
            html = self.request(urljoin(BASE + 'suche/', page.pagination_action), urlencode(fields).encode())

    def resolve(self, row):
        params = {'id_titlaufn': row['id']}
        if row['bestand'] and row['bestand'].isdigit():
            params['bestand'] = row['bestand']
        page = self.request(BASE + 'olf/druckansicht.php?' + urlencode(params))
        if 'bestand' not in params:
            for link in re.findall(r'struktur\.php\?([^\"\'<>\s]+)', page):
                query = parse_qs(link.replace('&amp;', '&'))
                if query.get('sprungId', [''])[0] == row['id']:
                    bestand = query.get('bestand', [''])[0]
                    if bestand.isdigit():
                        row['bestand'] = bestand
                        break
            if not row['bestand'] or not row['bestand'].isdigit():
                raise ValueError(f"No collection identifier for result {row['id']}")
        parser = Canonical(); parser.feed(page)
        if not parser.url:
            raise ValueError(f"No permalink for result {row['id']}")
        parsed = urlsplit(parser.url)
        aid = parse_qs(parsed.query).get('f', [''])[0]
        if parsed.hostname not in ('www.landesarchiv-bw.de', 'landesarchiv-bw.de') or not re.fullmatch(r'\d+-\d+(?:-\d+)?', aid):
            raise ValueError(f"Invalid permalink for result {row['id']}")
        return 'https://www.landesarchiv-bw.de/plink/?' + urlencode({'f': aid})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', help='phrase to search for')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--list-only', action='store_true', help='list results without downloading')
    mode.add_argument('--exists', action='store_true', help='print true or false without listing or importing')
    parser.add_argument('--skip-existing', action='store_true', help='skip records with a stored citation or URL')
    parser.add_argument('--limit', type=int, help='maximum number of results')
    parser.add_argument('--skip-pages', type=int, default=0,
                        help='skip this many catalogue pages before processing results')
    parser.add_argument('--skip-result-id', action='append', default=[],
                        help='skip this catalogue result during listing or import (repeatable)')
    parser.add_argument('--resume-after-result-id',
                        help='resume importing after this catalogue result (exclusive)')
    parser.add_argument('--delay', type=float, default=None, help='seconds between requests (overrides archive JSON)')
    parser.add_argument('--cache-dir', type=Path, default=CACHE, help='archive search cache directory')
    args = parser.parse_args()
    if args.delay is None:
        args.delay = search_delay('landesarchiv_bw')
    results = ResultsStore('landesarchiv_bw')
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
    if args.delay < 1 or not args.delay < float('inf'):
        parser.error('--delay must be at least 1 second')
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    if args.skip_pages < 0:
        parser.error('--skip-pages must be non-negative')
    if args.exists and args.skip_pages:
        parser.error('--skip-pages cannot be used with --exists')
    client = Client(args.delay, args.cache_dir)
    count = total = 0
    result_seen = False
    failures = []
    consecutive_failures = 0
    resume_pending = bool(args.resume_after_result_id)
    resume_found = not resume_pending
    try:
        if not args.exists and results.get(phrase) is False:
            print('Skipping search: saved result is empty', file=sys.stderr)
            return 0
        if args.exists:
            found = results.exists(phrase, lambda: next(client.search(phrase, exists=True))[1] > 0)
            print('true' if found else 'false')
            return 0
        if resume_pending:
            print(f'Searching catalogue pages for resume result {args.resume_after_result_id}',
                  file=sys.stderr, flush=True)
        for row, total in client.search(phrase, args.limit, skip_pages=args.skip_pages):
            result_seen = True
            results.record(phrase, True)
            if resume_pending:
                if row['id'] == args.resume_after_result_id:
                    resume_pending = False
                    resume_found = True
                    print(f'Resuming after catalogue result {row["id"]}', file=sys.stderr, flush=True)
                continue
            if row['id'] in args.skip_result_id:
                print(f'Skipping catalogue result {row["id"]}', file=sys.stderr, flush=True)
                consecutive_failures = 0
                continue
            if not args.list_only and args.skip_existing and has_source(ROOT / 'data/documents', row['signature']):
                print(f'Skipping existing citation: {row["signature"]}', flush=True)
                consecutive_failures = 0
                continue
            if not args.list_only and args.skip_existing and has_result_url(ROOT / 'data/documents', row['id']):
                print(f'Skipping existing URL for catalogue result {row["id"]}', flush=True)
                consecutive_failures = 0
                continue
            try:
                url = client.resolve(row)
            except (OSError, ValueError) as exc:
                failures.append((client.current_page, row['id'], row['signature'], str(exc)))
                print(f'Skipping result {row["id"]} ({row["signature"]}) on page {client.current_page}: {exc}', file=sys.stderr, flush=True)
                consecutive_failures += 1
                if consecutive_failures >= 2:
                    raise RuntimeError(f'Stopping after consecutive failures; last result {row["id"]}') from exc
                continue
            count += 1
            print(f'{count}. {row["signature"]} | {row["date"]}\n   {url}', flush=True)
            if not args.list_only and args.skip_existing and has_url(ROOT / 'data/documents', url):
                print(f'Skipping existing URL: {url}', flush=True)
                consecutive_failures = 0
                continue
            if not args.list_only:
                client.wait()
                print(f'Downloading {url}', flush=True)
                command = [sys.executable, str(ROOT / 'scripts/archive_records/archive_record_download.py'), url,
                    '--catalog-id', row['id'], '--bestand', row['bestand'],
                    '--delay', str(args.delay)]
                if row['has_viewer']:
                    command.append('--has-viewer')
                proc = subprocess.run(command, cwd=ROOT)
                client.last_request = time.monotonic()
                if proc.returncode:
                    failures.append((client.current_page, row['id'], row['signature'],
                                     f'downloader failed for {url} (exit {proc.returncode})'))
                    print(f'Skipping result {row["id"]} on page {client.current_page} after downloader failure', file=sys.stderr, flush=True)
                    consecutive_failures += 1
                    if consecutive_failures >= 2:
                        raise RuntimeError(f'Stopping after consecutive failures; last result {row["id"]}')
                    continue
            consecutive_failures = 0
        if not resume_found:
            raise ValueError(f'Could not find resume result {args.resume_after_result_id}')
        if not result_seen:
            results.record(phrase, False)
        suffix = f'; skipped {len(failures)} problematic result(s)' if failures else ''
        print(f'Listed {count} results; catalogue reports {total} hits' + (' (limit applied)' if args.limit is not None else '') + suffix,
              file=sys.stderr)
        if failures:
            for page, result_id, signature, error in failures:
                print(f'  page {page} | {result_id} | {signature}: {error}', file=sys.stderr)
        return 1 if failures else 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Error on catalogue page {client.current_page} after {count} results: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
