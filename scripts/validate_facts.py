#!/usr/bin/env python3
"""Read-only syntax checks for the proposed typed facts and legacy facts.

Examples:
    python3 scripts/validate_facts.py
    python3 scripts/validate_facts.py data/documents/1397-04-29.json
    python3 scripts/validate_facts.py --strict-migration data/books data/notes

The source assertion schema is in rules/json-formats.md. This script does
not verify source support or historical identity and does not build a graph.
Legacy strings and text objects remain accepted by default outside books.
Book facts and guesses always require explicit historical dates. Strict
migration also requires date-bearing objects for all facts and guesses in
notes, including free text.
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
TYPES = RELATIONS | {'title', 'death'}
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
        self.diagnostics.append(Diagnostic(str(location), severity, message))

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
        if isinstance(fact, str):
            self.check_text_person_references(fact, location)
            if not guess:
                self.counts['legacy'] += 1
            if not self.nonblank(fact):
                self.report(location, 'fact text must not be empty')
            if guess:
                if explicit_date_required:
                    self.report(location, 'this source requires guesses to be objects with an explicit historical date')
                else:
                    self.report(location, 'undated legacy guess requires historical date review', 'warning')
            elif explicit_date_required:
                self.report(location, 'this source requires facts to be objects with an explicit historical date')
            elif require_date and self.strict_migration:
                self.report(location, 'books/notes facts require an object with an explicit date in strict migration mode')
            return
        if not isinstance(fact, dict):
            self.report(location, 'fact must be a string or object')
            return
        typed = 'type' in fact
        if not guess:
            self.counts['typed' if typed else 'legacy'] += 1
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
        else:
            for field in sorted(set(fact) - {'date', 'text'}):
                self.report(location + '/' + field, 'legacy text facts support only date and text')
            if not self.nonblank(fact.get('text')):
                self.report(location + '/text', 'expected non-empty legacy fact text')
            else:
                self.check_text_person_references(fact['text'], location + '/text')
        if 'date' in fact:
            if document_source and inherited is not MISSING and fact['date'] == inherited:
                self.report(
                    location + '/date',
                    'redundant document date; omit this field to inherit the enclosing document or entry date',
                )
            self.check_date(fact['date'], location + '/date')
        elif guess and explicit_date_required:
            self.report(location + '/date', 'guesses require an explicit historical date')
        elif guess and document_source and typed:
            self.check_date(inherited, location + '/date (inherited)', inherited=True)
        elif guess:
            self.report(location + '/date', 'undated legacy guess requires historical date review', 'warning')
        elif explicit_date_required or (require_date and (typed or self.strict_migration)):
            self.report(location + '/date', 'books/notes facts require an explicit historical date')
        elif typed:
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('paths', nargs='*', type=Path, help='JSON files or directories (default: repository data/)')
    parser.add_argument('--people', type=Path, default=ROOT / 'data/people.json', help='person registry JSON')
    parser.add_argument('--strict-migration', action='store_true', help='also require explicit date-bearing objects for all notes facts')
    args = parser.parse_args(argv)
    validator = Validator(args.strict_migration)
    validator.load_people(args.people.resolve())
    for path in collect_paths(args.paths or [ROOT / 'data'], validator):
        validator.validate_file(path)
    for diagnostic in sorted(validator.diagnostics):
        print(diagnostic)
    errors = sum(item.severity == 'error' for item in validator.diagnostics)
    warnings = len(validator.diagnostics) - errors
    c = validator.counts
    print(f'Checked {c["files"]} files, {c["facts"]} facts ({c["typed"]} typed, {c["legacy"]} legacy), {c["guesses"]} guesses: {errors} errors, {warnings} warnings.')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
