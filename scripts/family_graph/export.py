"""Validate a generated graph in memory and write only data/tree.json."""

from copy import deepcopy
import json
import re
import math
from .constraints import cycle_nodes
from .model import fingerprint, registry_keys
from .sources import input_manifest
from .probability import parameters


def resolve_pointer(value, pointer):
    if not pointer.startswith('/'):
        raise ValueError('expected an absolute JSON Pointer')
    for token in pointer[1:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def pack_evidence(graph):
    result = deepcopy({key: graph[key] for key in ('nodes', 'relationships', 'comparisons') if key in graph})
    refs = {}
    for node in result['nodes']:
        for ref in [*(m['source'] for m in node['mentions']), *node['identitySources']]:
            refs[(ref['path'], ref['pointer'], ref['fingerprint'])] = ref
    for edge in result['relationships']:
        for d in edge['derivations']:
            for ref in d['sources']:
                refs[(ref['path'], ref['pointer'], ref['fingerprint'])] = ref
    for comparison in result.get('comparisons', []):
        for ref in comparison['sources']:
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
    for comparison in result.get('comparisons', []):
        comparison['sources'] = [number(ref) for ref in comparison['sources']]
    return {'sources': [refs[key] for key in ordered], **result}


def unpack_evidence(graph):
    if 'sources' not in graph:
        return graph
    if set(graph) not in ({'sources', 'nodes', 'relationships'}, {'sources', 'nodes', 'relationships', 'comparisons'}) or not isinstance(graph['sources'], list):
        raise ValueError('invalid reconstructed source table')
    result = deepcopy({key: graph[key] for key in ('nodes', 'relationships', 'comparisons') if key in graph})
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
    for comparison in result.get('comparisons', []):
        comparison['sources'] = [source(index) for index in comparison['sources']]
    return result


def serialize(inputs, results):
    if not results or any(result.configuration != results[0].configuration for result in results):
        raise ValueError('evidence views require the same engine configuration')
    registry = set(registry_keys(inputs.people))
    tree = {
        'configuration': {'searchLimit': results[0].configuration['searchLimit']},
        'inputs': inputs.manifest, 'fingerprint': fingerprint(inputs.manifest),
        'evidence': {result.view: pack_evidence(result.evidence_graph) for result in results},
        'matchingBackground': {result.view: result.evidence_graph['nameFrequencies'] for result in results},
        'coverage': {result.view: {
            'unresolvedMentions': sum(d.status == 'unresolved' for d in result.decisions.values()),
            'registryRelationships': sum(e['person'] in registry and e['of'] in registry for e in result.evidence_graph['relationships']),
            'conflicts': len(result.conflicts),
            'reconstructedPeople': len(result.evidence_graph['nodes']),
            'reconstructedRelationships': len(result.evidence_graph['relationships']),
            'contextualLinks': len(result.evidence_graph['links']),
            'candidateComparisons': len(result.evidence_graph['comparisons']),
            'contextCoverage': result.evidence_graph['contextCoverage'],
        } for result in results},
    }
    validate_generated(tree, inputs.people, inputs.root)
    return tree


def validate_generated(tree, people, root=None):
    if (not isinstance(tree, dict)
        or not isinstance(tree.get('evidence'), dict) or not tree['evidence']
        or not set(tree['evidence']) <= {'facts', 'with-guesses'}
        or not isinstance(tree.get('inputs'), dict)
        or not {'data/people.json', 'data/places.json', 'data/names.md', 'data/matching.json'} <= tree.get('inputs', {}).keys()
        or type(tree.get('configuration', {}).get('searchLimit')) is not int
        or tree['configuration']['searchLimit'] < 1
        or fingerprint(tree['inputs']) != tree.get('fingerprint')):
        raise ValueError('invalid generated tree metadata')
    backgrounds = tree.get('matchingBackground')
    if not isinstance(backgrounds, dict) or set(backgrounds) != set(tree['evidence']):
        raise ValueError('missing name-frequency background')
    for background in backgrounds.values():
        if (not isinstance(background, dict) or not isinstance(background.get('counts'), dict)
            or type(background.get('total')) not in (int, float) or not math.isfinite(background['total'])
            or background['total'] < 0 or any(not isinstance(name, str) or type(count) not in (int, float)
                or not math.isfinite(count) or count <= 0 for name, count in background['counts'].items())
            or abs(sum(background['counts'].values()) - background['total']) > 1e-6):
            raise ValueError('invalid name-frequency background')
    if not isinstance(people, list) or not people:
        raise ValueError('person registry must be a non-empty array')
    ids = [person.get('id') for person in people]
    if (any(not isinstance(value, str) or not value.strip() for value in ids)
        or len(set(ids)) != len(ids) or set(ids) & {person['name'] for person in people}):
        raise ValueError('invalid confirmed person IDs')
    if root is not None and tree['inputs'] != input_manifest(root, people):
        raise ValueError('stale build inputs; rerun reconstruction')
    settings = parameters(json.loads((root / 'data/matching.json').read_text())) if root is not None else None
    if 'data/tree.json' in tree['inputs']:
        raise ValueError('generated tree cannot be an input to itself')
    validate_evidence(tree, {person['id']: person['name'] for person in people}, root, settings=settings)
    return tree


def validate_evidence(metadata, registry, root=None, cache=None, settings=None):
    graphs = metadata.get('evidence')
    if not isinstance(graphs, dict) or set(graphs) != set(metadata.get('matchingBackground', {})):
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
        if set(graph) != {'nodes', 'relationships', 'comparisons'} or not isinstance(graph['nodes'], list) or not isinstance(graph['relationships'], list):
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
            if type(node.get('identityProbability')) not in (int, float) or not 0 <= node['identityProbability'] <= 1:
                raise ValueError('invalid source identity probability')
            named = bool(node.get('registry') and registry[node['registry']] == node['name'])
            for mention in node['mentions']:
                fact = source(mention['source'], view)
                field = mention.get('field')
                if field not in {'person', 'of'} or fact is not None and (not isinstance(fact, dict) or field not in fact):
                    raise ValueError('invalid reconstructed participant')
                reference = fact[field] if fact is not None else None
                if fact is not None and reference in registry and key != reference:
                    raise ValueError('reconstructed occurrence overrides a fixed registry anchor')
                named |= fact is not None and reference == node['name']
                location = (mention['source']['path'], mention['source']['pointer'], field, mention.get('reference', ''))
                if location in membership:
                    raise ValueError('source occurrence assigned to two reconstructed people')
                membership[location] = key
            if root is not None and not named:
                raise ValueError('reconstructed name lacks a supporting source or confirmed registry name')
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
                if (type(d.get('assertionWeight')) not in (int, float) or not 0 < d['assertionWeight'] <= 1
                    or d.get('endpointProbability') is not None and (type(d['endpointProbability']) not in (int, float) or not 0 <= d['endpointProbability'] <= 1)):
                    raise ValueError('invalid relationship evidence weights')
                supported = False
                for ref in d['sources']:
                    if '/guesses/' in ref['pointer'] and not d['usesGuesses']:
                        raise ValueError('unmarked reconstructed guess dependency')
                    fact = source(ref, view)
                    if (isinstance(fact, dict) and fact.get('type') == kind
                        and fact.get('term', '') == edge.get('term', '')):
                        pair = [membership.get((ref['path'], ref['pointer'], field, '')) for field in ('person', 'of')]
                        supported |= pair == [left, right] if kind == 'parent' else sorted(pair, key=str) == sorted([left, right])
                if root is not None and not supported:
                    raise ValueError('reconstructed edge has no supporting participant assignment')
        if cycle_nodes(parents):
            raise ValueError('reconstructed parentage cycle')
        for comparison in graph['comparisons']:
            probability, log_odds = comparison.get('probability'), comparison.get('logOdds')
            if (comparison.get('person') not in nodes or comparison.get('candidate') not in nodes
                or comparison.get('status') not in {'merged', 'below-threshold', 'ambiguous', 'incompatible', 'superseded'}
                or type(probability) not in (int, float) or not 0 <= probability <= 1
                or type(log_odds) not in (int, float) or not math.isfinite(log_odds)
                or type(comparison.get('usesGuesses')) is not bool or not comparison.get('sources')
                or view == 'facts' and comparison['usesGuesses']):
                raise ValueError('invalid probability comparison')
            expected = 1 / (1 + math.exp(-max(-700, min(700, log_odds))))
            features = comparison.get('features', [])
            if (not isinstance(features, list) or any(not isinstance(f.get('name'), str)
                or type(f.get('contribution')) not in (int, float) or not math.isfinite(f['contribution']) for f in features)
                or abs(expected - probability) > 1e-7):
                raise ValueError('invalid probability calculation')
            if settings is not None:
                prior = settings['priorProbability']
                if abs(math.log(prior / (1 - prior)) + sum(f['contribution'] for f in features) - log_odds) > 1e-6:
                    raise ValueError('invalid probability feature sum')
            for ref in comparison['sources']:
                source(ref, view)
                if '/guesses/' in ref['pointer'] and not comparison['usesGuesses']:
                    raise ValueError('unmarked probability guess dependency')


class ConcurrentChange(ValueError):
    """Inputs or the tree changed while building; rebuilding again is safe."""


def apply(inputs, tree):
    validate_generated(tree, inputs.people, inputs.root)
    path = inputs.root / 'data/tree.json'
    output = (json.dumps(tree, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    previous = path.read_bytes() if path.exists() else None
    inputs_changed = (inputs.manifest != input_manifest(inputs.root)
                      or (inputs.root / 'data/people.json').read_bytes() != inputs.registry_bytes)
    # Another build may already have written this same result.
    if inputs_changed or previous not in (inputs.tree_bytes, output):
        raise ConcurrentChange('inputs or tree changed during computation; tree was not written')
    if output != previous:
        path.write_bytes(output)
    return output
