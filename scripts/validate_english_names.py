#!/usr/bin/env python3
"""Find non-normalized personal names in English text in documents and books.

Examples:
    python3 scripts/validate_english_names.py
    python3 scripts/validate_english_names.py data/documents/1466-10-25.json

This read-only review tool reports name forms to check; it does not edit JSON.
"""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re

from place_names import resolve_place_names

ROOT = Path(__file__).resolve().parents[1]


def load_variants():
    given_names = {}
    for line in (ROOT / 'data/names.md').read_text(encoding='utf-8').splitlines():
        forms = [part.strip() for part in line.split('//', 1)[0].split(',') if part.strip()]
        if forms:
            for form in forms:
                given_names[form.casefold()] = forms[0]

    places = json.loads((ROOT / 'data/places.json').read_text(encoding='utf-8'))
    place_forms = defaultdict(set)
    canonical_places = set()
    for place in resolve_place_names(places):
        if place.get('category') == 'church':
            continue
        forms = place.get('variations', [])
        if forms:
            canonical_places.add(forms[0].casefold())
            for form in forms:
                place_forms[form.casefold()].add(forms[0])
    # Preserve each record's first variation as canonical even if another
    # record happens to list that spelling as an alias. Ambiguous aliases are
    # omitted so they do not produce an arbitrary normalization suggestion.
    surnames = {
        form: next(iter(canonicals))
        for form, canonicals in place_forms.items()
        if len(canonicals) == 1 and form not in canonical_places
    }
    for place in resolve_place_names(places):
        if place.get('category') == 'church':
            continue
        forms = place.get('variations', [])
        if forms:
            surnames[forms[0].casefold()] = forms[0]
    return given_names, surnames


def alternatives(values):
    return '|'.join(re.escape(value) for value in sorted(values, key=len, reverse=True))


def name_pattern(given_names, surnames):
    given = alternatives(given_names)
    surname = alternatives(surnames)
    return re.compile(
        rf'(?<!\w)(?P<given>{given})'
        rf'(?:\s+(?P<middle>{given}))?'
        rf'\s+(?P<connector>von|v\.|de)\s+'
        rf'(?P<surname>{surname})(?!\w)',
        re.IGNORECASE,
    )


def suggested_name(match, given_names, surnames):
    given = given_names[match.group('given').casefold()]
    middle = match.group('middle')
    middle = ' ' + given_names[middle.casefold()] if middle else ''
    surname = surnames[match.group('surname').casefold()]
    return f'{given}{middle} von {surname}'


def collect_files(paths):
    files = set()
    for path in paths:
        if path.is_dir():
            files.update(item.resolve() for item in path.rglob('*.json') if item.is_file())
        elif path.is_file():
            files.add(path.resolve())
        else:
            print(f'{path}: error: input path does not exist or is not a file/directory')
    return sorted(files)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'paths', nargs='*', type=Path,
        help='JSON files or directories (default: data/documents and data/books)',
    )
    args = parser.parse_args(argv)
    given_names, surnames = load_variants()
    pattern = name_pattern(given_names, surnames)
    findings = 0

    for path in collect_files(args.paths or [ROOT / 'data/documents', ROOT / 'data/books']):
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError) as exc:
            print(f'{path}: error: cannot read JSON: {exc}')
            findings += 1
            continue

        def visit(value, location):
            nonlocal findings
            if isinstance(value, dict):
                for key, child in value.items():
                    child_location = f'{location}/{key.replace("~", "~0").replace("/", "~1")}'
                    if key == 'english' and isinstance(child, str):
                        for match in pattern.finditer(child):
                            suggested = suggested_name(match, given_names, surnames)
                            original = match.group(0)
                            if original != suggested:
                                print(f'{path}#{child_location}: review: {original!r} -> {suggested!r}')
                                findings += 1
                    else:
                        visit(child, child_location)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, f'{location}/{index}')

        visit(document, '')

    print(f'Checked English name forms: {findings} finding(s).')
    return 1 if findings else 0


if __name__ == '__main__':
    raise SystemExit(main())
