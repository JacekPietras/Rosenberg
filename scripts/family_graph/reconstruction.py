"""Source people and contextual linkage beyond the curated registry.

All nodes start as occurrences. Candidate links are proposed against a frozen
round, then checked together; no link can merge distinct registry anchors.
"""

from collections import defaultdict
from itertools import combinations
import re

from .constraints import cycle_nodes
from .dates import compatible_deaths, near
from .model import fingerprint

RELATIONS = {'parent', 'spouse', 'sibling', 'kin'}
OPPOSED = ({'der Junge', 'der Jüngere'}, {'der Alte', 'der Ältere'})


def reconstruct(assertions, decisions, registry, names):
    mentions = {m.handle: m for a in assertions for m in a.mentions}
    parent = {key: key for key in mentions}
    dependencies = defaultdict(dict)
    links = []

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
        return {decisions[h].identity for h in handles if decisions[h].status == 'accepted'}

    def name(handle):
        decision = decisions[handle]
        return names.key(registry[decision.identity]['name'] if decision.status == 'accepted' else mentions[handle].reference)

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
            if len(anchor(component)) > 1 or not compatible_deaths([mentions[h] for h in component]):
                return False
            if anchor(component) and any('search limit' in decisions[h].reason and decisions[h].identity is None for h in component):
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
            if consistent([joined, *other]):
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
                links.append({'reason': reason, 'mentions': joined,
                              'sources': [refs[key].export() for key in sorted(refs)]})
                accepted += len(component) - 1
            current = groups()
        return accepted

    # Exact and already reviewed/inferred registry assignments are fixed seeds.
    by_anchor = defaultdict(list)
    for handle, decision in decisions.items():
        if handle in mentions and decision.status == 'accepted':
            by_anchor[decision.identity].append(handle)
    for handles in by_anchor.values():
        for handle in handles[1:]:
            parent[handle] = handles[0]
        for handle in handles:
            decision = decisions[handle]
            dependencies[handles[0]].update({source.key: source for source in decision.sources})
            if decision.uses_guesses:
                ref = mentions[handle].assertion.source
                dependencies[handles[0]][ref.key] = ref

    # A source's repeated participant reference supplies local context. If that
    # passage distinguishes namesakes, leave the unqualified occurrences apart.
    local = defaultdict(list)
    for handle, mention in mentions.items():
        if decisions[handle].status != 'accepted':
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

    # Resolve source families together. A shared grounded relative is stronger
    # than a name; two matching source-stated relatives can link a family even
    # when none of its members has a registry ID.
    for _ in range(12):
        current = groups()
        profiles = defaultdict(dict)
        sources = defaultdict(dict)
        parents = defaultdict(lambda: defaultdict(list))
        for assertion in assertions:
            if assertion.original['type'] not in RELATIONS:
                continue
            a, b = assertion.mentions
            for mention, relative, direction in ((a, b, 'out'), (b, a, 'in')):
                key = find(mention.handle)
                role = assertion.original['type'], direction if assertion.original['type'] == 'parent' else '', assertion.original.get('term', '')
                token = role, find(relative.handle)
                profiles[key].setdefault(token, set()).add(name(relative.handle))
                sources[key][assertion.source.key] = assertion.source
                if assertion.original['type'] == 'spouse':
                    profiles[key].setdefault((('family context', '', ''), find(relative.handle)), set()).add(name(relative.handle))
            if assertion.original['type'] == 'parent':
                parents[find(b.handle)][find(a.handle)].append(assertion)
        # Co-parentage is identity context only. It never generates a marriage
        # or another parent assertion; both parents already have source edges.
        for co_parents in parents.values():
            for left, right in combinations(co_parents, 2):
                for a, b in ((left, right), (right, left)):
                    profiles[a].setdefault((('family context', '', ''), b), set()).add(name(current[b][0]))
                    for assertion in [*co_parents[left], *co_parents[right]]:
                        sources[a][assertion.source.key] = assertion.source
        by_name = defaultdict(list)
        for key, handles in current.items():
            by_name[given(name(handles[0]))].append(key)
        scores = defaultdict(list)
        supports = {}
        for candidates in by_name.values():
            for left, right in combinations(candidates, 2):
                if not all(compatible_names(name(a), name(b)) for a in current[left] for b in current[right]):
                    continue
                if len(anchor([*current[left], *current[right]])) > 1:
                    continue
                if not any(near(mentions[a].assertion.bounds, mentions[b].assertion.bounds, 25)
                           for a in current[left] for b in current[right]):
                    continue
                shared = set(profiles[left]) & set(profiles[right])
                grounded = {token[1] for token in shared if anchor(current[token[1]])}
                # Distinct relatives, not duplicate facts about one relative.
                shared_relatives = {token[1] for token in shared}
                left_names = {(role, relative_name) for (role, _), values in profiles[left].items() for relative_name in values}
                right_names = {(role, relative_name) for (role, _), values in profiles[right].items() for relative_name in values}
                family = left_names & right_names
                family_names = {value for _, value in family}
                score = 10 * len(grounded) + 5 * len(shared_relatives - grounded)
                if len(family_names) >= 2:
                    score += 4 * len(family_names)
                # A repeated full spouse name is a family-pair hypothesis,
                # rather than name-only linkage of either partner. Both source
                # relationships remain its provenance and uncertainty is kept.
                spouses = {relative_name for role, relative_name in family
                           if role[0] == 'spouse' and len(relative_name.split()) >= 2}
                if spouses:
                    score += 9
                if score < 8:
                    continue
                refs = {**sources[left], **sources[right]}
                for key in (left, right, *(token[1] for token in shared)):
                    refs.update(dependencies[key])
                scores[left].append((score, right))
                scores[right].append((score, left))
                supports[tuple(sorted((left, right)))] = list(refs.values())
        proposals = []
        for left, options in scores.items():
            best = max(score for score, _ in options)
            # Ambiguous rivals with distinct anchors are deliberately retained.
            best_options = [right for score, right in options if best - score < 3]
            competing_anchors = set().union(*(anchor(current[key]) for key in [left, *best_options]))
            if len(competing_anchors) > 1:
                continue
            for right in best_options:
                reverse_best = max(score for score, _ in scores[right])
                score = next(score for score, candidate in scores[right] if candidate == left)
                if reverse_best - score < 3:
                    proposals.append((left, right, supports[tuple(sorted((left, right)))]))
        if not accept(proposals, 'compatible source-stated family context'):
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
            decision = decisions[mention.handle]
            if decision.status == 'accepted':
                methods.append(decision.method)
                support.update({ref.key: ref for ref in decision.sources})
            else:
                methods.append('inferred' if len(current[find(mention.handle)]) > 1 else 'source')
                support.update(dependencies[find(mention.handle)])
        identity = next((value for value in ('source', 'inferred', 'reviewed', 'anchored') if value in methods), 'source')
        derivation = {'identity': identity, 'usesGuesses': any(ref.kind == 'guesses' for ref in support.values()),
                      'sources': [support[value].export() for value in sorted(support)]}
        edge = edges.setdefault(key, {'type': kind, 'person': left, 'of': right, 'derivations': []})
        if kind == 'kin':
            edge['term'] = key[3]
        if derivation not in edge['derivations']:
            edge['derivations'].append(derivation)
    # Unconnected title/death occurrences remain available for identity scoring;
    # the family view contains participants in actual relationship assertions.
    participants = {edge[field] for edge in edges.values() for field in ('person', 'of')}
    return {'nodes': [node for node in nodes if node['key'] in participants],
            'relationships': [edges[key] for key in sorted(edges)], 'links': links}
