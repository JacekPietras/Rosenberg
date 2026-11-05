#!/usr/bin/env python3
"""Search the Landesarchiv Baden-Württemberg catalogue for an exact phrase."""
from __future__ import annotations

import argparse
import http.cookiejar
import re
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener

BASE = 'https://www2.landesarchiv-bw.de/ofs21/'
ROOT = Path(__file__).resolve().parent.parent


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
    def __init__(self, delay):
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.delay = delay
        self.last_request = None

    def wait(self):
        if self.last_request is not None:
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()

    def request(self, url, data=None):
        self.wait()
        req = Request(url, data=data, headers={'User-Agent': 'Rosenberg archive research/1.0'})
        try:
            with self.opener.open(req, timeout=60) as response:
                return response.read().decode(response.headers.get_content_charset() or 'utf-8', 'replace')
        except HTTPError as exc:
            if exc.code in (403, 429, 503):
                raise RuntimeError(f'Archive returned HTTP {exc.code}; stopping. Retry-After: {exc.headers.get("Retry-After", "not provided")}') from exc
            raise

    def search(self, phrase, limit=None):
        self.request(BASE + 'home.php')
        params = {'sortierung': 'archivort asc, klassifi_bestand asc, bereich asc, klassifi asc',
                  'trefferausgabe': '30', 'sucheAusgangspunkt': '../index', 'suchMaschine': 'lucene',
                  'logik': 'und', 'suche': f'"{phrase}"', 'archive[]': 'alle'}
        html = self.request(BASE + 'suche/ergebnis1.php', urlencode(params).encode())
        page_number = 0
        seen = set()
        total = None
        while True:
            page = SearchPage(); page.feed(html)
            hidden = dict(page.pagination)
            try:
                count = int(hidden['treffer'])
            except (KeyError, ValueError) as exc:
                raise ValueError('Could not read the catalogue result count') from exc
            if total is not None and count != total:
                raise ValueError('Result count changed during pagination')
            total = count
            if not page.rows and len(seen) < total:
                raise ValueError('Catalogue returned an empty page before the end')
            for row in page.rows:
                if row['id'] in seen:
                    raise ValueError('Catalogue returned a duplicate result during pagination')
                seen.add(row['id'])
                yield row, total
                if limit is not None and len(seen) >= limit:
                    return
            if len(seen) >= total:
                return
            if not page.pagination_action:
                raise ValueError('Catalogue did not provide a pagination form')
            page_number += 1
            fields = [(k, str(page_number) if k == 'trefferseite' else v) for k, v in page.pagination]
            html = self.request(urljoin(BASE + 'suche/', page.pagination_action), urlencode(fields).encode())

    def resolve(self, row):
        if not row['bestand'] or not row['bestand'].isdigit():
            raise ValueError(f"No collection identifier for result {row['id']}")
        query = urlencode({'id_titlaufn': row['id'], 'bestand': row['bestand']})
        page = self.request(BASE + 'olf/druckansicht.php?' + query)
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
    parser.add_argument('--list-only', action='store_true', help='list results without downloading')
    parser.add_argument('--limit', type=int, help='maximum number of results')
    parser.add_argument('--delay', type=float, default=3, help='seconds between requests (minimum 1; default 3)')
    args = parser.parse_args()
    phrase = args.query.strip()
    if phrase.startswith('"') and phrase.endswith('"'):
        phrase = phrase[1:-1].strip()
    if len(phrase) < 2 or '"' in phrase:
        parser.error('supply a phrase of at least two characters without embedded double quotes')
    if args.delay < 1 or not args.delay < float('inf'):
        parser.error('--delay must be at least 1 second')
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    client = Client(args.delay)
    count = total = 0
    try:
        for row, total in client.search(phrase, args.limit):
            url = client.resolve(row)
            count += 1
            print(f'{count}. {row["signature"]} | {row["date"]}\n   {url}', flush=True)
            if not args.list_only:
                client.wait()
                print(f'Downloading {url}', flush=True)
                command = [sys.executable, str(ROOT / 'scripts/downloader_universal.py'), url,
                    '--catalog-id', row['id'], '--bestand', row['bestand'], '--skip-existing',
                    '--delay', str(args.delay)]
                if row['has_viewer']:
                    command.append('--has-viewer')
                proc = subprocess.run(command, cwd=ROOT)
                client.last_request = time.monotonic()
                if proc.returncode:
                    raise RuntimeError(f'Downloader failed for {url}; stopping (exit {proc.returncode})')
        print(f'Listed {count} of {total} catalogue results' + (' (limited)' if count < total else ''), file=sys.stderr)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Error after {count} results: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
