"""Source people and contextual linkage beyond the curated registry.

All nodes start as occurrences. Candidate links are proposed against a frozen
round, then checked together; no link can merge distinct registry anchors.
"""

from collections import defaultdict
from itertools import combinations
import math
import re

from .constraints import cycle_nodes
from .dates import compatible_deaths, near
from .model import fingerprint
from .probability import ProbabilityModel, Profile, title_category, reliability

RELATIONS = {'parent', 'spouse', 'sibling', 'kin'}
OPPOSED = ({'der Junge', 'der Jüngere'}, {'der Alte', 'der Ältere'})


def reconstruct(assertions, decisions, registry, names, parameters=None, observations=()):
    mentions = {m.handle: m for a in assertions for m in a.mentions}
    parent = {key: key for key in mentions}
    dependencies = defaultdict(dict)
    links, comparisons = [], {}
    model = ProbabilityModel(parameters, names)
    confidence = defaultdict(lambda: 1.0)
    round_scores = {}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def groups():
        result = defaultdict(list)
        for key in mentions:
            result[find(key)].append(key)
        return result

    def anchor(handles):
        return {mentions[h].reference for h in handles if mentions[h].reference in registry and registry[mentions[h].reference].get('id') == mentions[h].reference}

    def name(handle):
        ref = mentions[handle].reference
        return names.key(registry[ref]['name'] if ref in registry and registry[ref].get('id') == ref else ref)

    def given(value):
        first = value.split()[0]
        return first[:-1] if len(first) >= 4 and first[-1:] in {'a', 'e'} else first

    def compatible_names(left, right):
        a, b = left.split(), right.split()
        return given(left) == given(right) and (len(a) == 1 or len(b) == 1 or a[1:] == b[1:])

    def scope(mention):
        return (mention.assertion.source.path,
                mention.assertion.source.pointer.rsplit('/' + mention.assertion.source.kind + '/', 1)[0],
                mention.assertion.historical_date)

    def consistent(components):
        mapping = {h: index for index, component in enumerate(components) for h in component}
        for component in components:
            if len(anchor(component)) > 1 or not compatible_deaths([mentions[h] for h in component if mentions[h].assertion.source.kind == 'facts']):
                return False
            forms = {name(h) for h in component}
            if any(not compatible_names(a, b) for a, b in combinations(forms, 2)):
                return False
            by_scope = defaultdict(set)
            for h in component:
                by_scope[scope(mentions[h])].update(mentions[h].titles)
            if any(titles & OPPOSED[0] and titles & OPPOSED[1] for titles in by_scope.values()):
                return False
        edges = []
        for assertion in assertions:
            if assertion.original['type'] not in RELATIONS:
                continue
            left, right = [mapping[m.handle] for m in assertion.mentions]
            if left == right:
                return False
            if assertion.original['type'] == 'parent':
                edges.append((left, right))
        return not cycle_nodes(edges)

    def accept(proposals, reason):
        if not proposals:
            return 0
        current = groups()
        adjacency = defaultdict(set)
        support = defaultdict(dict)
        for left, right, sources in proposals:
            left, right = find(left), find(right)
            if left == right:
                continue
            adjacency[left].add(right)
            adjacency[right].add(left)
            for endpoint in (left, right):
                support[endpoint].update({source.key: source for source in sources})
        unseen = set(adjacency)
        components = []
        while unseen:
            stack, component = [min(unseen)], set()
            while stack:
                item = stack.pop()
                if item in component:
                    continue
                component.add(item)
                unseen.discard(item)
                stack.extend(adjacency[item] - component)
            components.append(component)
        accepted = 0
        # Test a complete candidate component; never pick an arbitrary pair
        # from a component that could join two existing namesake anchors.
        candidates = []
        for component in components:
            joined = sorted(h for key in component for h in current[key])
            other = [handles for key, handles in current.items() if key not in component]
            negative_pair = any(round_scores.get(tuple(sorted((a, b))), {}).get('probability', 1) < model.settings['clusterMinimumProbability']
                                and any(f['contribution'] < 0 and f['name'] not in {'document time distance'} for f in round_scores.get(tuple(sorted((a, b))), {}).get('features', []))
                                for a, b in combinations(component, 2))
            if not negative_pair and consistent([joined, *other]):
                candidates.append(component)
        # Different identity components can jointly create an ancestry cycle.
        # Check all proposed links in each connected source family together,
        # retaining alternatives instead of letting traversal order choose one.
        connected = defaultdict(set)
        for component in candidates:
            root = min(component)
            for key in component:
                connected[root].add(key)
                connected[key].add(root)
        for assertion in assertions:
            if assertion.original['type'] in RELATIONS:
                left, right = [find(m.handle) for m in assertion.mentions]
                connected[left].add(right)
                connected[right].add(left)
        unseen = set().union(*candidates) if candidates else set()
        while unseen:
            stack, family = [min(unseen)], set()
            while stack:
                key = stack.pop()
                if key in family:
                    continue
                family.add(key)
                unseen.discard(key)
                stack.extend(connected[key] - family)
            batch = [component for component in candidates if component & family]
            involved = set().union(*batch)
            partitions = [[h for key in component for h in current[key]] for component in batch]
            partitions += [handles for key, handles in current.items() if key not in involved]
            if not consistent(partitions):
                continue
            for component in batch:
                joined = sorted(h for key in component for h in current[key])
                root, refs = min(component), {}
                for key in component:
                    refs.update(dependencies[key])
                    refs.update(support[key])
                for key in component:
                    parent[key] = root
                dependencies[root].update(refs)
                estimates = [record['probability'] for (a, b), record in round_scores.items() if a in component and b in component]
                confidence[root] = min([confidence[key] for key in component] + estimates)
                links.append({'reason': reason, 'mentions': joined,
                              'sources': [refs[key].export() for key in sorted(refs)]})
                accepted += len(component) - 1
            current = groups()
        return accepted

    # Only exact source IDs seed fixed identities. The preceding registry
    # resolver's inferred scores never bypass this probability model.
    by_anchor = defaultdict(list)
    for handle, mention in mentions.items():
        if mention.reference in anchor([handle]):
            by_anchor[mention.reference].append(handle)
    for handles in by_anchor.values():
        for handle in handles[1:]:
            parent[handle] = handles[0]

    # A source's repeated participant reference supplies local context. If that
    # passage distinguishes namesakes, leave the unqualified occurrences apart.
    local = defaultdict(list)
    for handle, mention in mentions.items():
        if not anchor([handle]):
            local[(scope(mention), name(handle))].append(handle)
    local_proposals = []
    for handles in local.values():
        if len(handles) < 2:
            continue
        for left, right in zip(handles, handles[1:]):
            local_proposals.append((left, right, [mentions[left].assertion.source, mentions[right].assertion.source]))
    accept(local_proposals, 'repeated participant within one dated source passage')

    # Only a specific source reference plus the historical date and complete
    # relationship signature can identify a repeated attestation.
    duplicates = defaultdict(list)
    for assertion in assertions:
        if assertion.original['type'] not in RELATIONS:
            continue
        citation = assertion.source.citation
        if not re.search(r'\b(?:nr|no|regest|urkunde|urk|charter|item)\.?\s*[:#]?\s*\d+|\bn\.\s*\d+', citation, re.I):
            continue
        signature = (assertion.historical_date, citation, assertion.original['type'],
                     tuple(name(m.handle) for m in assertion.mentions),
                     tuple(m.titles for m in assertion.mentions), assertion.original.get('term', ''))
        duplicates[signature].append(assertion)
    proposals = []
    for copies in duplicates.values():
        for first, second in zip(copies, copies[1:]):
            for left, right in zip(first.mentions, second.mentions):
                proposals.append((left.handle, right.handle, [first.source, second.source]))
    accept(proposals, 'same dated relationship in a specifically cited attestation')

    # Frozen-round profiles combine dated titles, geography, same-fact
    # associates and family evidence for every source identity, not just IDs.
    for iteration in range(model.settings['maxRounds']):
        current = groups()
        profiles = {root: Profile(handles, [mentions[h] for h in handles], anchored=bool(anchor(handles)), confidence=confidence[root], key=root)
                    for root, handles in current.items()}
        root_names = {root: min((name(h) for h in handles), key=lambda value: (-len(value.split()), -len(value), value))
                      for root, handles in current.items()}
        for root, profile in profiles.items():
            profile.refs.update(dependencies[root])
        scopes = defaultdict(lambda: defaultdict(set))
        for handle, mention in mentions.items():
            root = find(handle)
            passage = scope(mention)
            scopes[passage][name(handle)].add(root)
            profile = profiles[root]
            ref, bounds = mention.assertion.source, mention.assertion.bounds
            profile.refs[ref.key] = ref
            for title in mention.titles:
                profile.titles.setdefault(title_category(title), []).append((ref, bounds))
            model.add_context(profile, ref, bounds, issuance=mention.assertion.context.get('place', ''))
        for observation in observations:
            if not observation or observation.bounds is None:
                continue
            passage = (observation.source.path, observation.source.pointer.rsplit('/' + observation.source.kind + '/', 1)[0], observation.historical_date)
            found = model.person_names(observation.text)
            for person_name in sorted(found):
                candidates = scopes[passage].get(person_name, set())
                # A prose name cannot select one of several namesakes in a
                # passage, and a whole entry is never an associate clique.
                if len(candidates) == 1:
                    root = next(iter(candidates))
                    model.add_context(profiles[root], observation.source, observation.bounds, observation.text,
                                      self_names={root_names[root], person_name})
        parents = defaultdict(lambda: defaultdict(list))
        def relative(profile_root, relative_root, role, source_assertions):
            profile, other = profiles[profile_root], profiles[relative_root]
            relative_name = root_names[relative_root]
            tokens = [(role, relative_root, relative_name, other.anchored, other.confidence),
                      (role, '', relative_name, False, 1.0)]
            for token in tokens:
                profile.relatives.setdefault(token, []).extend((a.source, a.bounds) for a in source_assertions)
            for a in source_assertions:
                profile.refs[a.source.key] = a.source
            profile.refs.update(dependencies[relative_root])
        for assertion in assertions:
            if assertion.original['type'] not in RELATIONS:
                continue
            a, b = assertion.mentions
            left, right = find(a.handle), find(b.handle)
            kind = assertion.original['type']
            profiles[left].distinctions.setdefault(right, []).append(assertion.source)
            profiles[right].distinctions.setdefault(left, []).append(assertion.source)
            for own, other, direction in ((left, right, 'out'), (right, left, 'in')):
                role = kind, direction if kind == 'parent' else '', assertion.original.get('term', '')
                relative(own, other, role, [assertion])
                if kind == 'spouse':
                    relative(own, other, ('family context', '', ''), [assertion])
            if kind == 'parent':
                parents[right][left].append(assertion)
        for co_parents in parents.values():
            for left, right in combinations(co_parents, 2):
                basis = [*co_parents[left], *co_parents[right]]
                relative(left, right, ('family context', '', ''), basis)
                relative(right, left, ('family context', '', ''), basis)
        buckets = defaultdict(list)
        for root in current:
            buckets[given(root_names[root])].append(root)
        round_scores, options = {}, defaultdict(list)
        for roots in buckets.values():
            for left, right in combinations(roots, 2):
                if not all(compatible_names(name(a), name(b)) for a in current[left] for b in current[right]):
                    continue
                record = model.compare(profiles[left], profiles[right])
                if not record.pop('substantive'):
                    continue
                pair = tuple(sorted((left, right)))
                record.update(mentions=list(pair), iteration=iteration, status='below-threshold', reason='below merge probability')
                round_scores[pair] = record
                comparisons[pair] = record
                if len(anchor([*current[left], *current[right]])) > 1:
                    record.update(status='incompatible', reason='distinct confirmed registry IDs')
                    continue
                if record['probability'] < model.settings['mergeProbability']:
                    continue
                record.update(status='ambiguous', reason='competing candidates within the decision margin')
                options[left].append((record['logOdds'], right))
                options[right].append((record['logOdds'], left))
        proposals, selected = [], set()
        margin = model.settings['ambiguityLogOddsMargin']
        for left, alternatives in options.items():
            best = max(score for score, _ in alternatives)
            best_options = [right for score, right in alternatives if best - score < margin]
            if len(set().union(*(anchor(current[key]) for key in [left, *best_options]))) > 1:
                continue
            for right in best_options:
                reverse_best = max(score for score, _ in options[right])
                pair = tuple(sorted((left, right)))
                if reverse_best - round_scores[pair]['logOdds'] >= margin or pair in selected:
                    continue
                selected.add(pair)
                # Negative and rival evidence can influence selection too.
                refs = {**profiles[left].refs, **profiles[right].refs, **dependencies[left], **dependencies[right]}
                for (a, b), comparison in round_scores.items():
                    if left in (a, b) or right in (a, b):
                        without_negative = comparison['logOdds'] - sum(min(0, f['contribution']) for f in comparison['features'])
                        threshold = model.settings['mergeProbability']
                        if comparison['probability'] >= threshold or without_negative >= math.log(threshold / (1 - threshold)):
                            refs.update({ref.key: ref for ref in comparison['sources']})
                proposals.append((left, right, list(refs.values())))
                round_scores[pair]['sources'] = [refs[key] for key in sorted(refs)]
        count = accept(proposals, 'weighted probability of source identity')
        for pair in selected:
            if find(pair[0]) == find(pair[1]):
                round_scores[pair].update(status='merged', reason='probability, margin and cluster constraints passed')
            else:
                round_scores[pair].update(status='incompatible', reason='complete proposed cluster violates identity constraints')
        if not count:
            break

    current = groups()
    keys = {}
    nodes = []
    for root, handles in sorted(current.items()):
        anchors = anchor(handles)
        key = next(iter(anchors)) if anchors else '@evidence/' + fingerprint(sorted(handles)).split(':')[1][:20]
        for handle in handles:
            keys[handle] = key
        refs = {}
        occurrences = []
        for handle in sorted(handles):
            mention = mentions[handle]
            refs[mention.assertion.source.key] = mention.assertion.source
            occurrences.append({'source': mention.assertion.source.export(), 'field': mention.field,
                                'date': mention.assertion.historical_date})
        display = min(handles, key=lambda h: (-len(name(h).split()), -len(mentions[h].reference), h))
        nodes.append({'key': key, **({'registry': key} if anchors else {}),
                      'name': registry[key]['name'] if anchors else mentions[display].reference,
                      'titles': sorted({title for h in handles for title in mentions[h].titles}),
                      'dates': sorted({mentions[h].assertion.historical_date for h in handles}),
                      'status': 'anchored' if anchors else 'contextual' if len({scope(mentions[h]) for h in handles}) > 1 else 'source',
                      'identityProbability': round(confidence[root], 8),
                      'mentions': occurrences,
                      'identitySources': [ref.export() for _, ref in sorted(dependencies[root].items())]})
    edges = {}
    for assertion in assertions:
        kind = assertion.original['type']
        if kind not in RELATIONS:
            continue
        left, right = [keys[m.handle] for m in assertion.mentions]
        if kind != 'parent' and left > right:
            left, right = right, left
        key = kind, left, right, assertion.original.get('term', '')
        support = {assertion.source.key: assertion.source}
        methods = []
        for mention in assertion.mentions:
            root = find(mention.handle)
            if anchor([mention.handle]):
                methods.append('anchored')
            else:
                methods.append('inferred' if len(current[root]) > 1 else 'source')
                support.update(dependencies[root])
        identity = next((value for value in ('source', 'inferred', 'reviewed', 'anchored') if value in methods), 'source')
        derivation = {'identity': identity, 'usesGuesses': any(ref.kind == 'guesses' for ref in support.values()),
                      'assertionWeight': reliability(assertion.source, model.settings),
                      'endpointProbability': None if 'source' in methods else min(confidence[find(m.handle)] if not anchor([m.handle]) else 1.0 for m in assertion.mentions),
                      'sources': [support[value].export() for value in sorted(support)]}
        edge = edges.setdefault(key, {'type': kind, 'person': left, 'of': right, 'derivations': []})
        if kind == 'kin':
            edge['term'] = key[3]
        if derivation not in edge['derivations']:
            edge['derivations'].append(derivation)
    # Unconnected title/death occurrences remain available for identity scoring;
    # the family view contains participants in actual relationship assertions.
    participants = {edge[field] for edge in edges.values() for field in ('person', 'of')}
    exported_comparisons = []
    for pair, comparison in sorted(comparisons.items()):
        left, right = keys[pair[0]], keys[pair[1]]
        if left not in participants or right not in participants:
            continue
        if left == right and comparison['status'] != 'merged':
            comparison = {**comparison, 'status': 'superseded',
                          'reason': 'earlier comparison; later compatible cluster evidence joined these occurrences'}
        exported_comparisons.append({**comparison, 'person': left, 'candidate': right,
            'usesGuesses': any(ref.kind == 'guesses' for ref in comparison['sources']),
            'sources': [ref.export() for ref in comparison['sources']]})
    return {'nodes': [node for node in nodes if node['key'] in participants],
            'relationships': [edges[key] for key in sorted(edges)], 'links': links,
            'comparisons': exported_comparisons}
