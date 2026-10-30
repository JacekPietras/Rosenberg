"""Source people and contextual linkage beyond the curated registry.

All nodes start as occurrences. Candidate links are proposed against a frozen
round, then checked together; no link can merge distinct registry anchors.
"""

from collections import defaultdict
from itertools import combinations
import math
import re

from .constraints import cycle_nodes
from .model import fingerprint, Assertion, Mention
from .policy import AGE_TITLES
from .probability import ProbabilityModel, Profile, chronology_blocked, title_category, reliability

RELATIONS = {'parent', 'spouse', 'sibling', 'kin'}


def reconstruct(assertions, decisions, registry, names, parameters=None, observations=()):
    mentions = {m.handle: m for a in assertions for m in a.mentions}
    parent = {key: key for key in mentions}
    dependencies = defaultdict(dict)
    links, comparisons = [], {}
    model = ProbabilityModel(parameters, names)
    model.set_name_frequencies(assertions, observations, registry)
    # Informative prose-only actors are context occurrences, not new family
    # assertions. They can bridge typed family records, but never add edges.
    typed_scopes = defaultdict(list)
    for mention in mentions.values():
        key = (mention.assertion.source.path, mention.assertion.source.pointer.rsplit('/' + mention.assertion.source.kind + '/', 1)[0])
        typed_scopes[key].append(mention)
    context_handles = defaultdict(list)
    required = math.log(model.settings['mergeProbability'] / (1 - model.settings['mergeProbability'])) - math.log(model.settings['priorProbability'] / (1 - model.settings['priorProbability']))
    for observation in observations:
        if not observation.bounds:
            continue
        passage = (observation.source.path, observation.source.pointer.rsplit('/' + observation.source.kind + '/', 1)[0])
        explicit = {identity for identity, person in registry.items() if person.get('id') == identity and '[' + identity + ']' in observation.text}
        references = set(explicit)
        literal_references = model.person_references(observation.text)
        normalized_counts = defaultdict(int)
        for reference in literal_references:
            normalized_counts[names.key(reference)] += observation.text.count(reference)
        for identity in explicit:
            normalized_counts[names.key(registry[identity]['name'])] += 1
        for reference in literal_references:
            normalized = names.key(reference)
            if any(names.key(registry[m.reference]['name'] if m.reference in registry else m.reference) == normalized
                   and max(m.assertion.bounds[0], observation.bounds[0]) <= min(m.assertion.bounds[1], observation.bounds[1])
                   for m in typed_scopes[passage]):
                continue
            # A repeated literal name in one fact may distinguish namesakes.
            if normalized_counts[normalized] != 1 or reference in registry:
                continue
            profile = Profile([], [])
            model.add_context(profile, observation.source, observation.bounds, observation.text,
                              issuance=observation.context.get('place', ''), self_names={normalized})
            places = {place: max(model.settings['placeWeights'][role] for role, site in profile.places if place == site) for _, place in profile.places}
            potential = (sum(places.values()) + min(model.settings['associateMaxWeight'], len(profile.associates) * model.settings['associateWeight'])) * reliability(observation.source, model.settings)
            if potential >= required:
                references.add(reference)
        for reference in sorted(references):
            handle = observation.source.key + '/text/' + reference
            assertion = Assertion(observation.source, {'type': 'context'}, observation.historical_date, observation.bounds, observation.context)
            mention = Mention(handle, reference, 'text', (), False, assertion)
            assertion.mentions = [mention]
            mentions[handle] = mention
            parent[handle] = handle
            context_handles[observation.source.key].append(handle)
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

    def chronology_conflict(component):
        # An identity whose own sources already conflict (a data conflict on a
        # fixed ID) is not blocked again; pairwise comparisons still apply.
        parts = defaultdict(list)
        for h in component:
            parts[find(h)].append(mentions[h])
        if any(chronology_blocked(part, model.settings) for part in parts.values()):
            return False
        return chronology_blocked([mentions[h] for h in component], model.settings)

    def consistent(components, new=None):
        # Only proposed components are checked for chronology; unchanged
        # identities cannot block unrelated merges.
        mapping = {h: index for index, component in enumerate(components) for h in component}
        for index, component in enumerate(components):
            if len(anchor(component)) > 1:
                return False
            if (new is None or index < new) and chronology_conflict(component):
                return False
            forms = {name(h) for h in component}
            if any(not compatible_names(a, b) for a, b in combinations(forms, 2)):
                return False
            by_scope = defaultdict(set)
            for h in component:
                by_scope[scope(mentions[h])].update(mentions[h].titles)
            # Different age designations in one passage name different people.
            if any(len(titles & AGE_TITLES) > 1 for titles in by_scope.values()):
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
                                and any(f['contribution'] < 0 for f in round_scores.get(tuple(sorted((a, b))), {}).get('features', []))
                                for a, b in combinations(component, 2))
            if not negative_pair and consistent([joined, *other], 1):
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
            if not consistent(partitions, len(batch)):
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
                estimates = [round_scores[pair]['probability'] for a in component for b in adjacency[a]
                             if a < b and (pair := tuple(sorted((a, b)))) in round_scores]
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
        if not anchor([handle]) and mention.field != 'text':
            local[(scope(mention), name(handle))].append(handle)
    local_proposals = []
    current_local = groups()
    def compatible_local(handles):
        roots = {find(h) for h in handles}
        joined = [h for root in roots for h in current_local[root]]
        return consistent([joined, *[group for root, group in current_local.items() if root not in roots]], 1)
    for handles in local.values():
        if len(handles) < 2:
            continue
        neighbors = defaultdict(set)
        pairs = []
        for left, right in combinations(handles, 2):
            if compatible_local([left, right]):
                pairs.append((left, right))
                neighbors[left].add(right); neighbors[right].add(left)
        # An unqualified occurrence compatible with conflicting namesakes must
        # not bridge them. Qualified occurrences can still group with each other.
        ambiguous = {h for h, choices in neighbors.items() if not compatible_local([h, *choices])}
        for left, right in pairs:
            if left not in ambiguous and right not in ambiguous:
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
        scope_mentions = defaultdict(list)
        for handle, mention in mentions.items():
            root = find(handle)
            scope_mentions[(scope(mention)[:2], name(handle))].append((handle, mention))
            profile = profiles[root]
            ref, bounds = mention.assertion.source, mention.assertion.bounds
            profile.refs[ref.key] = ref
            for title in mention.titles:
                category = title_category(title)
                profile.titles.setdefault(category, []).append((ref, bounds))
                if category[0] == 'office':
                    for place in model.places(title):
                        profile.office_scopes.setdefault(place, []).append((ref, bounds))
            model.add_context(profile, ref, bounds, issuance=mention.assertion.context.get('place', ''))
        context_coverage = {'total': len(observations), 'attached': 0, 'undated': 0, 'unattached': 0, 'explicitIdFacts': 0}
        # A bracketed confirmed ID identifies its person even when that source
        # contains no typed participant. Plain names still require local context.
        ids = {identity: registry[identity]['name'] for identity in by_anchor}
        for observation in observations:
            if not observation or observation.bounds is None:
                context_coverage['undated'] += 1
                continue
            passage = (observation.source.path, observation.source.pointer.rsplit('/' + observation.source.kind + '/', 1)[0])
            explicit = {identity for identity in ids if '[' + identity + ']' in observation.text}
            text = observation.text
            for identity in sorted(explicit):
                text = text.replace('[' + identity + ']', ids[identity])
            attached = {find(by_anchor[identity][0]) for identity in explicit}
            attached.update(find(handle) for handle in context_handles[observation.source.key])
            if explicit:
                context_coverage['explicitIdFacts'] += 1
            found = model.person_names(observation.text)
            for person_name in sorted(found):
                # Match date intervals, not ISO spelling: 1393 and 1393-05-01
                # may refer to the same passage participant.
                candidates = {find(h) for h, m in scope_mentions[(passage, person_name)]
                              if max(m.assertion.bounds[0], observation.bounds[0]) <= min(m.assertion.bounds[1], observation.bounds[1])}
                if len(candidates) == 1:
                    attached.update(candidates)
            for root in sorted(attached):
                model.add_context(profiles[root], observation.source, observation.bounds, text,
                                  self_names={root_names[root]})
            context_coverage['attached' if attached else 'unattached'] += 1
        parents = defaultdict(lambda: defaultdict(list))
        def relative(profile_root, relative_root, role, source_assertions, context_confidence=1.0, context_refs=()):
            profile, other = profiles[profile_root], profiles[relative_root]
            relative_name = root_names[relative_root]
            tokens = [(role, relative_root, relative_name, other.anchored, min(other.confidence, context_confidence)),
                      (role, '', relative_name, False, 1.0)]
            for token in tokens:
                profile.relatives.setdefault(token, []).extend((a.source, a.bounds) for a in source_assertions)
            for a in source_assertions:
                profile.refs[a.source.key] = a.source
            profile.refs.update(dependencies[relative_root])
            profile.refs.update({ref.key: ref for ref in context_refs})
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
        for child, co_parents in parents.items():
            for left, right in combinations(co_parents, 2):
                # Repeated attestations of a same-named parent are not evidence
                # that those unresolved parent records are different partners.
                if compatible_names(root_names[left], root_names[right]):
                    continue
                basis = [*co_parents[left], *co_parents[right]]
                relative(left, right, ('family context', '', ''), basis, confidence[child], dependencies[child].values())
                relative(right, left, ('family context', '', ''), basis, confidence[child], dependencies[child].values())
        buckets = defaultdict(list)
        for root in current:
            buckets[given(root_names[root])].append(root)
        round_scores, options = {}, defaultdict(list)
        for roots in buckets.values():
            for left, right in combinations(roots, 2):
                if not all(compatible_names(name(a), name(b)) for a in current[left] for b in current[right]):
                    continue
                record = model.compare(profiles[left], profiles[right])
                blocks = record.pop('blocks')
                if not record.pop('substantive'):
                    continue
                pair = tuple(sorted((left, right)))
                record.update(mentions=list(pair), iteration=iteration, status='below-threshold', reason='below merge probability')
                round_scores[pair] = record
                comparisons[pair] = record
                if len(anchor([*current[left], *current[right]])) > 1:
                    record.update(status='incompatible', reason='distinct confirmed registry IDs')
                    continue
                if blocks:
                    record.update(status='incompatible', reason='blocked: ' + '; '.join(blocks))
                    continue
                partial_name = any((len(name(a).split()) == 1) != (len(name(b).split()) == 1)
                                   for a in current[left] for b in current[right])
                if partial_name and not any(f['contribution'] > 0 and ('family context:' in f['name'] or 'office title:' in f['name'] or 'designation title:' in f['name']) for f in record['features']):
                    record.update(status='incompatible', reason='an omitted surname requires family or identifying-title support; shared geography and associates are insufficient')
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
                                'date': mention.assertion.historical_date,
                                **({'reference': mention.reference} if mention.field == 'text' else {})})
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
    context_coverage['contextOnlyOccurrences'] = sum(len(handles) for handles in context_handles.values())
    context_coverage['contextOccurrencesInFamilies'] = sum(keys[handle] in participants for handles in context_handles.values() for handle in handles)
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
            'comparisons': exported_comparisons, 'contextCoverage': context_coverage,
            'nameFrequencies': model.background}
