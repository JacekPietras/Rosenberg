"""Read each source assertion once, with its complete inherited context."""

import json
from pathlib import Path
from validate_facts import TYPES, Validator
from .dates import date_bounds, inherited_date_bounds
from .model import Assertion, Inputs, Mention, SourceRef, fingerprint
from .probability import Observation, parameters

SOURCE_DIRS = ('books', 'documents', 'notes', 'images')


def identities(people):
    return [{key: person[key] for key in ('id', 'name') if key in person} for person in people]


def source_paths(root):
    return sorted(path for folder in SOURCE_DIRS for path in (root / 'data' / folder).rglob('*.json') if path.is_file())


def input_manifest(root, people=None):
    paths = source_paths(root) + [root / 'data/names.md', root / 'data/titles.md', root / 'data/kinship.md', root / 'data/places.json', root / 'data/matching.json']
    manifest = {}
    for path in sorted(set(paths)):
        if not path.exists():
            continue  # A small synthetic repository may omit optional data files.
        text = path.read_text(encoding='utf-8')
        try:
            value = json.loads(text) if path.suffix == '.json' else text
        except ValueError as exc:
            raise ValueError(f'{path}: {exc}') from exc
        manifest[path.relative_to(root).as_posix()] = fingerprint(value)
    if people is None:
        people = json.loads((root / 'data/people.json').read_text(encoding='utf-8'))
    manifest['data/people.json'] = fingerprint(identities(people))
    return dict(sorted(manifest.items()))


def walk_assertions(document, path, include_text=False):
    explicit = path.startswith(('data/books/', 'data/notes/')) or isinstance(document, dict) and 'book' in document

    def visit(value, pointer='', inherited='', context=None):
        if isinstance(value, dict):
            current_date = '' if explicit else value.get('date', inherited)
            current_context = {**(context or {}), **{k: value[k] for k in ('source', 'url', 'book', 'title', 'place') if k in value}}
            for key, child in value.items():
                location = pointer + '/' + key.replace('~', '~0').replace('/', '~1')
                if key in ('facts', 'guesses'):
                    if not isinstance(child, list):
                        raise ValueError(f'{path}#{location}: expected an array')
                    for index, fact in enumerate(child):
                        ref = SourceRef(path, f'{location}/{index}', fingerprint(fact), key,
                                        json.dumps(current_context.get('source', current_context.get('book', '')), ensure_ascii=False, sort_keys=True))
                        if not isinstance(fact, dict) or 'type' not in fact:
                            text = fact if isinstance(fact, str) else fact.get('text', '') if isinstance(fact, dict) else ''
                            historical_date = fact.get('date', current_date) if isinstance(fact, dict) else current_date
                            try:
                                bounds = inherited_date_bounds(historical_date)
                            except (ValueError, TypeError):
                                bounds = None
                            yield ref, Observation(ref, text, historical_date, bounds, current_context) if include_text else None
                            continue
                        if fact['type'] not in TYPES:
                            raise ValueError(f'{ref.key}: unsupported assertion type')
                        historical_date = fact.get('date', current_date)
                        try:
                            bounds = (date_bounds if 'date' in fact else inherited_date_bounds)(historical_date)
                        except (ValueError, TypeError) as exc:
                            raise ValueError(f'{ref.key}: invalid or missing historical date: {exc}') from exc
                        assertion = Assertion(ref, fact, historical_date, bounds, current_context)
                        for field in ('person', 'of'):
                            if field in fact:
                                assertion.mentions.append(Mention(ref.key + '/' + field, fact[field], field,
                                    tuple(fact.get(field + 'Title', [])), fact.get(field + 'Deceased') is True, assertion))
                        yield ref, assertion
                else:
                    yield from visit(child, location, current_date, current_context)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from visit(child, f'{pointer}/{index}', inherited, context)

    yield from visit(document)


def load_inputs(root, validate=True):
    root = Path(root).resolve()
    initial_manifest = input_manifest(root)
    registry_bytes = (root / 'data/people.json').read_bytes()
    tree_path = root / 'data/tree.json'
    tree_bytes = tree_path.read_bytes() if tree_path.exists() else None
    people = json.loads(registry_bytes)
    if not isinstance(people, list) or not people:
        raise ValueError('people.json must be a non-empty array')
    ids = [person['id'] for person in people if person.get('id')]
    if len(ids) != len(set(ids)) or set(ids) & {person['name'] for person in people}:
        raise ValueError('duplicate IDs or ID/name collisions in people.json')
    validator = Validator(root=root)
    if validate:
        validator.load_people(root / 'data/people.json')
    assertions, observations, prose = [], [], {'facts': 0, 'guesses': 0}
    for path in source_paths(root):
        if validate:
            validator.validate_file(path)
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError) as exc:
            raise ValueError(f'{path}: {exc}') from exc
        for ref, assertion in walk_assertions(document, path.relative_to(root).as_posix(), include_text=True):
            if isinstance(assertion, Assertion):
                assertions.append(assertion)
            else:
                observations.append(assertion)
                prose[ref.kind] += 1
    errors = [str(item) for item in validator.diagnostics if item.severity == 'error']
    if errors:
        raise ValueError('\n'.join(errors))
    names = (root / 'data/names.md').read_text(encoding='utf-8')
    titles_path = root / 'data/titles.md'
    titles = titles_path.read_text(encoding='utf-8') if titles_path.exists() else ''
    kinship_path = root / 'data/kinship.md'
    kinship = kinship_path.read_text(encoding='utf-8') if kinship_path.exists() else ''
    places = json.loads((root / 'data/places.json').read_text(encoding='utf-8'))
    matching_path = root / 'data/matching.json'
    if validate and not matching_path.exists():
        raise ValueError('data/matching.json: global probability configuration is missing')
    matching = parameters(json.loads(matching_path.read_text(encoding='utf-8')) if matching_path.exists() else None)
    manifest = input_manifest(root, people)
    # Refuse a mixed snapshot if a file changed during ingestion.
    if manifest != initial_manifest or registry_bytes != (root / 'data/people.json').read_bytes():
        raise ValueError('inputs changed during ingestion; rerun reconstruction')
    return Inputs(root, people, names, places, assertions, manifest, prose, registry_bytes, tree_bytes, matching, observations, titles, kinship)
