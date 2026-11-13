#!/usr/bin/env python3
"""Find non-normalized personal names in English text in documents and books.

Examples:
    python3 scripts/linters/validate_english_names.py
    python3 scripts/linters/validate_english_names.py data/documents/1466-10-25.json

This tool normalizes unambiguous name variants in English text using
``data/names.md`` and ``data/places.json``.
"""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import sys

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_ROOT))

from given_names import name_groups
from place_names import resolve_place_names

ROOT = SCRIPTS_ROOT.parent


def load_variants():
    given_names = {}
    for forms, _ in name_groups((ROOT / 'data/names.md').read_text(encoding='utf-8')):
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
        rf'(?P<middle>(?:\s+(?:{given}))*)'
        rf'\s+(?P<connector>von|v\.|de)\s+'
        rf'(?P<surname>{surname})(?!\w)',
        re.IGNORECASE,
    )


def shared_suffix_pattern(given_names, surnames):
    """Match two coordinated given names sharing a recognized von-surname."""
    given = alternatives(given_names)
    surname = alternatives(surnames)
    return re.compile(
        rf'(?<!\w)(?P<first>{given})\s+and\s+(?P<second>{given})'
        rf'\s+(?P<connector>von|v\.)\s+(?P<place>{surname})(?!\w)',
        re.IGNORECASE,
    )


def expand_shared_suffix(match, given_names, surnames):
    first = given_names[match.group('first').casefold()]
    second = given_names[match.group('second').casefold()]
    place = surnames[match.group('place').casefold()]
    return f'{first} von {place} and {second} von {place}'


def suggested_name(match, given_names, surnames):
    given = given_names[match.group('given').casefold()]
    middle = match.group('middle')
    middle = ''.join(' ' + given_names[word.casefold()] for word in middle.split())
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
    shared_pattern = shared_suffix_pattern(given_names, surnames)
    findings = 0

    for path in collect_files(args.paths or [ROOT / 'data/documents', ROOT / 'data/books']):
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError) as exc:
            print(f'{path}: error: cannot read JSON: {exc}')
            findings += 1
            continue

        changed = False

        def visit(value, location):
            nonlocal findings, changed
            if isinstance(value, dict):
                for key, child in value.items():
                    child_location = f'{location}/{key.replace("~", "~0").replace("/", "~1")}'
                    if key == 'english' and isinstance(child, str):
                        def expand_shared(match):
                            nonlocal findings, changed
                            expanded = expand_shared_suffix(match, given_names, surnames)
                            original = match.group(0)
                            if original != expanded:
                                print(f'{path}#{child_location}: fixed: {original!r} -> {expanded!r}')
                                findings += 1
                                changed = True
                            return expanded

                        child = shared_pattern.sub(expand_shared, child)

                        def normalize(match):
                            nonlocal findings, changed
                            suggested = suggested_name(match, given_names, surnames)
                            original = match.group(0)
                            if original != suggested:
                                print(f'{path}#{child_location}: fixed: {original!r} -> {suggested!r}')
                                findings += 1
                                changed = True
                            return suggested

                        value[key] = pattern.sub(normalize, child)
                    else:
                        visit(child, child_location)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, f'{location}/{index}')

        visit(document, '')
        if changed:
            original = path.read_text(encoding='utf-8')
            trailing_newline = original.endswith('\n')
            updated = json.dumps(document, ensure_ascii=False, indent=2)
            if trailing_newline:
                updated += '\n'
            path.write_text(updated, encoding='utf-8')

    print(f'Normalized {findings} English name form(s).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
