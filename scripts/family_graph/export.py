"""Validate a complete replacement in memory, then write the registry once."""

from collections import Counter
from copy import deepcopy
import json
import re
from .constraints import cycle_nodes
from .model import fingerprint, registry_keys
from .policy import ENGINE_VERSION, POLICY_VERSION
from .sources import identities, input_manifest


def resolve_pointer(value, pointer):
    if not pointer.startswith('/'):
        raise ValueError('expected an absolute JSON Pointer')
    for token in pointer[1:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def pack_evidence(graph):
    result = deepcopy({key: graph[key] for key in ('nodes', 'relationships')})
    refs = {}
    for node in result['nodes']:
        for ref in [*(m['source'] for m in node['mentions']), *node['identitySources']]:
            refs[(ref['path'], ref['pointer'], ref['fingerprint'])] = ref
    for edge in result['relationships']:
        for d in edge['derivations']:
            for ref in d['sources']:
                refs[(ref['path'], ref['pointer'], ref['fingerprint'])] = ref
    ordered = sorted(refs)
    index = {key: i for i, key in enumerate(ordered)}
    def number(ref):
        return index[(ref['path'], ref['pointer'], ref['fingerprint'])]
    for node in result['nodes']:
        for mention in node['mentions']:
            mention['source'] = number(mention['source'])
        node['identitySources'] = [number(ref) for ref in node['identitySources']]
    for edge in result['relationships']:
        for d in edge['derivations']:
            d['sources'] = [number(ref) for ref in d['sources']]
    return {'sources': [refs[key] for key in ordered], **result}


def unpack_evidence(graph):
    if 'sources' not in graph:
        return graph
    if set(graph) != {'sources', 'nodes', 'relationships'} or not isinstance(graph['sources'], list):
        raise ValueError('invalid reconstructed source table')
    result = deepcopy({key: graph[key] for key in ('nodes', 'relationships')})
    def source(index):
        if type(index) is not int or not 0 <= index < len(graph['sources']):
            raise ValueError('invalid reconstructed source index')
        return graph['sources'][index]
    for node in result['nodes']:
        for mention in node['mentions']:
            mention['source'] = source(mention['source'])
        node['identitySources'] = [source(index) for index in node['identitySources']]
    for edge in result['relationships']:
        for d in edge['derivations']:
            d['sources'] = [source(index) for index in d['sources']]
    return result


def serialize(inputs, results):
    if not results or any(result.configuration != results[0].configuration for result in results):
        raise ValueError('evidence views require the same engine configuration')
    people = deepcopy(identities(inputs.people))
    counts = Counter(person['name'] for person in people)
    keys = registry_keys(people)
    references = {key: person.get('id') or (person['name'] if counts[person['name']] == 1 else None)
                  for key, person in zip(keys, people)}
    by_key = dict(zip(keys, people))
    for person in people:
        person['relationships'] = []
    combined = {}
    for result in results:
        for edge in result.relationships:
            if not references.get(edge.person) or not references.get(edge.of):
                continue
            left, right = edge.person, edge.of
            if edge.type != 'parent' and references[left] > references[right]:
                left, right = right, left
            key = (left, edge.type, references[right], edge.term)
            record = combined.setdefault(key, {'type': edge.type, 'of': references[right], 'derivations': []})
            if edge.term:
                record['term'] = edge.term
            for derivation in edge.derivations:
                if derivation not in record['derivations']:
                    record['derivations'].append(derivation)
    for (owner, _, _, _), record in sorted(combined.items()):
        record['derivations'].sort(key=lambda value: (value['view'], fingerprint(value)))
        by_key[owner]['relationships'].append(record)
    people[0]['familyGraph'] = {
        'schema': 2, 'engine': ENGINE_VERSION, 'policy': POLICY_VERSION,
        'configuration': results[0].configuration,
        'views': [result.view for result in results],
        'inputs': inputs.manifest, 'fingerprint': fingerprint(inputs.manifest),
        'evidence': {result.view: pack_evidence(result.evidence_graph) for result in results},
        'coverage': {result.view: {'unresolvedMentions': sum(d.status == 'unresolved' for d in result.decisions.values()),
                                  'omittedRelationships': sum(not references.get(e.person) or not references.get(e.of) for e in result.relationships),
                                  'conflicts': len(result.conflicts),
                                  'reconstructedPeople': len(result.evidence_graph['nodes']),
                                  'reconstructedRelationships': len(result.evidence_graph['relationships']),
                                  'contextualLinks': len(result.evidence_graph['links'])} for result in results},
    }
    validate_generated(people, inputs.root)
    return people


def validate_generated(people, root=None):
    if not isinstance(people, list) or not people:
        raise ValueError('generated registry must be a non-empty array')
    metadata = people[0].get('familyGraph', {})
    if (metadata.get('schema') != 2 or metadata.get('engine') != ENGINE_VERSION or metadata.get('policy') != POLICY_VERSION
        or metadata.get('views') not in (['facts'], ['facts', 'with-guesses'])
        or not isinstance(metadata.get('inputs'), dict)
        or not {'data/people.json', 'data/places.json', 'data/names.md'} <= metadata.get('inputs', {}).keys()
        or type(metadata.get('configuration', {}).get('searchLimit')) is not int
        or metadata['configuration']['searchLimit'] < 1
        or fingerprint(metadata['inputs']) != metadata.get('fingerprint')):
        raise ValueError('invalid generated build metadata')
    if root is not None and metadata['inputs'] != input_manifest(root, people):
        raise ValueError('stale build inputs; rerun reconstruction')
    ids = {person['id']: index for index, person in enumerate(people) if person.get('id')}
    if len(ids) != sum(bool(person.get('id')) for person in people):
        raise ValueError('duplicate person ID')
    names = {}
    for index, person in enumerate(people):
        names.setdefault(person['name'], []).append(index)

    def target(reference):
        if reference in ids:
            return ids[reference]
        matches = names.get(reference, [])
        if len(matches) != 1:
            raise ValueError(f'unknown or ambiguous generated endpoint {reference!r}')
        return matches[0]

    cache, seen = {}, set()
    parent_edges = {view: [] for view in metadata['views']}
    for index, person in enumerate(people):
        if any(field in person for field in ('wife', 'children')) or index > 0 and 'familyGraph' in person:
            raise ValueError('mixed legacy/generated registry or duplicate build metadata')
        if not isinstance(person.get('relationships'), list):
            raise ValueError('every generated person requires a relationships array')
        for edge in person['relationships']:
            if edge.get('type') not in {'parent', 'spouse', 'sibling', 'kin'} or set(edge) - {'type', 'of', 'term', 'derivations'}:
                raise ValueError('invalid generated relationship')
            if (edge['type'] == 'kin') != (isinstance(edge.get('term'), str) and bool(edge['term'].strip())):
                raise ValueError('only kin requires a non-empty source term')
            endpoint = target(edge['of'])
            if endpoint == index:
                raise ValueError('self-relationship')
            pair = (index, endpoint) if edge['type'] == 'parent' else tuple(sorted((index, endpoint)))
            key = (edge['type'], pair, edge.get('term', ''))
            if key in seen:
                raise ValueError('duplicate relationship')
            seen.add(key)
            if not isinstance(edge.get('derivations'), list) or not edge['derivations']:
                raise ValueError('relationship without derivations')
            for derivation in edge['derivations']:
                view = derivation.get('view')
                if (set(derivation) != {'view', 'identity', 'usesGuesses', 'sources'}
                    or view not in metadata['views'] or derivation.get('identity') not in {'anchored', 'reviewed', 'inferred'}
                    or not isinstance(derivation.get('usesGuesses'), bool)
                    or view == 'facts' and derivation['usesGuesses']
                    or not isinstance(derivation.get('sources'), list) or not derivation['sources']):
                    raise ValueError('invalid relationship derivation')
                if edge['type'] == 'parent':
                    parent_edges[view].append((index, endpoint))
                found_relationship = False
                for source in derivation['sources']:
                    path = source.get('path', '')
                    pointer = source.get('pointer', '')
                    if (set(source) != {'path', 'pointer', 'fingerprint'} or path not in metadata['inputs']
                        or not re.fullmatch(r'data/(books|documents|notes|images)/[^\0]+\.json', path)
                        or '..' in path.split('/') or not re.fullmatch(r'sha256:[a-f0-9]{64}', source.get('fingerprint', ''))
                        or not re.search(r'/(facts|guesses)/[0-9]+$', pointer)):
                        raise ValueError('invalid source reference')
                    if '/guesses/' in pointer and not derivation['usesGuesses']:
                        raise ValueError('unmarked guess dependency')
                    if root is not None:
                        if path not in cache:
                            cache[path] = json.loads((root / path).read_text(encoding='utf-8'))
                        try:
                            assertion = resolve_pointer(cache[path], pointer)
                        except (KeyError, IndexError, TypeError, ValueError) as exc:
                            raise ValueError('stale evidence pointer') from exc
                        if fingerprint(assertion) != source['fingerprint']:
                            raise ValueError('stale evidence fingerprint')
                        found_relationship |= assertion.get('type') == edge['type']
                if root is not None and not found_relationship:
                    raise ValueError('derivation lacks a supporting relationship assertion')
    if any(cycle_nodes(edges) for edges in parent_edges.values()):
        raise ValueError('generated parentage cycle')
    validate_evidence(metadata, registry_keys(people), root, cache)
    return metadata


def validate_evidence(metadata, registry, root=None, cache=None):
    graphs = metadata.get('evidence')
    if not isinstance(graphs, dict) or set(graphs) != set(metadata['views']):
        raise ValueError('missing reconstructed evidence views')
    cache = {} if cache is None else cache
    resolved = {}

    def source(ref, view):
        path, pointer = ref.get('path', ''), ref.get('pointer', '')
        if (set(ref) != {'path', 'pointer', 'fingerprint'} or path not in metadata['inputs']
            or not re.fullmatch(r'data/(books|documents|notes|images)/[^\0]+\.json', path)
            or '..' in path.split('/') or not re.fullmatch(r'sha256:[a-f0-9]{64}', ref.get('fingerprint', ''))
            or not re.search(r'/(facts|guesses)/[0-9]+$', pointer)
            or view == 'facts' and '/guesses/' in pointer):
            raise ValueError('invalid reconstructed source reference')
        if root is None:
            return None
        key = path, pointer, ref['fingerprint']
        if key not in resolved:
            if path not in cache:
                cache[path] = json.loads((root / path).read_text(encoding='utf-8'))
            try:
                value = resolve_pointer(cache[path], pointer)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise ValueError('stale reconstructed evidence pointer') from exc
            if fingerprint(value) != ref['fingerprint']:
                raise ValueError('stale reconstructed evidence fingerprint')
            resolved[key] = value
        return resolved[key]

    for view, graph in graphs.items():
        graph = unpack_evidence(graph)
        if set(graph) != {'nodes', 'relationships'} or not isinstance(graph['nodes'], list) or not isinstance(graph['relationships'], list):
            raise ValueError('invalid reconstructed graph')
        nodes, membership = {}, {}
        for node in graph['nodes']:
            key = node.get('key')
            if (not isinstance(key, str) or key in nodes or not node.get('name')
                or node.get('status') not in {'anchored', 'contextual', 'source'} or not node.get('mentions')
                or ('registry' in node and (node['registry'] != key or key not in registry))
                or ('registry' not in node and (not key.startswith('@evidence/') or key in registry))):
                raise ValueError('invalid reconstructed person')
            nodes[key] = node
            for mention in node['mentions']:
                fact = source(mention['source'], view)
                field = mention.get('field')
                if field not in {'person', 'of'} or fact is not None and field not in fact:
                    raise ValueError('invalid reconstructed participant')
                if fact is not None and fact[field] in registry and key != fact[field]:
                    raise ValueError('reconstructed occurrence overrides a fixed registry anchor')
                location = (mention['source']['path'], mention['source']['pointer'], field)
                if location in membership:
                    raise ValueError('source occurrence assigned to two reconstructed people')
                membership[location] = key
            for ref in node.get('identitySources', []):
                source(ref, view)
        parents, seen = [], set()
        for edge in graph['relationships']:
            kind, left, right = edge.get('type'), edge.get('person'), edge.get('of')
            if kind not in {'parent', 'spouse', 'sibling', 'kin'} or left not in nodes or right not in nodes or left == right:
                raise ValueError('invalid reconstructed relationship endpoint')
            key = (kind, left, right, edge.get('term', '')) if kind == 'parent' else (kind, *sorted((left, right)), edge.get('term', ''))
            if key in seen or not edge.get('derivations') or kind == 'kin' and not edge.get('term', '').strip():
                raise ValueError('invalid reconstructed relationship')
            seen.add(key)
            if kind == 'parent':
                parents.append((left, right))
            for d in edge['derivations']:
                if (d.get('identity') not in {'anchored', 'reviewed', 'inferred', 'source'}
                    or type(d.get('usesGuesses')) is not bool or not d.get('sources')
                    or view == 'facts' and d['usesGuesses']):
                    raise ValueError('invalid reconstructed derivation')
                supported = False
                for ref in d['sources']:
                    if '/guesses/' in ref['pointer'] and not d['usesGuesses']:
                        raise ValueError('unmarked reconstructed guess dependency')
                    fact = source(ref, view)
                    if fact is not None and fact.get('type') == kind:
                        pair = [membership.get((ref['path'], ref['pointer'], field)) for field in ('person', 'of')]
                        supported |= pair == [left, right] if kind == 'parent' else sorted(pair, key=str) == sorted([left, right])
                if root is not None and not supported:
                    raise ValueError('reconstructed edge has no supporting participant assignment')
        if cycle_nodes(parents):
            raise ValueError('reconstructed parentage cycle')


def apply(inputs, people):
    validate_generated(people, inputs.root)
    path = inputs.root / 'data/people.json'
    output = (json.dumps(people, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if inputs.manifest != input_manifest(inputs.root) or path.read_bytes() != inputs.registry_bytes:
        raise ValueError('inputs changed during computation; registry was not written')
    if output != inputs.registry_bytes:
        path.write_bytes(output)
    return output
