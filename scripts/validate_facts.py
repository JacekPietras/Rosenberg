#!/usr/bin/env python3
"""Migrate von und zu names and check typed facts and guesses.

Examples:
    python3 scripts/validate_facts.py
    python3 scripts/validate_facts.py data/documents/1397-04-29.json
    python3 scripts/validate_facts.py data/books data/notes

The source assertion schema is in rules/json-formats.md. This script does
not verify source support or historical identity and does not build a graph.
Every assertion must be typed. Books and notes require explicit historical dates.
"""

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import re
from place_names import resolve_place_names

ROOT = Path(__file__).resolve().parents[1]
RELATIONS = frozenset({'parent', 'sibling', 'spouse', 'kin'})
TYPES = RELATIONS | {'title', 'death', 'generic'}
MISSING = object()
DATE_PATTERN = re.compile(r'[0-9]{4}(?:-[0-9]{2}(?:-[0-9]{2})?)?\Z')


@dataclass(frozen=True, order=True)
class Diagnostic:
    location: str
    severity: str
    message: str

    def __str__(self):
        return f'{self.location}: {self.severity}: {self.message}'


def date_bounds(value):
    """Validate ISO precision and return comparison bounds without changing it."""
    if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
        raise ValueError('expected YYYY, YYYY-MM, or YYYY-MM-DD')
    parts = [int(part) for part in value.split('-')]
    year, month, day = (parts + [1, 1])[:3]
    start = date(year, month, day)
    if len(parts) == 1:
        end = date(year, 12, 31)
    elif len(parts) == 2:
        import calendar
        end = date(year, month, calendar.monthrange(year, month)[1])
    else:
        end = start
    return start, end


def inherited_date_bounds(value):
    """Also accept existing document intervals, without inventing a single day."""
    if isinstance(value, str):
        if '/' in value:
            endpoints = value.split('/')
        elif '--' in value:
            endpoints = value.split('--')
        elif re.fullmatch(r'[0-9]{4}-[0-9]{4}', value):
            endpoints = value.split('-')
        else:
            return date_bounds(value)
        if len(endpoints) != 2:
            raise ValueError('expected two interval endpoints')
        start, _ = date_bounds(endpoints[0])
        _, end = date_bounds(endpoints[1])
        if start > end:
            raise ValueError('interval starts after it ends')
        return start, end
    return date_bounds(value)


