#!/usr/bin/env python3
"""Screen name variations and search archives for surviving combinations."""
from __future__ import annotations

import argparse
import itertools
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from place_names import resolve_place_names

SCRIPTS = {name: Path(__file__).with_name(f'search_{name}.py') for name in (
    'monasterium', 'arcinsys_hessen', 'gda_bayern', 'landesarchiv_bw',
    'landesarchiv_nrw', 'regesta_imperii',
)}
CACHE_ARCHIVES = {'monasterium', 'gda_bayern', 'landesarchiv_nrw', 'regesta_imperii'}
PREFIXES = ('von', 'v', 'v.', 'von.', 'de', '')


def unique(values):
    result, seen = [], set()
    for value in values:
        value = value.strip()
        if value and value.lower() not in seen:
            seen.add(value.lower())
            result.append(value)
    return result


def name_variants(name, names_file):
    for line in names_file.read_text(encoding='utf-8').splitlines():
        variants = unique(line.split(','))
        if any(name.casefold() == variant.casefold() for variant in variants):
            return unique([name, *variants])
    return [name]


def title_variants(title, titles_file):
    for line in titles_file.read_text(encoding='utf-8').splitlines():
        if line.lstrip().startswith('//'):
            continue
        variants = unique(line.split(','))
        if any(title.casefold() == variant.casefold() for variant in variants):
            return unique([title, *variants])
    return []


def surname_variants(surname, places_file):
    places = resolve_place_names(json.loads(places_file.read_text(encoding='utf-8')))
    matches = [place for place in places if place.get('category') != 'church'
               and any(surname.casefold() == v.casefold() for v in place.get('variations', []))]
    if len(matches) > 1:
        raise ValueError(f'Ambiguous place name {surname!r}; matches multiple places')
    return unique([surname, *matches[0]['variations']]) if matches else [surname]


class Checker:
    def __init__(self, archive, cache_dir=None, results_file=None):
        self.archive = archive
        self.cache_dir = cache_dir
        self.results_file = results_file
        self.last_finished = None
        self.answers = {}
        self.failed = []

    def run(self, query, exists=False):
        # Some archive clients keep rate-limit timestamps only in their process.
        if self.last_finished is not None and self.archive not in CACHE_ARCHIVES:
            time.sleep(max(0, 15 - (time.monotonic() - self.last_finished)))
        command = [sys.executable, str(SCRIPTS[self.archive]), query]
        if exists:
            command.append('--exists')
        if self.cache_dir is not None:
            command.extend(['--cache-dir', str(self.cache_dir)])
        if self.results_file is not None:
            command.extend(['--results-file', str(self.results_file)])
        print(f'{"Checking" if exists else "Searching"}: {query}', file=sys.stderr, flush=True)
        result = subprocess.run(command, cwd=ROOT, text=True,
                                stdout=subprocess.PIPE if exists else None)
        self.last_finished = time.monotonic()
        if result.returncode == 75 and self.archive == 'monasterium':
            self.failed.append(query)
            print(f'Monasterium returned HTTP 500 for {query!r}; continuing', file=sys.stderr)
            return True if exists else None
        if result.returncode:
            raise RuntimeError(f'Search failed for {query!r} (exit {result.returncode})')
        if not exists:
            return
        answer = result.stdout.strip()
        if answer not in ('true', 'false'):
            raise RuntimeError(f'Unexpected response for {query!r}: {answer!r}')
        found = answer == 'true'
        return found

    def exists(self, query):
        if query not in self.answers:
            self.answers[query] = self.run(query, exists=True)
        return self.answers[query]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', choices=SCRIPTS)
    parser.add_argument('name', help='name or title followed by von or zu and a place')
    parser.add_argument('--cache-dir', type=Path, help='archive search cache directory (where supported)')
    parser.add_argument('--results-file', type=Path,
                        help='JSON file for verified existence results')
    args = parser.parse_args()
    if args.cache_dir is not None and args.archive not in CACHE_ARCHIVES:
        parser.error(f'{args.archive} does not support --cache-dir')
    parts = re.split(r'\s+(von|zu)\s+', args.name.strip(), flags=re.IGNORECASE)
    if len(parts) != 3 or not parts[0] or not parts[2]:
        parser.error('supply a name or title followed by von or zu and a place')
    preceding, particle, surname = parts
    try:
        surnames = surname_variants(surname, ROOT / 'data/places.json')
        whole_title = title_variants(preceding, ROOT / 'data/titles.md')
        title_groups = [title_variants(word, ROOT / 'data/titles.md') for word in preceding.split()]
        only_titles = bool(whole_title) or all(title_groups)
        names = ([whole_title] if whole_title else
                 [title or name_variants(word, ROOT / 'data/names.md')
                  for word, title in zip(preceding.split(), title_groups)])
        prefixes = (*PREFIXES[:-1], 'zu', 'des', '') if only_titles else PREFIXES
        checker = Checker(args.archive, args.cache_dir, args.results_file)
        surnames = [variant for variant in surnames if checker.exists(variant)]
        if not surnames:
            return 1 if checker.failed else 0
        prefixed_surnames = [f'{prefix} {family}' if prefix else family
                             for family in surnames for prefix in prefixes
                             if not prefix or checker.exists(f'{prefix} {family}')]
        if not prefixed_surnames:
            return 0
        surviving_names = []
        for variants in names:
            found = [variant for variant in variants if checker.exists(variant)]
            if not found:
                if checker.failed:
                    print('Incomplete checks (HTTP 500): ' + ', '.join(repr(q) for q in checker.failed), file=sys.stderr)
                return 1 if checker.failed else 0
            surviving_names.append(found)
        for given, family in itertools.product(itertools.product(*surviving_names), prefixed_surnames):
            query = ' '.join((*given, family))
            checker.run(query)
        if checker.failed:
            print('Incomplete searches (HTTP 500): ' + ', '.join(repr(q) for q in checker.failed), file=sys.stderr)
            return 1
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Error: {exc}; stopping', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
