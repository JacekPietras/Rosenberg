"""Source people and contextual linkage beyond the curated registry.

All nodes start as occurrences. Candidate links are proposed against a frozen
round, then checked together; no link can merge distinct registry anchors.
"""

from collections import defaultdict
from itertools import combinations, product
import math
import re

from .constraints import cycle_nodes
from .model import fingerprint, Assertion, Mention
from .policy import AGE_TITLES
from .kinship import generation, tree_paths
from .probability import ProbabilityModel, Profile, chronology_blocked, decay, title_category, reliability, speculative_parent_claim

RELATIONS = {'parent', 'spouse', 'sibling', 'kin'}


def generations_consistent(parent_edges, sibling_edges):
    """Siblings share a generation; a parent is exactly one generation above."""
    root, offset = {}, {}
    def find(node):
        root.setdefault(node, node); offset.setdefault(node, 0)
        if root[node] != node:
            top, value = find(root[node])
            offset[node] += value
            root[node] = top
        return root[node], offset[node]
    for (upper, lower), difference in [*((edge, 1) for edge in parent_edges), *((edge, 0) for edge in sibling_edges)]:
        (a, x), (b, y) = find(upper), find(lower)
        if a == b:
            if x - y != difference:
                return False
        else:
            root[a], offset[a] = b, difference + y - x
    return True


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
        # A typed participant already carries its titles and deceased status.
        # Do not create a second, apparently living occurrence for its context.
        references = {identity for identity in explicit
                      if not any(m.reference == identity and m.assertion.source.key == observation.source.key
                                 for m in typed_scopes[passage])}
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
    # References and source passages stay fixed while identity groups change.
    # Compute these once per reconstruction, including prose-only mentions.
    mention_names = {}
    mention_scopes = {}
    for handle, mention in mentions.items():
        ref = mention.reference
        mention_names[handle] = names.key(registry[ref]['name'] if ref in registry and registry[ref].get('id') == ref else ref)
        mention_scopes[handle] = (mention.assertion.source.path,
                                 mention.assertion.source.pointer.rsplit('/' + mention.assertion.source.kind + '/', 1)[0],
                                 mention.assertion.historical_date)

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
        return mention_names[handle]

    def given(value):
        first = value.split()[0]
        return first[:-1] if len(first) >= 4 and first[-1:] in {'a', 'e'} else first

    def compatible_names(left, right):
        a, b = left.split(), right.split()
        return given(left) == given(right) and (len(a) == 1 or len(b) == 1 or a[1:] == b[1:])

    def scope(mention):
        return mention_scopes[mention.handle]

    def chronology_conflict(component):
        # An identity whose own sources already conflict (a data conflict on a
        # fixed ID) is not blocked again; pairwise comparisons still apply.
        parts = defaultdict(list)
        for h in component:
            parts[find(h)].append(mentions[h])
        if any(chronology_blocked(part, model.settings, names) for part in parts.values()):
            return False
        return chronology_blocked([mentions[h] for h in component], model.settings, names)

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
        edges, siblings = [], []
        same_named_parents = defaultdict(set)
        same_named_spouses = defaultdict(set)
        for assertion in assertions:
            if assertion.original['type'] not in RELATIONS:
                continue
            left, right = [mapping[m.handle] for m in assertion.mentions]
            if left == right:
                return False
            if assertion.original['type'] == 'parent':
                edges.append((left, right))
                if new is None or right < new:
                    same_named_parents[(right, name(assertion.mentions[0].handle))].add(left)
            elif assertion.original['type'] == 'sibling':
                siblings.append((left, right))
            elif assertion.original['type'] == 'spouse':
                for own, (other, partner) in ((left, (right, assertion.mentions[1])), (right, (left, assertion.mentions[0]))):
                    if new is None or own < new:
                        same_named_spouses[(own, name(partner.handle))].add(other)
        # Same-named parents or spouses of one person should be one person; if
        # they cannot be, the merge that gave that person both of them is wrong.
        for relatives in [*same_named_parents.values(), *same_named_spouses.values()]:
            if len(relatives) > 1:
                union = [h for index in relatives for h in components[index]]
                if len(anchor(union)) > 1 or chronology_conflict(union):
                    return False
        return not cycle_nodes(edges) and generations_consistent(edges, siblings)

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

    # A source's repeated participant references supply local context. All
    # same-name occurrences of one passage form the fewest people the
    # constraints jointly allow; only occurrences grouped together in every
    # such partition are merged.
    local = defaultdict(lambda: defaultdict(list))
    for handle, mention in mentions.items():
        if not anchor([handle]) and mention.field != 'text':
            local[scope(mention)][name(handle)].append(handle)

    def partitions_of(roots, allowed, size, limit=1000):
        """Partitions into exactly `size` pairwise-compatible blocks, or None if too many."""
        result = []
        def assign(index, blocks):
            if len(result) > limit or len(blocks) + len(roots) - index < size:
                return
            if index == len(roots):
                result.append([list(block) for block in blocks])
                return
            root = roots[index]
            for block in blocks:
                if all(allowed[frozenset((member, root))] for member in block):
                    block.append(root)
                    assign(index + 1, blocks)
                    block.pop()
            if len(blocks) < size:
                blocks.append([root])
                assign(index + 1, blocks)
                blocks.pop()
        assign(0, [])
        return None if len(result) > limit else result

    def passage_partitions(name_roots, current_local, limit=2000):
        involved = {root for roots in name_roots for root in roots}
        others = [group for root, group in current_local.items() if root not in involved]
        fixed = [current_local[root] for roots in name_roots if len(roots) == 1 for root in roots]
        variable = [roots for roots in name_roots if len(roots) > 1]
        allowed = []
        for roots in variable:
            rest = [current_local[r] for r in involved if r not in roots]
            allowed.append({frozenset((a, b)): consistent([current_local[a] + current_local[b], *others, *rest,
                                                           *[current_local[r] for r in roots if r not in (a, b)]], 1)
                            for a, b in combinations(roots, 2)})
        cache = {}
        def choices(index, size):
            if (index, size) not in cache:
                cache[index, size] = partitions_of(variable[index], allowed[index], size)
            return cache[index, size]
        checked = 0
        # Fewest people first: stop at the first total with a consistent grouping.
        for total in range(len(variable), sum(map(len, variable)) + 1):
            valid = []
            for sizes in product(*[range(1, len(roots) + 1) for roots in variable]):
                if sum(sizes) != total:
                    continue
                options = [choices(index, size) for index, size in enumerate(sizes)]
                if any(option is None for option in options):
                    return []
                for combination in product(*options):
                    checked += 1
                    if checked > limit:
                        return []
                    blocks = [[h for r in block for h in current_local[r]] for partition in combination for block in partition]
                    if consistent([*blocks, *fixed, *others], len(blocks)):
                        valid.append([set(block) for partition in combination for block in partition])
            if valid:
                return valid
        return []

    for _ in range(len(mentions)):
        current_local = groups()
        local_proposals = []
        for by_name in local.values():
            name_roots = [sorted({find(h) for h in handles}) for _, handles in sorted(by_name.items())]
            if all(len(roots) < 2 for roots in name_roots):
                continue
            partitions = passage_partitions(name_roots, current_local)
            for roots in name_roots:
                for left, right in combinations(roots, 2):
                    if partitions and all(any({left, right} <= block for block in partition) for partition in partitions):
                        first, second = current_local[left][0], current_local[right][0]
                        local_proposals.append((first, second, [mentions[first].assertion.source, mentions[second].assertion.source]))
        if not accept(local_proposals, 'repeated participant within one dated source passage'):
            break

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
    def build_profiles():
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
                category = title_category(title, names)
                profile.titles.setdefault(category, []).append((ref, bounds))
                if category[0] in {'office', 'designation'}:
                    scopes = profile.office_scopes if category[0] == 'office' else profile.designation_places
                    for place in model.places(title):
                        scopes.setdefault(place, []).append((ref, bounds))
            content = mention.assertion.original.get('content', '') if mention.assertion.original['type'] == 'generic' else ''
            model.add_context(profile, ref, bounds, text=content,
                              issuance=mention.assertion.context.get('place', ''), self_names=(name(handle),),
                              personal_claim=mention.assertion.original['type'] == 'generic')
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
        return current, profiles, root_names, context_coverage

    for iteration in range(model.settings['maxRounds']):
        current, profiles, root_names, context_coverage = build_profiles()
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
                record.update(mentions=list(pair), iteration=iteration, **{'pass': 1}, status='below-threshold', reason='below merge probability')
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

    # Second pass: single-passage leftovers attach to the frozen tree through
    # the positions their relationships allow; attachments never support each
    # other and never join two existing identities.
    second = model.settings['secondPass']
    current, profiles, root_names, context_coverage = build_profiles()
    labels = {root: next(iter(anchor(handles)), root_names[root]) for root, handles in current.items()}
    reference = {root for root, handles in current.items()
                 if anchor(handles) or len({scope(mentions[h])[:2] for h in handles}) > 1}
    tree, relations, family_roots = defaultdict(set), defaultdict(list), set()
    factual_parents = defaultdict(list)
    steps = {'parent': ('C', 'P'), 'sibling': ('S', 'S'), 'spouse': ('Sp', 'Sp')}
    for assertion in assertions:
        kind = assertion.original['type']
        if kind not in RELATIONS:
            continue
        a, b = assertion.mentions
        left, right = find(a.handle), find(b.handle)
        family_roots.update((left, right))
        if kind == 'parent' and assertion.source.kind == 'facts':
            factual_parents[left].append((right, assertion))
        if left == right:
            continue
        if kind in steps:
            tree[left].add((steps[kind][0], right))
            tree[right].add((steps[kind][1], left))
        for own, field, other in ((left, a.field, right), (right, b.field, left)):
            if own not in reference and other in reference:
                relations[own].append((assertion, field, other))
    widows = defaultdict(list)
    widow_claim = re.compile(r'^(?:(?:was|is|remained|became)\s+(?:a\s+)?widow(?:er)?\b|'
                            r'(?:was|is)\s+(?:recorded|described|named|mentioned|listed)\b[^.!?;]*\bas\s+(?:a\s+)?widow(?:er)?\b)', re.I)
    for assertion in assertions:
        if assertion.source.kind != 'facts':
            continue
        if assertion.original['type'] == 'spouse':
            a, b = assertion.mentions
            for own, other in ((a, b), (b, a)):
                if other.deceased and not own.deceased:
                    widows[find(own.handle)].append(own)
        elif (assertion.original['type'] == 'generic' and assertion.mentions
              and not assertion.mentions[0].deceased and widow_claim.search(assertion.original['content'])):
            mention = assertion.mentions[0]
            widows[find(mention.handle)].append(mention)
    # A deliberately weaker rule for standalone widow records: one full name
    # may attach to an established family, but no two reference identities join.
    widow_leftovers = {root for root in widows if root not in reference and root not in family_roots
                      and len(root_names[root].split()) >= 2}
    parental_mentions = defaultdict(list)
    established_names = {root_names[root] for root in reference}
    for root, handles in current.items():
        if root in reference or root in family_roots or len(root_names[root].split()) < 2:
            continue
        for handle in handles:
            mention = mentions[handle]
            claim = speculative_parent_claim(mention)
            if not claim:
                continue
            children = set()
            for literal in model.person_references(claim[1]):
                child = names.key(literal)
                # English plural names in "the two X von Ys" still discuss X
                # von Y. This retrieves a name; it never supplies a second child.
                if (child.endswith('s') and child not in established_names and child[:-1] in established_names
                    and re.search(r'\b(?:two|both|several)\s+' + re.escape(literal), claim[1], re.I)):
                    child = child[:-1]
                children.add(child)
            if children:
                parental_mentions[root].append((mention, children))
    paths = {}
    def paths_from(root):
        if root not in paths:
            paths[root] = tree_paths(tree, root, second['maxPathSteps'])
        return paths[root]
    def nearest(assertion, root):
        return max(decay(assertion.bounds, mentions[h].assertion.bounds, model.settings['familyHalfLifeYears']) for h in current[root])
    elder = {'der Ältere', 'der Alte'}
    younger = {'der Jüngere', 'der Junge'}
    second_scores, proposals = {}, []
    for leftover in sorted(set(relations) | widow_leftovers | parental_mentions.keys()):
        if all(mentions[h].field == 'text' for h in current[leftover]):
            continue
        candidates = [root for root in sorted(reference)
                      if given(root_names[root]) == given(root_names[leftover])
                      and all(compatible_names(name(a), name(b)) for a in current[leftover] for b in current[root])]
        weak_only = leftover in widow_leftovers
        attribution_only = leftover in parental_mentions
        if weak_only or attribution_only:
            candidates = [root for root in candidates if root_names[root] == root_names[leftover]]
        scored = {}
        for candidate in candidates:
            record = model.compare(profiles[leftover], profiles[candidate])
            blocks = record.pop('blocks')
            record.pop('substantive')
            added, positioned, contradicted = [], False, False
            if (weak_only and candidate in family_roots
                and len({scope(mentions[h])[:2] for h in current[candidate]}) > 1):
                support = [(own, other) for own in widows[leftover] for other in widows[candidate]
                           if other.assertion.bounds[0] <= own.assertion.bounds[1]]
                if support:
                    own, other = max(support, key=lambda pair: min(reliability(m.assertion.source, model.settings) for m in pair))
                    value = second['widowhoodNameWeight'] * min(reliability(m.assertion.source, model.settings) for m in (own, other))
                    added.append(('weak attachment: same full name and earlier widowhood', value, own.assertion.source))
            family = {f['name'].split(': ', 1)[1] for f in record['features'] if 'family context: ' in f['name']}
            by_relative = {}
            for mention, children in parental_mentions.get(leftover, ()):
                for child, factual in factual_parents[candidate]:
                    if child not in reference or root_names[child] not in children:
                        continue
                    # Identify the actor through independently recorded factual
                    # parentage. The hypothesis itself remains a guess and adds
                    # no relationship. Its tentative wording is not uncertainty
                    # that the source explicitly names this parent and child.
                    source_weight = model.settings['sourceWeights'][mention.assertion.source.path.split('/')[1]]
                    weight = min(source_weight, reliability(factual.source, model.settings))
                    # An exact child ID in the factual relationship is fixed;
                    # uncertain aliases elsewhere in that child's cluster do
                    # not weaken this independently anchored parentage.
                    child_confidence = 1.0 if anchor([factual.mentions[1].handle]) else confidence[child]
                    value = model.settings['sharedRelativeWeight'] * weight * child_confidence
                    if value > by_relative.get(child, (0,))[0]:
                        by_relative[child] = (value, f'factual parentage of {root_names[child]} corroborates speculative mention',
                                              mention.assertion.source)
                    if factual.source.key not in {ref.key for ref in record['sources']}:
                        record['sources'].append(factual.source)
                    for ref in dependencies[child].values():
                        if ref.key not in {source.key for source in record['sources']}:
                            record['sources'].append(ref)
            for assertion, field, relative_root in relations[leftover]:
                term = names.kinship.position(assertion, field)
                found = paths_from(relative_root).get(candidate, set())
                allowed = sorted(path for path in found if term.allowed.contains(path))
                weight = reliability(assertion.source, model.settings)
                label = assertion.original.get('term') or assertion.original['type']
                if allowed:
                    positioned = True
                    if root_names[relative_root] in family:
                        continue  # pass 1 already counted this relative
                    value = (model.settings['sharedRelativeWeight'] * second['specificityFactors'][term.specificity] * weight
                             * confidence[relative_root] * nearest(assertion, candidate))
                    if value > by_relative.get(relative_root, (0,))[0]:
                        by_relative[relative_root] = value, f'kinship position {"".join(allowed[0])} of {labels[relative_root]} ({label})', assertion.source
                elif found and all(term.excludes(path) for path in found):
                    text = f'kinship term {label} excludes position {"".join(sorted(found)[0])} of {labels[relative_root]}'
                    contradicted = True
                    if weight == 1:
                        blocks.append(text)
                    else:
                        added.append((text, -model.settings['deathConflictPenalty'] * weight, assertion.source))
            remaining = model.settings['familyMaxWeight']
            for value, text, source in sorted(by_relative.values(), key=lambda item: (-item[0], item[1])):
                added.append((text, min(value, remaining), source))
                remaining -= min(value, remaining)
            # An age title implies a same-named relative of another generation
            # in that passage; the candidate should sit on the other side of it.
            for h in current[leftover]:
                titles = set(mentions[h].titles)
                offset = 1 if titles & elder else -1 if titles & younger else 0
                if not offset:
                    continue
                namesakes = [root for root in candidates if root != candidate
                             and any(scope(mentions[x])[:2] == scope(mentions[h])[:2] for x in current[root])]
                if any(generation(path) == offset for root in namesakes for path in paths_from(root).get(candidate, ())):
                    added.append(('age-title namesake one generation ' + ('below' if offset > 0 else 'above'),
                                  second['ageTitleNamesakeWeight'] * reliability(mentions[h].assertion.source, model.settings),
                                  mentions[h].assertion.source))
                    break
            scored[candidate] = record, blocks, added, positioned, contradicted
        # Only candidate: one compatible same-named identity in that family,
        # unless another leftover of that name is related to the same family.
        compatible = [c for c, (_, blocks, _, positioned, _) in scored.items() if positioned and not blocks]
        relatives = {relative_root for _, _, relative_root in relations[leftover]}
        competing = any(other != leftover and given(root_names[other]) == given(root_names[leftover])
                     and relatives & {relative_root for _, _, relative_root in relations[other]} for other in relations)
        if len(compatible) == 1 and not competing and not weak_only and not attribution_only:
            source = relations[leftover][0][0].source
            scored[compatible[0]][2].append((f'only compatible candidate near {", ".join(sorted(labels[r] for r in relatives))}',
                                             second['eliminationWeight'] * min(reliability(a.source, model.settings) for a, _, _ in relations[leftover]), source))
        options = []
        for candidate, (record, blocks, added, _, contradicted) in scored.items():
            if not added and not contradicted:
                continue
            for text, value, source in added:
                record['features'].append({'name': text, 'contribution': round(value, 8)})
                if source.key not in {ref.key for ref in record['sources']}:
                    record['sources'].append(source)
            record['logOdds'] = round(record['logOdds'] + sum(value for _, value, _ in added), 8)
            record['probability'] = round(1 / (1 + math.exp(-max(-700, min(700, record['logOdds'])))), 8)
            pair = tuple(sorted((leftover, candidate)))
            record.update(mentions=list(pair), **{'pass': 2}, status='below-threshold', reason='below second-pass merge probability')
            if blocks:
                record.update(status='incompatible', reason='blocked: ' + '; '.join(blocks))
            elif weak_only and sum(not entry[1] for entry in scored.values()) != 1:
                record.update(status='ambiguous', reason='weak widowhood attachment has competing same-name reference identities')
            elif attribution_only and sum(bool(entry[2]) and not entry[1] for entry in scored.values()) != 1:
                record.update(status='ambiguous', reason='speculative mention has competing factual parents with the same names')
            elif record['probability'] >= second['mergeProbability']:
                options.append((record['logOdds'], candidate))
            second_scores[pair] = record
            comparisons[pair] = record
        rivals = sorted((record['logOdds'] for record, blocks, added, _, _ in scored.values() if added and not blocks), reverse=True)
        if options:
            best, candidate = max(options)
            pair = tuple(sorted((leftover, candidate)))
            if len(rivals) > 1 and best - rivals[1] < model.settings['ambiguityLogOddsMargin']:
                second_scores[pair].update(status='ambiguous', reason='competing candidates within the decision margin')
            else:
                proposals.append((leftover, candidate, second_scores[pair]['sources']))
    round_scores = second_scores
    accept(proposals, 'second pass: relationship position, corroborated speculative mention, or weak widowhood attachment')
    for leftover, candidate, _ in proposals:
        pair = tuple(sorted((leftover, candidate)))
        if find(leftover) == find(candidate):
            second_scores[pair].update(status='merged', reason='second-pass probability, margin and cluster constraints passed')
        else:
            second_scores[pair].update(status='incompatible', reason='complete proposed cluster violates identity constraints')

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
