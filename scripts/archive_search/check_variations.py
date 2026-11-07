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
    def __init__(self, archive, cache_dir=None, results_file=None, skip_result_ids=(), resume_after_result_id=None):
        self.archive = archive
        self.cache_dir = cache_dir
        self.results_file = results_file
        self.skip_result_ids = skip_result_ids
        self.resume_after_result_id = resume_after_result_id
        self.last_finished = None
        self.answers = {}
        self.failed = []
        results_path = results_file or ROOT / 'data/archive_search' / f'{archive}.json'
        if results_path.exists():
            saved = json.loads(results_path.read_text(encoding='utf-8'))
            if saved.get('archive') == archive and isinstance(saved.get('queries'), dict):
                self.answers.update({query: answer for query, answer in saved['queries'].items()
                                     if isinstance(query, str) and isinstance(answer, bool)})

    def run(self, query, exists=False):
        # Some archive clients keep rate-limit timestamps only in their process.
        if self.last_finished is not None and self.archive not in CACHE_ARCHIVES:
            time.sleep(max(0, 15 - (time.monotonic() - self.last_finished)))
        command = [sys.executable, str(SCRIPTS[self.archive]), query]
        if exists:
            command.append('--exists')
        else:
            command.append('--skip-existing')
            for result_id in self.skip_result_ids:
                command.extend(['--skip-result-id', result_id])
            if self.resume_after_result_id:
                command.extend(['--resume-after-result-id', self.resume_after_result_id])
                self.resume_after_result_id = None
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
    parser.add_argument('name', help='optional name or title followed by von or zu and a place')
    parser.add_argument('--cache-dir', type=Path, help='archive search cache directory (where supported)')
    parser.add_argument('--results-file', type=Path,
                        help='JSON file for verified existence results')
    parser.add_argument('--skip-result-id', action='append', default=[],
                        help='skip this catalogue result when importing (Landesarchiv BW only; repeatable)')
    parser.add_argument('--resume-after-result-id',
                        help='resume the first Landesarchiv BW import after this result ID')
    parser.add_argument('--exists-only', action='store_true',
                        help='check surviving full queries for results without listing or importing records')
    args = parser.parse_args()
    if args.cache_dir is not None and args.archive not in CACHE_ARCHIVES:
        parser.error(f'{args.archive} does not support --cache-dir')
    if args.skip_result_id and args.archive != 'landesarchiv_bw':
        parser.error('--skip-result-id is supported only for landesarchiv_bw')
    if args.resume_after_result_id and args.archive != 'landesarchiv_bw':
        parser.error('--resume-after-result-id is supported only for landesarchiv_bw')
    match = re.fullmatch(r'(?:(.+?)\s+)?(von|zu)\s+(.+)', args.name.strip(), flags=re.IGNORECASE)
    if not match:
        parser.error('supply von or zu and a place, optionally preceded by a name or title')
    preceding, particle, surname = match.groups()
    preceding = preceding or ''
    try:
        surnames = surname_variants(surname, ROOT / 'data/places.json')
        whole_title = title_variants(preceding, ROOT / 'data/titles.md')
        title_groups = [title_variants(word, ROOT / 'data/titles.md') for word in preceding.split()]
        only_titles = bool(whole_title) or (bool(title_groups) and all(title_groups))
        names = ([whole_title] if whole_title else
                 [title or name_variants(word, ROOT / 'data/names.md')
                  for word, title in zip(preceding.split(), title_groups)])
        prefixes = (*PREFIXES[:-1], 'zu', 'des', '') if only_titles else PREFIXES
        checker = Checker(args.archive, args.cache_dir, args.results_file, args.skip_result_id,
                          args.resume_after_result_id)
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
            if args.exists_only:
                print(f'{query}\t{str(checker.exists(query)).lower()}')
            else:
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