class Validator:
    def __init__(self, strict_migration=False, root=ROOT):
        self.strict_migration = strict_migration
        self.root = Path(root)
        self.diagnostics = []
        self.counts = Counter()
        self.person_ids = set()
        self.person_names = set()
        self.people_by_id = {}
        self.given_name_variants = {}
        self.place_name_variants = {}
        self.load_name_variants()

    def report(self, location, message, severity='error'):
        location = str(location)
        repository_prefix = str(self.root.resolve()) + '/'
        if location.startswith(repository_prefix):
            location = '/' + location[len(repository_prefix):]
        self.diagnostics.append(Diagnostic(location, severity, message))

    def read_json(self, path):
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError) as exc:
            self.report(path, f'cannot read JSON: {exc}')
            return MISSING

    @staticmethod
    def nonblank(value):
        return isinstance(value, str) and bool(value.strip())

    def load_name_variants(self):
        names_path = self.root / 'data/names.md'
        try:
            for line in names_path.read_text(encoding='utf-8').splitlines():
                line = line.split('//', 1)[0]
                forms = [form.strip() for form in line.split(',') if form.strip()]
                if forms:
                    for form in forms:
                        self.given_name_variants[form.casefold()] = forms[0]
            places = json.loads((self.root / 'data/places.json').read_text(encoding='utf-8'))
            for place in resolve_place_names(places):
                variations = place.get('variations', [])
                if variations:
                    for form in variations:
                        self.place_name_variants[form.casefold()] = variations[0]
        except (OSError, UnicodeError, ValueError, KeyError) as exc:
            self.report(names_path, f'cannot load name/place variations: {exc}')

    def load_people(self, path):
        people = self.read_json(path)
        if people is MISSING:
            return
        if not isinstance(people, list):
            self.report(path, 'person registry must be an array')
            return
        for index, person in enumerate(people):
            loc = f'{path}#/{index}'
            if not isinstance(person, dict):
                self.report(loc, 'person record must be an object')
                continue
            for field in sorted(set(person) - {'id', 'name'}):
                self.report(loc + '/' + field, 'confirmed people support only id and name; calculated data belongs in tree.json')
            if 'id' not in person:
                self.report(loc + '/id', 'confirmed people require an ID')
            name = person.get('name')
            if not self.nonblank(name):
                self.report(loc + '/name', 'expected a non-empty name string')
            else:
                self.person_names.add(name)
            if 'id' in person:
                person_id = person['id']
                if not self.nonblank(person_id):
                    self.report(loc + '/id', 'expected a non-empty ID string')
                elif person_id in self.person_ids:
                    self.report(loc + '/id', f'duplicate person ID {person_id!r}')
                else:
                    self.person_ids.add(person_id)
                    if self.nonblank(name):
                        self.people_by_id[person_id] = name
        for collision in sorted(self.person_ids & self.person_names):
            self.report(path, f'person ID collides with full name {collision!r}')

    def check_date(self, value, location, inherited=False):
        if value is MISSING:
            self.report(location, 'missing historical date; supply a valid historical date')
        elif value is None:
            self.report(location, 'null dates are not supported; omit unnecessary date fields or supply a valid historical date')
        else:
            try:
                (inherited_date_bounds if inherited else date_bounds)(value)
            except ValueError as exc:
                self.report(location, f'invalid date {value!r}: {exc}')

    def check_person(self, value, location):
        if not self.nonblank(value):
            self.report(location, 'expected a non-empty person ID or name string')
        elif value not in self.person_ids:
            if '_' in value:
                self.report(location, f'unknown person ID {value!r}; IDs must exist in people.json', 'warning')
                return
            valid_shape = (
                re.fullmatch(r'\S+(?:\s+\S+)?', value)
                or re.fullmatch(r'\S+(?:\s+\S+)*\s+von\s+\S+(?:\s+\S+)*', value)
                or value in self.person_names
            )
            if not valid_shape:
                self.report(
                    location,
                    'person name must be a name, a name followed by a surname, or a name followed by "von" and a surname; '
                    'move additional designations to personTitle/ofTitle, or leave the name for manual review and verification',
                )
                return
            parts = value.split()
            given = parts[0]
            given_canonical = self.given_name_variants.get(given.casefold())
            if given_canonical and given != given_canonical:
                self.report(location, f'given name {given!r} is a variation; use normalized form {given_canonical!r} from data/names.md')
            if 'von' in [part.casefold() for part in parts]:
                von_index = next(index for index, part in enumerate(parts) if part.casefold() == 'von')
                surname_parts = parts[von_index + 1:]
            else:
                surname_parts = parts[1:]
            if surname_parts:
                surname = ' '.join(surname_parts)
                surname_canonical = self.place_name_variants.get(surname.casefold())
                if surname_canonical and surname != surname_canonical:
                    self.report(location, f'surname {surname!r} is a place-name variation; use normalized form {surname_canonical!r} from data/places.json')

    def check_titles(self, value, location):
        if not isinstance(value, list) or not value:
            self.report(location, 'expected a non-empty array of unique non-empty title strings; omit absent titles')
            return
        seen = set()
        for index, item in enumerate(value):
            if not self.nonblank(item):
                self.report(f'{location}/{index}', 'expected a non-empty title string')
            elif item in seen:
                self.report(f'{location}/{index}', f'duplicate title {item!r}')
            else:
                seen.add(item)

    def check_text_person_references(self, text, location):
        for match in re.finditer(r'\[([^\[\]]+)\]', text):
            person_id = match.group(1)
            name = self.people_by_id.get(person_id)
            if not name:
                continue
            given, *rest = name.split()
            canonical = self.given_name_variants.get(given.casefold(), given).casefold()
            variants = {given.casefold()} | {
                form for form, standard in self.given_name_variants.items()
                if standard.casefold() == canonical
            }
            suffix = r'\s+'.join(re.escape(part) for part in rest)
            for variant in variants:
                pattern = r'(?<!\w)' + re.escape(variant)
                if suffix:
                    pattern += r'\s+' + suffix
                if re.search(pattern + r'\s*$', text[:match.start()], re.IGNORECASE):
                    self.report(location, f'person name duplicates [{person_id}]; use the bracketed ID alone')
                    break

    def check_fact(self, fact, location, require_date, explicit_date_required,
                   inherited, document_source=False, guess=False):
        self.counts['guesses' if guess else 'facts'] += 1
        if not isinstance(fact, dict):
            self.report(location, 'fact or guess must be a typed object')
            return
        typed = 'type' in fact
        if not typed:
            self.report(location + '/type', 'required field is missing; use a supported typed object')
            return
        if not guess:
            self.counts['typed'] += 1
        if typed:
            kind = fact['type']
            if not isinstance(kind, str) or kind not in TYPES:
                self.report(location + '/type', f'unsupported type {kind!r}; allowed: {", ".join(sorted(TYPES))}')
                return
            allowed = {'type', 'person', 'date', 'personTitle'}
            required = {'person'}
            if kind in RELATIONS:
                allowed |= {'of', 'ofTitle', 'personDeceased', 'ofDeceased'}
                required.add('of')
            elif kind == 'title':
                allowed.add('personDeceased')
                required.add('personTitle')
            elif kind == 'generic':
                allowed |= {'content', 'personDeceased', 'subject'}
                required.discard('person')
                if ('person' in fact) == ('subject' in fact):
                    self.report(location, 'generic facts require exactly one of person or subject')
                if 'subject' in fact:
                    allowed -= {'personTitle', 'personDeceased'}
                    if not self.nonblank(fact['subject']):
                        self.report(location + '/subject', 'expected a non-empty non-person subject string')
                required.add('content')
                if 'content' in fact:
                    if not self.nonblank(fact['content']):
                        self.report(location + '/content', 'expected a non-empty content string')
                    else:
                        self.check_text_person_references(fact['content'], location + '/content')
            elif kind == 'death':
                allowed |= {'diedOn', 'diedBefore', 'circumstances'}
                death_fields = {'diedOn', 'diedBefore'} & set(fact)
                if len(death_fields) != 1:
                    self.report(location, "death facts require exactly one of 'diedOn' or 'diedBefore'")
                for field in ('diedOn', 'diedBefore'):
                    if field in fact:
                        self.check_date(fact[field], location + '/' + field)
                if 'circumstances' in fact and not self.nonblank(fact['circumstances']):
                    self.report(location + '/circumstances', 'expected a non-empty circumstances string')
            if kind == 'kin':
                allowed.add('term')
                required.add('term')
            for field in sorted(set(fact) - allowed):
                self.report(location + '/' + field, f'field is not supported for {kind!r}')
            for field in sorted(required - set(fact)):
                self.report(location + '/' + field, 'required field is missing')
            for field in ('person', 'of'):
                if field in fact and field in allowed:
                    self.check_person(fact[field], location + '/' + field)
            for field in ('personTitle', 'ofTitle'):
                if field in fact and field in allowed:
                    self.check_titles(fact[field], location + '/' + field)
            for field in ('personDeceased', 'ofDeceased'):
                if field in fact and (field not in allowed or fact[field] is not True):
                    self.report(location + '/' + field, 'expected true when the source identifies this participant as deceased; otherwise omit the field')
            if kind == 'kin' and 'term' in fact and not self.nonblank(fact['term']):
                self.report(location + '/term', 'expected a non-empty kinship term string')
        if 'date' in fact:
            if document_source and kind == 'generic':
                self.report(location + '/date', 'generic document facts and guesses cannot have a date; inherit the enclosing date')
            elif document_source and inherited is not MISSING and fact['date'] == inherited:
                self.report(
                    location + '/date',
                    'redundant document date; omit this field to inherit the enclosing document or entry date',
                )
            self.check_date(fact['date'], location + '/date')
        elif require_date or explicit_date_required:
            self.report(location + '/date', 'books/notes facts and guesses require an explicit historical date')
        else:
            self.check_date(inherited, location + '/date (inherited)', inherited=True)

    def validate_file(self, path):
        document = self.read_json(path)
        if document is MISSING:
            return
        self.counts['files'] += 1
        # Generated tree data is validated by family_graph.export, not as
        # source assertions; its view names include facts and guesses.
        if path.name == 'people.json' and isinstance(document, list):
            return
        if path.resolve() == (self.root / 'data/tree.json').resolve():
            return
        is_book = 'books' in path.parts or (isinstance(document, dict) and 'book' in document)
        is_document = 'documents' in path.parts
        require_date = is_book or 'notes' in path.parts
        explicit_date_required = is_book or ('notes' in path.parts and self.strict_migration)

        def visit(value, location, inherited=MISSING):
            if isinstance(value, dict):
                current_date = value.get('date', inherited) if not require_date else MISSING
                for key in sorted(value):
                    child = value[key]
                    loc = location + '/' + key.replace('~', '~0').replace('/', '~1')
                    if key in ('facts', 'guesses'):
                        if not isinstance(child, list):
                            self.report(loc, f'{key} must be an array')
                        else:
                            for index, fact in enumerate(child):
                                self.check_fact(
                                    fact, f'{loc}/{index}', require_date,
                                    explicit_date_required, current_date,
                                    document_source=is_document,
                                    guess=key == 'guesses',
                                )
                    else:
                        visit(child, loc, current_date)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, f'{location}/{index}', inherited)
        visit(document, f'{path}#')


