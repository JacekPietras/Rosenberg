#!/usr/bin/env python3
"""Check name and surname variations and their full-person combinations."""
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
PREFIXES = ('von', 'v', 'v.', 'von.', 'de')


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

    def exists(self, query):
        if query in self.answers:
            return self.answers[query]
        # Some archive clients keep rate-limit timestamps only in their process.
        if self.last_finished is not None and self.archive not in CACHE_ARCHIVES:
            time.sleep(max(0, 15 - (time.monotonic() - self.last_finished)))
        command = [sys.executable, str(SCRIPTS[self.archive]), query, '--exists']
        if self.cache_dir is not None:
            command.extend(['--cache-dir', str(self.cache_dir)])
        if self.results_file is not None:
            command.extend(['--results-file', str(self.results_file)])
        print(f'Checking: {query}', file=sys.stderr, flush=True)
        result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE)
        self.last_finished = time.monotonic()
        if result.returncode:
            raise RuntimeError(f'Check failed for {query!r} (exit {result.returncode})')
        answer = result.stdout.strip()
        if answer not in ('true', 'false'):
            raise RuntimeError(f'Unexpected response for {query!r}: {answer!r}')
        found = answer == 'true'
        self.answers[query] = found
        return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', choices=SCRIPTS)
    parser.add_argument('name', help='full name in the form "given name von surname"')
    parser.add_argument('--cache-dir', type=Path, help='archive search cache directory (where supported)')
    parser.add_argument('--results-file', type=Path,
                        help='JSON file for verified existence results')
    args = parser.parse_args()
    if args.cache_dir is not None and args.archive not in CACHE_ARCHIVES:
        parser.error(f'{args.archive} does not support --cache-dir')
    parts = re.split(r'\s+von\s+', args.name.strip(), flags=re.IGNORECASE)
    if len(parts) != 2 or not all(parts):
        parser.error('supply a full name in the form "given name von surname"')
    given_names, surname = parts[0].split(), parts[1]
    try:
        surnames = surname_variants(surname, ROOT / 'data/places.json')
        names = [name_variants(name, ROOT / 'data/names.md') for name in given_names]
        checker = Checker(args.archive, args.cache_dir, args.results_file)
        surnames = [variant for variant in surnames if checker.exists(variant)]
        if not surnames:
            return 0
        prefixed_surnames = [f'{prefix} {family}' for family in surnames for prefix in PREFIXES
                             if checker.exists(f'{prefix} {family}')]
        if not prefixed_surnames:
            return 0
        surviving_names = []
        for variants in names:
            found = [variant for variant in variants if checker.exists(variant)]
            if not found:
                return 0
            surviving_names.append(found)
        for given, family in itertools.product(itertools.product(*surviving_names), prefixed_surnames):
            query = ' '.join((*given, family))
            answer = checker.exists(query)
            print(f'{query}\t{str(answer).lower()}', flush=True)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Error: {exc}; stopping', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
