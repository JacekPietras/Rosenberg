"""Source people and contextual linkage beyond the curated registry.

All nodes start as occurrences. Candidate links are proposed against a frozen
round, then checked together; no link can merge distinct registry anchors.
"""

from collections import defaultdict
from datetime import date
import heapq
from itertools import combinations, product
import math
import re

from .constraints import cycle_nodes
from .model import fingerprint, Assertion, Mention, passage_key
from .policy import AGE_TITLES
from .kinship import generation, tree_paths
from .dates import death_interval
from .probability import (ProbabilityModel, Profile, PERSON_NAME, YEAR, chronology, chronology_blocked, cumulative, decay,
                          gap_years, living_span, mention_rank, names_relative, reliability, single_day,
                          speculative_parent_claim, title_category)

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


def reconstruct(assertions, decisions, registry, names, parameters=None, observations=(), progress=None):
    progress = progress or (lambda _stage: None)
    progress('Reconstructing identities and family evidence')
    assertions = list(assertions)
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
        key = passage_key(mention.assertion.source)
        typed_scopes[key].append(mention)
    context_handles = defaultdict(list)
    required = math.log(model.settings['mergeProbability'] / (1 - model.settings['mergeProbability'])) - math.log(model.settings['priorProbability'] / (1 - model.settings['priorProbability']))
    for observation in observations:
        if not observation.bounds:
            continue
        passage = passage_key(observation.source)
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
    membership = defaultdict(lambda: 1.0)
    round_scores = {}
    # References and source passages stay fixed while identity groups change.
    # Compute these once per reconstruction, including prose-only mentions.
    mention_names = {}
    mention_scopes = {}
    for handle, mention in mentions.items():
        ref = mention.reference
        mention_names[handle] = names.key(registry[ref]['name'] if ref in registry and registry[ref].get('id') == ref else ref)
        mention_scopes[handle] = (*passage_key(mention.assertion.source),
                                 mention.assertion.historical_date)
    parents_of_mention = defaultdict(list)

    def index_parents():
        parents_of_mention.clear()
        for assertion in assertions:
            if assertion.original['type'] == 'parent':
                senior, child = assertion.mentions
                sex = names.gender(mention_names[senior.handle])
                if sex:
                    parents_of_mention[child.handle].append((sex, senior.handle))
    index_parents()

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    cached_groups = []

    def groups():
        if not cached_groups:
            result = defaultdict(list)
            for key in mentions:
                result[find(key)].append(key)
            cached_groups.append(result)
        return cached_groups[0]

    def anchor(handles):
        return {mentions[h].reference for h in handles if mentions[h].reference in registry and registry[mentions[h].reference].get('id') == mentions[h].reference}

    def name(handle):
        return mention_names[handle]

    given_memo = {}

    def given(value):
        if value not in given_memo:
            first = value.split()[0]
            given_memo[value] = first[:-1] if len(first) >= 4 and first[-1:] in {'a', 'e'} else first
        return given_memo[value]

    compatible_memo = {}

    def compatible_names(left, right):
        key = left, right
        if key not in compatible_memo:
            a, b = left.split(), right.split()
            compatible_memo[key] = given(left) == given(right) and (len(a) == 1 or len(b) == 1 or a[1:] == b[1:])
        return compatible_memo[key]

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

    def passage_conflict(handles):
        """Same-passage distinctions: opposite ranks, an explicitly deceased and a
        living occurrence, or two separate facts with the same content."""
        ranks, alive, contents = defaultdict(set), defaultdict(set), defaultdict(set)
        for h in handles:
            mention = mentions[h]
            where = scope(mention)
            rank = mention_rank(mention)
            if rank:
                ranks[where].add(rank)
            if mention.field != 'text' and not speculative_parent_claim(mention):
                if mention.deceased:
                    alive[where].add(False)
                elif mention.assertion.original['type'] != 'death' and not names_relative(mention):
                    alive[where].add(True)
            if mention.field == 'person' and mention.assertion.original['type'] == 'generic':
                contents[where, mention.assertion.original['content']].add(mention.assertion.source.key)
        return (any(len(values) > 1 for values in ranks.values()) or any(len(values) > 1 for values in alive.values())
                or any(len(values) > 1 for values in contents.values()))

    def too_old(handles):
        """Impossible for any source type: too long a life or an impossible age."""
        group = [mentions[h] for h in handles]
        if living_span(group, model.settings, names) > model.settings['bestCandidate']['maxLivingSpanYears']:
            return True
        level = cumulative(chronology(group, model.settings, names), 0)
        return 'birth' in level and 'last' in level and (level['last'][0] - level['birth'][0]) / YEAR > model.settings['maxAgeYears']

    def new_too_old(component):
        parts = defaultdict(list)
        for h in component:
            parts[find(h)].append(h)
        return too_old(component) and not any(too_old(part) for part in parts.values())

    def new_passage_conflict(component):
        # Conflicts already inside one existing identity are data problems,
        # reported elsewhere; they must not block every later merge.
        parts = defaultdict(list)
        for h in component:
            parts[find(h)].append(h)
        return passage_conflict(component) and not any(passage_conflict(part) for part in parts.values())

    def could_be_one(left, right, members):
        """Two parent identities (root, mention handle) are or could become one person."""
        (x, a), (y, b) = left, right
        if x == y:
            return True
        if not compatible_names(name(a), name(b)) or len(anchor(members[x] + members[y])) > 1:
            return False
        return not chronology_conflict(members[x] + members[y]) and chronology_allows((members[x], members[y]))

    def different_parent(parts):
        """A person has one father and one mother: records whose fathers (or mothers),
        recorded or inherited, cannot be one person are different people."""
        found = []
        for part in parts:
            seen = defaultdict(dict)
            for h in part:
                for sex, handle in parents_of_mention.get(h, ()):
                    seen[sex].setdefault(find(handle), handle)
            found.append(seen)
        members = None
        def one_person(left, right):
            nonlocal members
            members = members or groups()
            return could_be_one(left, right, members)
        for a, b in combinations(found, 2):
            for sex in sorted(set(a) & set(b)):
                if not any(one_person(x, y) for x in a[sex].items() for y in b[sex].items()):
                    role = 'father' if sex == 'man' else 'mother'
                    listed = lambda side: ', '.join(sorted({name(h) for h in side[sex].values()}))
                    return f'different {role}: {listed(a)} / {listed(b)}'
        return None

    def new_different_parent(component):
        parts = defaultdict(list)
        for h in component:
            parts[find(h)].append(h)
        return different_parent(list(parts.values()))

    relation_assertions = [a for a in assertions if a.original['type'] in RELATIONS and not a.basis]
    static_memo = {}

    def static_consistent(component):
        key = tuple(component)
        if key not in static_memo:
            static_memo[key] = static_check(component)
        return static_memo[key]

    def static_check(component):
        if len(anchor(component)) > 1:
            return False
        forms = {name(h) for h in component}
        if any(not compatible_names(a, b) for a, b in combinations(forms, 2)):
            return False
        by_scope = defaultdict(set)
        for h in component:
            by_scope[scope(mentions[h])].update(mentions[h].titles)
        # Different age designations in one passage name different people.
        return not any(len(titles & AGE_TITLES) > 1 for titles in by_scope.values())

    def consistent(components, new=None):
        # Only proposed components are checked for chronology; unchanged
        # identities cannot block unrelated merges.
        mapping = {h: index for index, component in enumerate(components) for h in component}
        for index, component in enumerate(components):
            if not static_consistent(component):
                return False
            if (new is None or index < new) and (chronology_conflict(component) or new_different_parent(component)
                                                 or new_passage_conflict(component) or new_too_old(component)):
                return False
        edges, siblings = [], []
        same_named_parents = defaultdict(set)
        same_named_spouses = defaultdict(set)
        for assertion in relation_assertions:
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

    def passages(handles):
        return len({scope(mentions[h])[:2] for h in handles})

    def join_membership(component, current, adjacency, scores):
        # A mention's membership confidence is the product of the merge
        # probabilities linking it to the identity's core (registry mention,
        # else the largest part); the cluster minimum is only a summary.
        core = min(component, key=lambda key: (not anchor(current[key]), -passages(current[key]), key))
        for key in component:
            if key == core:
                continue
            estimates = [scores[pair]['probability'] for other in adjacency[key]
                         if (pair := tuple(sorted((key, other)))) in scores]
            factor = max(estimates, default=1.0)
            for h in current[key]:
                membership[h] *= factor

    steps = {'parent': ('C', 'P'), 'sibling': ('S', 'S'), 'spouse': ('Sp', 'Sp')}
    # Paths between two records of one person: both in one sibling group
    # (siblings, shared parent, child of the parent's spouse), both parents of
    # one sibling group, both spouses of one person, or the spouse of X and
    # the other parent of X's child.
    same_role = re.compile(r'^(?:(?:s|pc|pmc)+|c(?:s|pc|pmc)*p|mm|mc(?:s|pc|pmc)*p|c(?:s|pc|pmc)*pm)$')
    letters = {'P': 'p', 'C': 'c', 'S': 's', 'Sp': 'm'}
    def family_tree():
        tree, relations, factual_parents = defaultdict(set), defaultdict(list), defaultdict(list)
        for assertion in assertions:
            kind = assertion.original['type']
            if kind not in RELATIONS or assertion.basis:
                continue
            a, b = assertion.mentions
            left, right = find(a.handle), find(b.handle)
            if kind == 'parent' and assertion.source.kind == 'facts':
                factual_parents[left].append((right, assertion))
            if left == right:
                continue
            if kind in steps:
                tree[left].add((steps[kind][0], right))
                tree[right].add((steps[kind][1], left))
            relations[left].append((assertion, a.field, right))
            relations[right].append((assertion, b.field, left))
        return tree, relations, factual_parents

    def relative_blocks(tree, start):
        """Identities reachable from `start` by a path that makes them a different person."""
        blocked = {}
        def walk(node, path, seen):
            if path and node not in blocked and not same_role.match(''.join(letters[step] for step in path)):
                blocked[node] = 'known relatives: ' + '-'.join(path)
            if len(path) == model.settings['bestCandidate']['maxRelativePathSteps']:
                return
            for step, other in sorted(tree.get(node, ())):
                if other not in seen:
                    walk(other, path + (step,), seen | {other})
        walk(start, (), {start})
        return blocked

    def known_relatives(component, current):
        """Two parts of a proposed identity that the tree already relates as different people."""
        if len(component) < 2:
            return False
        tree = family_tree()[0]
        return any(other in relative_blocks(tree, key) for key in component for other in component if other != key)

    def accept(proposals, reason, scores=None, strict=False):
        scores = round_scores if scores is None else scores
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
            if not negative_pair and consistent([joined, *other], 1) and not known_relatives(component, current):
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
            if not consistent(partitions, len(batch)) and strict:
                # Unweighted merges never choose between conflicting groupings:
                # keep only components that conflict with no other component.
                def together(items):
                    used = set().union(*items)
                    parts = [[h for key in item for h in current[key]] for item in items]
                    parts += [handles for key, handles in current.items() if key not in used]
                    return consistent(parts, len(items))
                kept = [c for c in batch if all(together([c, other]) for other in batch if other is not c)]
                batch = kept if together(kept) else []
            elif not consistent(partitions, len(batch)):
                # Keep every component that stays consistent, in a fixed order.
                kept = []
                for component in sorted(batch, key=min):
                    trial = [*kept, component]
                    used = set().union(*trial)
                    parts = [[h for key in item for h in current[key]] for item in trial]
                    parts += [handles for key, handles in current.items() if key not in used]
                    if consistent(parts, len(trial)):
                        kept.append(component)
                batch = kept
            for component in batch:
                joined = sorted(h for key in component for h in current[key])
                root, refs = min(component), {}
                for key in component:
                    refs.update(dependencies[key])
                    refs.update(support[key])
                join_membership(component, current, adjacency, scores)
                cached_groups.clear()
                for key in component:
                    parent[key] = root
                dependencies[root].update(refs)
                confidence[root] = min(membership[h] for h in joined)
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
            cached_groups.clear()
            parent[handle] = handles[0]

    # Pass 0: normalize kinship variants before grouping relationships.
    # Source assertions retain their verbatim terms.
    kin_terms = {a.source.key: names.kinship.canonical(a.original.get('term', '')) for a in assertions}

    # Pass 0: within one document file, or one book, notes or image section,
    # occurrences with the same name and the same titles (or both untitled)
    # are one person, whatever their dates, unless a block separates them.
    def section(mention):
        source = mention.assertion.source
        if source.path.startswith('data/documents/'):
            return source.path,
        return passage_key(source)

    def title_key(mention):
        return frozenset(title_category(title, names) for title in mention.titles)

    def chronology_allows(handles):
        left, right = handles
        profiles = [Profile(list(side), [mentions[h] for h in side]) for side in (left, right)]
        blocks = model.compare(*profiles)['hardBlocks']
        return not any(block.startswith(('impossible age', 'mention after', 'incompatible death', 'living mentions'))
                       for block in blocks)

    same_section = defaultdict(list)
    for handle, mention in mentions.items():
        if mention.field != 'text' and not anchor([handle]):
            same_section[section(mention), name(handle), title_key(mention)].append(handle)
    zero_proposals = []
    for key in sorted(same_section, key=str):
        handles = sorted(same_section[key], key=lambda h: (mentions[h].assertion.bounds, h))
        if len({find(h) for h in handles}) < 2:
            continue
        clusters = []
        current = groups()
        for handle in handles:
            fitting = []
            for cluster in clusters:
                joined = sorted({h for x in (*cluster, handle) for h in current[find(x)]})
                others = [group for root, group in current.items() if root not in {find(x) for x in (*cluster, handle)}]
                if (consistent([joined, *others], 1)
                        and not known_relatives({find(x) for x in (*cluster, handle)}, current)
                        and chronology_allows(([h for x in cluster for h in current[find(x)]], current[find(handle)]))):
                    fitting.append(cluster)
            if len(fitting) == 1:
                fitting[0].append(handle)
            elif not fitting:
                clusters.append([handle])
            # An occurrence that fits several people stays for the later stages.
        for cluster in clusters:
            zero_proposals += [(cluster[0], other, [mentions[cluster[0]].assertion.source, mentions[other].assertion.source])
                               for other in cluster[1:]]
    accept(zero_proposals, 'same name and titles in one document or section', {}, strict=True)

    # A source's repeated participant references supply local context. All
    # same-name occurrences of one passage form the fewest people the
    # constraints jointly allow. Among those groupings, the ones whose groups
    # agree best on titles win; occurrences together in all winners merge.
    local = defaultdict(lambda: defaultdict(list))
    for handle, mention in mentions.items():
        if not anchor([handle]) and mention.field != 'text':
            local[scope(mention)][name(handle)].append(handle)

    def partitions_of(roots, allowed, size, limit=20000):
        """Partitions into exactly `size` pairwise-compatible blocks (the first `limit` found)."""
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
        return result[:limit]

    def agreement_keys(handles):
        keys = set()
        for h in handles:
            mention = mentions[h]
            rank = mention_rank(mention)
            if rank:
                keys.add(('rank', rank))
            for title in mention.titles:
                category = title_category(title, names)
                if category[0] in {'office', 'designation', 'age'}:
                    keys.add(category)
            if mention.deceased:
                keys.add(('deceased', ''))
            if mention.assertion.original['type'] == 'death':
                keys.add(('death record', ''))
        return keys

    def agreement(blocks):
        # Shared ranks, offices, designations or age titles, and a death record
        # grouped with an explicitly deceased occurrence, support a grouping.
        score = 0
        for block in blocks:
            keys = [agreement_keys(group) for group in block]
            for a, b in combinations(keys, 2):
                plain = {key for key in a & b if key[0] not in {'deceased', 'death record'}}
                death = ('death record', '') in a and ('deceased', '') in b or ('death record', '') in b and ('deceased', '') in a
                score += bool(plain) + death
        return score * model.settings['passageTitleAgreementWeight']

    def passage_partitions(name_roots, current_local, limit=200000):
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
                for combination in product(*options):
                    checked += 1
                    if checked > limit:
                        break
                    blocks = [[h for r in block for h in current_local[r]] for partition in combination for block in partition]
                    if consistent([*blocks, *fixed, *others], len(blocks)):
                        grouping = [set(block) for partition in combination for block in partition]
                        valid.append((agreement([[current_local[r] for r in block] for block in grouping]), grouping))
            if valid:
                best = max(score for score, _ in valid)
                return [grouping for score, grouping in valid if score == best]
        return []

    stage1_tied = set()
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
                    together = [any({left, right} <= block for block in partition) for partition in partitions]
                    if partitions and all(together):
                        first, second = current_local[left][0], current_local[right][0]
                        local_proposals.append((first, second, [mentions[first].assertion.source, mentions[second].assertion.source]))
                    elif any(together):
                        # Left apart only because the best groupings disagree.
                        stage1_tied.update(current_local[left] + current_local[right])
        if not accept(local_proposals, 'repeated participant within one dated source passage', {}):
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
                     tuple(m.titles for m in assertion.mentions), kin_terms[assertion.source.key])
        duplicates[signature].append(assertion)
    proposals = []
    for copies in duplicates.values():
        for first, second in zip(copies, copies[1:]):
            for left, right in zip(first.mentions, second.mentions):
                proposals.append((left.handle, right.handle, [first.source, second.source]))
    accept(proposals, 'same dated relationship in a specifically cited attestation')

    def retrospective(mention):
        """A title of a deceased person describes the years before the death bound."""
        died = death_interval(mention) if mention.assertion.original['type'] == 'death' else None
        if not mention.deceased and not died:
            return None
        end = died[1] if died else mention.assertion.bounds[1]
        start = date.fromordinal(max(1, end.toordinal() - round(model.settings['retrospectiveLookBackYears'] * YEAR)))
        return start, end

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
            rank = mention_rank(mention)
            if rank:
                profile.ranks.append((rank, ref, bounds, scope(mention)))
            for title in mention.titles:
                category = title_category(title, names)
                attested = retrospective(mention) or bounds
                profile.titles.setdefault(category, []).append((ref, attested))
                if category[0] in {'office', 'designation'}:
                    scopes = profile.office_scopes if category[0] == 'office' else profile.designation_places
                    for place in model.places(title):
                        scopes.setdefault(place, []).append((ref, attested))
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
            passage = passage_key(observation.source)
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
        def relative(profile_root, relative_root, role, source_assertions, relative_confidence=1.0, context_refs=()):
            profile, other = profiles[profile_root], profiles[relative_root]
            relative_name = root_names[relative_root]
            linked = 1.0 if other.anchored and relative_confidence == 1.0 else relative_confidence
            for token, value in (((role, relative_root, relative_name, other.anchored), linked), ((role, '', relative_name, False), 1.0)):
                profile.relatives.setdefault(token, []).extend((a.source, a.bounds, value) for a in source_assertions)
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
            if not assertion.basis:
                profiles[left].distinctions.setdefault(right, []).append(assertion.source)
                profiles[right].distinctions.setdefault(left, []).append(assertion.source)
            for own, other, direction, other_mention in ((left, right, 'out', b), (right, left, 'in', a)):
                role = kind, direction if kind == 'parent' else '', kin_terms[assertion.source.key]
                relative(own, other, role, [assertion], membership[other_mention.handle])
                if kind == 'spouse':
                    relative(own, other, ('family context', '', ''), [assertion], membership[other_mention.handle])
            if kind == 'parent':
                parents[right][left].append(assertion)
        # A child is born at most `posthumousBirthYears` after a parent's death;
        # the bound feeds the child's ordinary age rules and penalties.
        deaths, lives = {}, {}
        for assertion in assertions:
            if assertion.original['type'] != 'parent' or assertion.basis:
                continue
            father, child = (find(m.handle) for m in assertion.mentions)
            if father == child:
                continue
            if father not in deaths:
                deaths[father] = [(value, level['deathEnd']) for value, level in
                                  chronology(profiles[father].mentions, model.settings, names).items() if 'deathEnd' in level]
            for value, (end, source) in deaths[father]:
                weight = min(value, reliability(assertion.source, model.settings))
                profiles[child].derived.append((weight, end + round(model.settings['posthumousBirthYears'] * YEAR), source))
            if child not in lives:
                lives[child] = [(value, level['last']) for value, level in
                                chronology(profiles[child].mentions, model.settings, names).items() if 'last' in level]
            for value, (last, source) in lives[child]:
                profiles[father].children.append((min(value, reliability(assertion.source, model.settings)), last, source))
        for child, co_parents in parents.items():
            for left, right in combinations(co_parents, 2):
                # Repeated attestations of a same-named parent are not evidence
                # that those unresolved parent records are different partners.
                if compatible_names(root_names[left], root_names[right]):
                    continue
                basis = [*co_parents[left], *co_parents[right]]
                child_confidence = max(membership[a.mentions[1].handle] for a in basis)
                relative(left, right, ('family context', '', ''), basis, child_confidence, dependencies[child].values())
                relative(right, left, ('family context', '', ''), basis, child_confidence, dependencies[child].values())
        return current, profiles, root_names, context_coverage

    def same_named_relatives():
        """Same-name people in one role to one identity are one person unless blocked."""
        current = groups()
        found = defaultdict(dict)
        for assertion in assertions:
            kind = assertion.original['type']
            if kind not in {'parent', 'sibling', 'spouse'}:
                continue
            a, b = assertion.mentions
            for own, other in ((a, b), (b, a)):
                if membership[own.handle] < model.settings['mergeProbability']:
                    continue
                role = ('child' if own is a else 'parent') if kind == 'parent' else kind
                own_root, other_root = find(own.handle), find(other.handle)
                if own_root != other_root:
                    found[own_root, role, given(name(other.handle))].setdefault(other_root, []).append(assertion.source)
        proposals = []
        for _, roots in sorted(found.items()):
            for left, right in combinations(sorted(roots), 2):
                if all(compatible_names(name(x), name(y)) for x in current[left] for y in current[right]):
                    proposals.append((current[left][0], current[right][0], [*roots[left], *roots[right]]))
        return accept(proposals, 'same-named relatives of one identity', {})

    inferred_bases = set()

    def shared_fathers():
        """A same-surname sibling shares an identity's same-surname father; mothers may differ.
        The inferred father only adds evidence and lets father records join; it never blocks."""
        current = groups()
        def surname(root):
            forms = {tuple(name(h).split()[1:]) for h in current[root]} - {()}
            return next(iter(forms)) if len(forms) == 1 else None
        def structure():
            edges, siblings = [], []
            for a in assertions:
                if a.original['type'] in {'parent', 'sibling'}:
                    pair = tuple(find(m.handle) for m in a.mentions)
                    (edges if a.original['type'] == 'parent' else siblings).append(pair)
            return not cycle_nodes(edges) and generations_consistent(edges, siblings)
        parents_of = defaultdict(list)
        for a in assertions:
            if a.original['type'] == 'parent':
                parents_of[find(a.mentions[1].handle)].append(a)
        valid = structure()
        added = 0
        for sibling in [a for a in assertions if a.original['type'] == 'sibling']:
            for known, other in (sibling.mentions, sibling.mentions[::-1]):
                x, y = find(known.handle), find(other.handle)
                family = surname(x)
                if x == y or not family or surname(y) != family:
                    continue
                for parent in [p for p in parents_of[x] if not p.basis]:
                    key = parent.source.key, sibling.source.key, other.handle
                    father_handle = parent.mentions[0].handle
                    father = find(father_handle)
                    if (key in inferred_bases or father == y or surname(father) != family
                            or names.gender(root_names_of(current[father])) != 'man'):
                        continue
                    fathers = {find(p.mentions[0].handle) for p in parents_of[y]}
                    if father in fathers:
                        continue
                    paternal = [f for f in fathers if names.gender(root_names_of(current[f])) == 'man']
                    if any(given(root_names_of(current[f])) != given(root_names_of(current[father])) for f in paternal):
                        continue  # a different recorded father: half-siblings or a wrong identity
                    if not all(could_be_one((f, current[f][0]), (father, father_handle), current) for f in paternal):
                        continue
                    weaker = min((parent, sibling), key=lambda a: (a.source.kind == 'facts', reliability(a.source, model.settings)))
                    father_mention = parent.mentions[0]
                    inferred = Assertion(weaker.source, {'type': 'parent', 'person': father_mention.reference, 'of': other.reference},
                                         weaker.historical_date, weaker.bounds, weaker.context, [father_mention, other], (parent, sibling))
                    assertions.append(inferred)
                    if valid and not structure():
                        assertions.pop()
                        inferred_bases.add(key)
                        continue
                    inferred_bases.add(key)
                    sex = names.gender(name(father_mention.handle))
                    parents_of_mention[other.handle].append((sex, father_mention.handle))
                    parents_of[y].append(inferred)
                    added += 1
        return added

    def root_names_of(handles):
        return min((name(h) for h in handles), key=lambda value: (-len(value.split()), -len(value), value))

    def withdraw_inferred():
        """Drop inferred fathers that later merges contradict: a self-parent, a cycle,
        a generation conflict, or a second father who cannot be the same person."""
        members = groups()
        recorded = [a for a in assertions if not a.basis and a.original['type'] in {'parent', 'sibling'}]
        edges = [tuple(find(m.handle) for m in a.mentions) for a in recorded if a.original['type'] == 'parent']
        siblings = [tuple(find(m.handle) for m in a.mentions) for a in recorded if a.original['type'] == 'sibling']
        fathers = defaultdict(dict)
        for a in recorded:
            if a.original['type'] == 'parent' and names.gender(name(a.mentions[0].handle)) == 'man':
                fathers[find(a.mentions[1].handle)].setdefault(find(a.mentions[0].handle), a.mentions[0].handle)
        valid = not cycle_nodes(edges) and generations_consistent(edges, siblings)
        withdrawn = set()
        for a in [a for a in assertions if a.basis]:
            pair = father, child = tuple(find(m.handle) for m in a.mentions)
            own = father, a.mentions[0].handle
            if (father == child or not all(could_be_one(own, other, members) for other in fathers[child].items())
                    or valid and (cycle_nodes([*edges, pair]) or not generations_consistent([*edges, pair], siblings))):
                withdrawn.add(id(a))
            else:
                edges.append(pair)
                fathers[child].setdefault(father, a.mentions[0].handle)
        if withdrawn:
            assertions[:] = [a for a in assertions if id(a) not in withdrawn]
            index_parents()

    def family_closure():
        withdraw_inferred()
        return shared_fathers() + same_named_relatives()

    progress('Pass 3: closing initially known family relationships')
    family_closure()
    for iteration in range(model.settings['maxRounds']):
        current, profiles, root_names, context_coverage = build_profiles()
        progress(f'Pass 3 round {iteration + 1}: comparing {len(current)} identities')
        buckets = defaultdict(list)
        for root in current:
            buckets[given(root_names[root])].append(root)
        round_scores, options = {}, defaultdict(list)
        compared_pairs = 0
        for roots in buckets.values():
            for left, right in combinations(roots, 2):
                if not all(compatible_names(name(a), name(b)) for a in current[left] for b in current[right]):
                    continue
                compared_pairs += 1
                if compared_pairs % 5000 == 0:
                    progress(f'Pass 3 round {iteration + 1}: compared {compared_pairs:,} compatible identity pairs')
                record = model.compare(profiles[left], profiles[right])
                blocks = record.pop('blocks')
                record.pop('hardBlocks')
                if not record.pop('substantive'):
                    continue
                pair = tuple(sorted((left, right)))
                record.update(mentions=list(pair), iteration=iteration, stage=3, status='below-threshold', reason='below merge probability')
                round_scores[pair] = record
                comparisons[pair] = record
                if len(anchor([*current[left], *current[right]])) > 1:
                    record.update(status='incompatible', reason='distinct confirmed registry IDs')
                    continue
                conflict = different_parent([current[left], current[right]])
                if conflict:
                    blocks.append(conflict)
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
        count += family_closure()
        progress(f'Pass 3 round {iteration + 1} complete: {count} merges; {len(comparisons)} comparisons recorded')
        if not count:
            break

    # Stage 4: every identity joins its most probable same-name identity unless
    # a hard block forbids it. Thresholds above only decided which merges came
    # first; here a join needs real evidence, not a probability threshold.
    best_settings = model.settings['bestCandidate']
    second = model.settings['secondPass']
    prior_log_odds = math.log(model.settings['priorProbability'] / (1 - model.settings['priorProbability']))
    widow_claim = re.compile(r'^(?:(?:was|is|remained|became)\s+(?:a\s+)?widow(?:er)?\b|'
                             r'(?:was|is)\s+(?:recorded|described|named|mentioned|listed)\b[^.!?;]*\bas\s+(?:a\s+)?widow(?:er)?\b)', re.I)
    tied_roots = set()
    possible = {}

    def time_gap(left, right):
        hull = lambda handles: (min(mentions[h].assertion.bounds[0] for h in handles), max(mentions[h].assertion.bounds[1] for h in handles))
        return gap_years(hull(left), hull(right))

    progress('Pass 4: joining each identity to its best supported candidate')
    for stage_round in range(len(mentions)):
        current, profiles, root_names, context_coverage = build_profiles()
        if stage_round == 0 or stage_round % 10 == 0:
            progress(f'Pass 4 round {stage_round + 1}: comparing {len(current)} identities')
        labels = {root: next(iter(anchor(handles)), root_names[root]) for root, handles in current.items()}
        reference = {root for root, handles in current.items() if anchor(handles) or passages(handles) > 1}
        tree, relations, factual_parents = family_tree()
        family_roots = set(relations)
        typed = {root for root, handles in current.items() if any(mentions[h].field != 'text' for h in handles)}
        tied_roots = {root for root in typed if passages(current[root]) == 1 and stage1_tied & set(current[root])}
        widows = defaultdict(list)
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
                widows[find(assertion.mentions[0].handle)].append(assertion.mentions[0])
        parental_mentions = defaultdict(list)
        established_names = {root_names[root] for root in reference}
        for root, handles in current.items():
            if root in reference or root in family_roots or len(root_names[root].split()) < 2:
                continue
            for handle in handles:
                claim = speculative_parent_claim(mentions[handle])
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
                    parental_mentions[root].append((mentions[handle], children))
        paths = {}
        def paths_from(root):
            if root not in paths:
                paths[root] = tree_paths(tree, root, second['maxPathSteps'])
            return paths[root]
        passage_memo = {}
        def passage_set(root):
            if root not in passage_memo:
                passage_memo[root] = {scope(mentions[x])[:2] for x in current[root]}
            return passage_memo[root]
        relative_memo = {}
        def relative_block(root, candidate):
            if root not in relative_memo:
                relative_memo[root] = relative_blocks(tree, root)
            return relative_memo[root].get(candidate)
        def nearest(assertion, root):
            return max(decay(assertion.bounds, mentions[h].assertion.bounds, model.settings['familyHalfLifeYears']) for h in current[root])
        buckets = defaultdict(list)
        for root in sorted(typed):
            buckets[given(root_names[root])].append(root)
        base = {}
        compared_pairs = 0
        for roots in buckets.values():
            for left, right in combinations(roots, 2):
                if all(compatible_names(name(a), name(b)) for a in current[left] for b in current[right]):
                    compared_pairs += 1
                    if compared_pairs % 5000 == 0:
                        progress(f'Pass 4 round {stage_round + 1}: compared {compared_pairs:,} compatible identity pairs')
                    base[left, right] = base[right, left] = model.compare(profiles[left], profiles[right])

        def score(root, candidate):
            """Directional record: shared evidence plus the root's own kinship positions."""
            record = {key: (list(value) if isinstance(value, list) else value) for key, value in base[root, candidate].items()}
            record['features'] = [dict(f) for f in record['features']]
            blocks = list(record.pop('hardBlocks'))
            record.pop('blocks')
            record.pop('substantive')
            if len(anchor([*current[root], *current[candidate]])) > 1:
                blocks.append('distinct confirmed registry IDs')
            conflict = different_parent([current[root], current[candidate]])
            if conflict:
                blocks.append(conflict)
            known = relative_block(root, candidate)
            if known:
                blocks.append(known)
            added = []
            family = {f['name'].split(': ', 1)[1] for f in record['features'] if 'family context: ' in f['name']}
            by_relative = {}
            positioned = False
            for assertion, field, relative_root in relations[root]:
                if relative_root == candidate:
                    continue
                term = names.kinship.position(assertion, field)
                found = paths_from(relative_root).get(candidate, set())
                allowed = sorted(path for path in found if term.allowed.contains(path))
                weight = reliability(assertion.source, model.settings)
                label = assertion.original.get('term') or assertion.original['type']
                if allowed:
                    positioned = True
                    if root_names[relative_root] in family:
                        continue  # the shared-relative feature already counts it
                    relative_mention = assertion.mentions[1] if field == 'person' else assertion.mentions[0]
                    value = (model.settings['sharedRelativeWeight'] * second['specificityFactors'][term.specificity] * weight
                             * membership[relative_mention.handle] * nearest(assertion, candidate))
                    if value > by_relative.get(relative_root, (0,))[0]:
                        by_relative[relative_root] = value, f'kinship position {"".join(allowed[0])} of {labels[relative_root]} ({label})', assertion.source
                elif found and all(term.excludes(path) for path in found):
                    blocks.append(f'kinship term {label} excludes position {"".join(sorted(found)[0])} of {labels[relative_root]}')
            remaining = model.settings['familyMaxWeight']
            for value, text, source in sorted(by_relative.values(), key=lambda item: (-item[0], item[1])):
                added.append((text, min(value, remaining), source))
                remaining -= min(value, remaining)
            # An age title implies a same-named relative of another generation
            # in that passage; the candidate should sit on the other side of it.
            for h in current[root]:
                titles = set(mentions[h].titles)
                age_classes = {title_category(title, names)[1] for title in titles
                               if title_category(title, names)[0] == 'age'}
                offset = 1 if 'older' in age_classes else -1 if 'younger' in age_classes else 0
                if not offset:
                    continue
                passage = scope(mentions[h])[:2]
                namesakes = [other for other in buckets[given(root_names[root])] if other not in (root, candidate)
                             and passage in passage_set(other)]
                if any(generation(path) == offset for other in namesakes for path in paths_from(other).get(candidate, ())):
                    added.append(('age-title namesake one generation ' + ('below' if offset > 0 else 'above'),
                                  second['ageTitleNamesakeWeight'] * reliability(mentions[h].assertion.source, model.settings),
                                  mentions[h].assertion.source))
                    break
            # A standalone widow record and an established family with earlier
            # widowhood under the same full name.
            if (root not in family_roots and root in widows and root_names[root] == root_names[candidate]
                    and candidate in family_roots and passages(current[candidate]) > 1):
                support = [(own, other) for own in widows[root] for other in widows[candidate]
                           if other.assertion.bounds[0] <= own.assertion.bounds[1]]
                if support:
                    own, other = max(support, key=lambda pair: min(reliability(m.assertion.source, model.settings) for m in pair))
                    value = second['widowhoodNameWeight'] * min(reliability(m.assertion.source, model.settings) for m in (own, other))
                    added.append(('weak attachment: same full name and earlier widowhood', value, own.assertion.source))
            # A speculative "may have been the parent of X" corroborated by
            # independently recorded factual parentage of X.
            if root_names[root] == root_names[candidate]:
                corroborated = {}
                for mention, children in parental_mentions.get(root, ()):
                    for child, factual in factual_parents[candidate]:
                        if child not in reference or root_names[child] not in children:
                            continue
                        source_weight = model.settings['sourceWeights'][mention.assertion.source.path.split('/')[1]]
                        weight = min(source_weight, reliability(factual.source, model.settings))
                        child_confidence = 1.0 if anchor([factual.mentions[1].handle]) else membership[factual.mentions[1].handle]
                        value = model.settings['sharedRelativeWeight'] * weight * child_confidence
                        if value > corroborated.get(child, (0,))[0]:
                            corroborated[child] = (value, f'factual parentage of {root_names[child]} corroborates speculative mention',
                                                   mention.assertion.source)
                        if factual.source.key not in {ref.key for ref in record['sources']}:
                            record['sources'].append(factual.source)
                added.extend((text, value, source) for value, text, source in corroborated.values())
            for text, value, source in added:
                record['features'].append({'name': text, 'contribution': round(value, 8)})
                if source.key not in {ref.key for ref in record['sources']}:
                    record['sources'].append(source)
            record['logOdds'] = round(record['logOdds'] + sum(value for _, value, _ in added), 8)
            record['probability'] = round(1 / (1 + math.exp(-max(-700, min(700, record['logOdds'])))), 8)
            return record, blocks, positioned

        heap, orders, records, directed, ties = [], {}, {}, {}, {}
        for root in sorted(typed):
            candidates = [other for other in buckets[given(root_names[root])] if other != root and (root, other) in base]
            scored = {candidate: score(root, candidate) for candidate in candidates}
            # Only candidate: one unblocked identity in an allowed kinship position.
            positioned = [c for c, (_, blocks, ok) in scored.items() if ok and not blocks]
            if len(positioned) == 1 and relations[root]:
                record = scored[positioned[0]][0]
                value = second['eliminationWeight'] * min(reliability(a.source, model.settings) for a, _, _ in relations[root])
                record['features'].append({'name': 'only compatible candidate in the family', 'contribution': round(value, 8)})
                record['logOdds'] = round(record['logOdds'] + value, 8)
                record['probability'] = round(1 / (1 + math.exp(-max(-700, min(700, record['logOdds'])))), 8)
            unblocked = {c: record for c, (record, blocks, _) in scored.items() if not blocks}
            total = sum(math.exp(min(700, record['logOdds'])) for record in unblocked.values())
            eligible = []
            for candidate, (record, blocks, _) in sorted(scored.items()):
                pair = tuple(sorted((root, candidate)))
                net = record['logOdds'] - prior_log_odds
                positive = [f for f in record['features'] if f['contribution'] > 0 and not f['name'].startswith('rank title')]
                identifying = any('family context:' in f['name'] or 'office title:' in f['name'] or 'designation title:' in f['name']
                                  or f['name'].startswith(('kinship position', 'factual parentage', 'weak attachment'))
                                  for f in positive)
                partial_name = any((len(name(a).split()) == 1) != (len(name(b).split()) == 1)
                                   for a in current[root] for b in current[candidate])
                record.update(mentions=list(pair), stage=4, iteration=stage_round)
                if blocks:
                    record.update(status='incompatible', reason='blocked: ' + '; '.join(blocks))
                elif net < best_settings['minJoinEvidence'] or not positive:
                    record.update(status='below-threshold', reason='not enough evidence for a join')
                elif partial_name and not identifying:
                    record.update(status='incompatible', reason='an omitted surname requires family or identifying-title support; shared geography and associates are insufficient')
                else:
                    record.update(status='below-threshold', reason='a stronger candidate was chosen')
                    eligible.append(candidate)
                record['share'] = round(math.exp(min(700, record['logOdds'])) / (1 + total), 8) if not blocks else 0.0
                directed[root, candidate] = record
                worth = any(f['contribution'] > 0 for f in record['features']) or blocks and not blocks[0].startswith('impossible age')
                if worth and record['logOdds'] >= records.get(pair, {'logOdds': -math.inf})['logOdds']:
                    records[pair] = record
                if not blocks and record['probability'] >= model.settings['possibleSameDisplayProbability']:
                    possible[pair] = record['probability']
            eligible.sort(key=lambda c: (-scored[c][0]['logOdds'], c))
            if not eligible:
                continue
            top = scored[eligible[0]][0]['logOdds']
            tied = [c for c in eligible if top - scored[c][0]['logOdds'] < best_settings['attachmentTieLogOdds']]
            chosen = tied[0]
            if len(tied) > 1:
                chosen = None
                if root not in tied_roots:
                    has_family = [c for c in tied if any(f['contribution'] > 0 and ('family context' in f['name'] or f['name'].startswith('kinship position'))
                                                         for f in scored[c][0]['features'])]
                    if len(has_family) == 1:
                        chosen = has_family[0]
                    else:
                        pool = has_family or tied
                        gaps = {c: time_gap(current[root], current[c]) for c in pool}
                        nearest_gap = min(gaps.values())
                        if sum(gap == nearest_gap for gap in gaps.values()) == 1:
                            chosen = min(gaps, key=gaps.get)
                if chosen is None:
                    ties[root] = set(tied)
                    for c in tied:
                        pair = tuple(sorted((root, c)))
                        scored[c][0].update(status='ambiguous', reason='tied with another candidate')
                        records[pair] = scored[c][0]
                        possible[pair] = scored[c][0]['probability']
                    continue
            orders[root] = [chosen] + [c for c in eligible if c not in tied]
            heapq.heappush(heap, (-scored[chosen][0]['logOdds'], root, chosen, 0))
        comparisons.update(records)
        joined, touched = 0, set()
        while heap:
            _, root, candidate, index = heapq.heappop(heap)
            left, right = find(root), find(candidate)
            def retry():
                if index + 1 < len(orders[root]):
                    following = orders[root][index + 1]
                    heapq.heappush(heap, (-directed[root, following]['logOdds'], root, following, index + 1))
            if left == right or left in touched or right in touched:
                continue  # scored against an identity that changed; next round
            if root in ties.get(candidate, ()):
                retry()  # the candidate cannot choose between this identity and another
                continue
            live = groups()
            union = sorted(live[left] + live[right])
            others = [handles for key, handles in live.items() if key not in (left, right)]
            if (len(anchor(union)) > 1 or relative_blocks(family_tree()[0], left).get(right)
                    or not consistent([union, *others], 1)):
                retry()
                continue
            pair = tuple(sorted((root, candidate)))
            record = directed[root, candidate]
            comparisons[pair] = record
            share = record['share']
            # The record that joins carries the uncertainty of the choice.
            moving = left if not anchor(live[left]) and (anchor(live[right]) or root == left) else right
            for h in live[moving]:
                membership[h] *= share
            top_root = min(left, right)
            cached_groups.clear()
            parent[left if top_root == right else right] = top_root
            touched.update((left, right))
            refs = {**dependencies[left], **dependencies[right], **{ref.key: ref for ref in record['sources']}}
            dependencies[top_root].update(refs)
            confidence[top_root] = min(membership[h] for h in union)
            record.update(status='merged', reason=f'best unblocked candidate (share {share:.0%})')
            possible.pop(pair, None)
            links.append({'reason': 'best unblocked candidate', 'mentions': union,
                          'sources': [refs[key].export() for key in sorted(refs)]})
            joined += 1
        joined += family_closure()
        progress(f'Pass 4 round {stage_round + 1} complete: {joined} merges; {len(comparisons)} comparisons recorded')
        if not joined:
            break
    progress('Exporting reconstructed identities and relationships')
    withdraw_inferred()
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
        key = kind, left, right, kin_terms[assertion.source.key]
        if assertion.basis and (key in edges or left == right):
            continue  # a recorded relationship needs no inferred derivation
        basis = assertion.basis or (assertion,)
        support = {a.source.key: a.source for a in basis}
        for a in basis:
            for mention in a.mentions:
                if not anchor([mention.handle]):
                    support.update(dependencies[find(mention.handle)])
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
                      'assertionWeight': min(reliability(a.source, model.settings) for a in basis),
                      'endpointProbability': None if 'source' in methods else min(confidence[find(m.handle)] if not anchor([m.handle]) else 1.0 for m in assertion.mentions),
                      'sources': [support[value].export() for value in sorted(support)],
                      **({'inference': 'sibling'} if assertion.basis else {})}
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
    # Candidates that could not be decided (ties, or likely but not chosen)
    # are shown as possibly the same person, never merged.
    possibly = defaultdict(dict)
    for (left, right), probability in possible.items():
        one, other = keys[left], keys[right]
        if one != other and one in participants and other in participants:
            for x, y in ((one, other), (other, one)):
                possibly[x][y] = max(probability, possibly[x].get(y, 0))
    for node in nodes:
        if possibly.get(node['key']):
            node['possiblySame'] = [{'key': key, 'probability': round(value, 8)} for key, value in sorted(possibly[node['key']].items())]
    return {'nodes': [node for node in nodes if node['key'] in participants],
            'relationships': [edges[key] for key in sorted(edges)], 'links': links,
            'comparisons': exported_comparisons, 'contextCoverage': context_coverage,
            'nameFrequencies': model.background}