def collect_paths(paths, validator):
    files = set()
    for path in paths:
        if path.is_dir():
            files.update(item.resolve() for item in path.rglob('*.json') if item.is_file())
        elif path.is_file():
            files.add(path.resolve())
        else:
            validator.report(path, 'input path does not exist or is not a regular file/directory')
    return sorted(files)


def clean_facts(path, validator):
    if path.resolve() == (validator.root / 'data/tree.json').resolve():
        return
    original = path.read_text(encoding='utf-8')
    document = json.loads(original)

    def clean(value):
        if isinstance(value, dict):
            if value.get('facts') == []:
                del value['facts']
            for field in ('facts', 'guesses'):
                for fact in value.get(field, []) if isinstance(value.get(field), list) else []:
                    if isinstance(fact, dict):
                        order = ('subject', 'person', 'personTitle', 'personDeceased', 'type', 'of', 'ofTitle', 'ofDeceased')
                        reordered = {key: fact[key] for key in order if key in fact}
                        reordered.update((key, item) for key, item in fact.items() if key not in reordered and key != 'date')
                        if 'date' in fact:
                            reordered['date'] = fact['date']
                        fact.clear()
                        fact.update(reordered)
            for child in value.values():
                clean(child)
        elif isinstance(value, list):
            for child in value:
                clean(child)

    canonical = json.dumps(document, ensure_ascii=False, indent=2) + '\n'
    clean(document)
    updated = json.dumps(document, ensure_ascii=False, indent=2) + '\n'
    if updated != canonical:
        if original != canonical:
            validator.report(path, 'cannot clean facts in nonstandard JSON formatting')
        else:
            path.write_text(updated, encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('paths', nargs='*', type=Path, help='JSON files or directories (default: repository data/)')
    parser.add_argument('--people', type=Path, default=ROOT / 'data/people.json', help='person registry JSON')
    parser.add_argument('--strict-migration', action='store_true', help='compatibility option; all facts and guesses already require typed objects and historical dates')
    args = parser.parse_args(argv)
    validator = Validator(args.strict_migration)
    validator.load_people(args.people.resolve())
    # Report unreadable inputs before migration, which assumes parseable JSON.
    paths = [path for path in collect_paths(args.paths or [ROOT / 'data'], validator)
             if validator.read_json(path) is not MISSING]
    if paths:
        from migrate_von_und_zu import main as migrate_von_und_zu
        migrate_von_und_zu([*(str(path) for path in paths), '--apply'])
    for path in paths:
        clean_facts(path, validator)
        validator.validate_file(path)
    for diagnostic in sorted(validator.diagnostics):
        print(diagnostic)
    errors = sum(item.severity == 'error' for item in validator.diagnostics)
    warnings = len(validator.diagnostics) - errors
    c = validator.counts
    print(f'Checked {c["files"]} files, {c["facts"]} facts ({c["typed"]} typed), {c["guesses"]} guesses: {errors} errors, {warnings} warnings.')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
