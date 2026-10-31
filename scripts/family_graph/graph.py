"""Build independently reproducible evidence views without registry genealogy."""

from collections import defaultdict
from .constraints import cycle_edges, cycle_nodes
from .dates import compatible_deaths
from .model import BuildResult, Candidate, IdentityDecision, Relationship, fingerprint
from .names import Names
from .probability import chronology_blocked, parameters
from .policy import OFFICE_RULES, SEARCH_LIMIT
from .resolve import resolve
from .scoring import anchor_profiles, make_candidates
from .reconstruction import reconstruct

RELATIONS = {'parent', 'spouse', 'sibling', 'kin'}


def build(inputs, include_guesses=False, rules=OFFICE_RULES, search_limit=SEARCH_LIMIT):
    assertions = [assertion for assertion in inputs.assertions if include_guesses or assertion.source.kind == 'facts']
    names = Names(inputs.names, inputs.places, inputs.titles, inputs.kinship)
    registry, profiles = anchor_profiles(assertions, inputs.people)
    conflicts, blocked, ignored_guesses = [], set(), set()
    for identity, observations in profiles.items():
        factual = [mention for mention in observations if mention.assertion.source.kind == 'facts']
        if not compatible_deaths(factual):
            blocked.add(identity)
            conflicts.append({'reason': 'conflicting factual death constraints', 'identities': [identity],
                              'sources': [mention.assertion.source.export() for mention in factual]})
        elif chronology_blocked(factual, parameters(inputs.matching or None), names):
            conflicts.append({'reason': 'unmarked mention after recorded death or impossible age', 'identities': [identity],
                              'sources': [mention.assertion.source.export() for mention in factual]})
        elif not compatible_deaths(observations):
            # Keep guessed death evidence available to the weighted model.
            # It must neither erase factual identities nor disappear silently.
            conflicts.append({'reason': 'incompatible guessed death alternatives', 'identities': [identity],
                              'sources': [mention.assertion.source.export() for mention in observations]})
    # Diagnose anchored contradictions before considering inferred assignments.
    anchored_edges = []
    for assertion in assertions:
        if assertion.original['type'] not in RELATIONS:
            continue
        refs = [mention.reference for mention in assertion.mentions]
        if len(refs) == 2 and all(ref in registry for ref in refs):
            if refs[0] == refs[1]:
                if assertion.source.kind == 'facts':
                    blocked.add(refs[0])
                else:
                    ignored_guesses.add(assertion.source.key)
                conflicts.append({'reason': 'anchored self-relationship', 'identities': refs, 'sources': [assertion.source.export()]})
            if assertion.original['type'] == 'parent' and assertion.source.kind == 'facts':
                anchored_edges.append(tuple(refs))
    cyclic = cycle_nodes(anchored_edges)
    if cyclic:
        blocked.update(cyclic)
        conflicts.append({'reason': 'anchored factual parentage cycle', 'identities': sorted(cyclic)})
    # Reject cyclic exact-ID guesses before scoring. Otherwise one inconsistent
    # family makes every joint assignment invalid, even in unrelated families,
    # and removed guesses can still leak into identity-support dependencies.
    anchored_parents = [a for a in assertions if a.original['type'] == 'parent'
                        and a.source.key not in ignored_guesses
                        and all(m.reference in registry and m.reference not in blocked for m in a.mentions)]
    cyclic_pairs = cycle_edges(tuple(m.reference for m in a.mentions) for a in anchored_parents)
    rejected_parents = [a for a in anchored_parents if a.source.kind == 'guesses'
                        and tuple(m.reference for m in a.mentions) in cyclic_pairs]
    ignored_guesses.update(a.source.key for a in rejected_parents)
    if rejected_parents:
        conflicts.append({'reason': 'incompatible parentage alternatives',
                          'identities': sorted({m.reference for a in rejected_parents for m in a.mentions}),
                          'sources': [a.source.export() for a in rejected_parents]})
    usable = [assertion for assertion in assertions if assertion.source.key not in ignored_guesses
              and not any(mention.reference in blocked for mention in assertion.mentions)]
    # Candidates must be rebuilt after removing incompatible hypothetical
    # constraints so rejected guesses cannot supply positive identity evidence.
    registry, _, candidates = make_candidates(usable, inputs.people, names, rules)
    decisions, alternatives = resolve(usable, registry, candidates, search_limit)
    if rejected_parents:
        alternatives.append({'relationships': [Relationship('parent', a.mentions[0].reference, a.mentions[1].reference, '',
            derivations=[{'view': 'with-guesses', 'identity': 'anchored', 'usesGuesses': True,
                          'sources': [a.source.export()]}]) for a in rejected_parents]})
    for assertion in assertions:
        for mention in assertion.mentions:
            if mention.handle not in decisions:
                decisions[mention.handle] = IdentityDecision(mention, 'rejected', mention.reference if mention.reference in registry else None,
                    'anchored' if mention.reference in registry else 'unresolved', reason='affected by contradictory anchored evidence')
    relationships = {}
    view = 'with-guesses' if include_guesses else 'facts'
    for assertion in usable:
        kind = assertion.original['type']
        if kind not in RELATIONS:
            continue
        left, right = [decisions[mention.handle] for mention in assertion.mentions]
        # Unresolved endpoints remain distinct provisional mentions in memory.
        endpoints = [decision.identity if decision.status == 'accepted' else decision.mention.handle for decision in (left, right)]
        if any(endpoint in blocked for endpoint in endpoints):
            continue
        if kind != 'parent':
            endpoints.sort()
        key = (kind, *endpoints, assertion.original.get('term', ''))
        sources = {source.key: source for source in [assertion.source, *left.sources, *right.sources]}
        methods = [decision.method for decision in (left, right)]
        method = 'inferred' if any(value in {'inferred', 'unresolved'} for value in methods) else 'reviewed' if 'reviewed' in methods else 'anchored'
        derivation = {'view': view, 'identity': method,
            'usesGuesses': assertion.source.kind == 'guesses' or left.uses_guesses or right.uses_guesses,
            'sources': [sources[source].export() for source in sorted(sources)]}
        edge = relationships.setdefault(key, Relationship(*key))
        if derivation not in edge.derivations:
            edge.derivations.append(derivation)
    edges = list(relationships.values())
    # Never flatten inconsistent guessed graphs. Keep competing guessed edges
    # inspectable, exporting the uncontested factual subset of this view.
    cyclic_pairs = cycle_edges((edge.person, edge.of) for edge in edges if edge.type == 'parent')
    if cyclic_pairs:
        conflicting = [edge for edge in edges if edge.type == 'parent' and (edge.person, edge.of) in cyclic_pairs]
        guessed = [edge for edge in conflicting if all(d['usesGuesses'] for d in edge.derivations)]
        removed = guessed or conflicting
        conflicts.append({'reason': 'incompatible parentage alternatives', 'identities': sorted({node for pair in cyclic_pairs for node in pair})})
        alternatives.append({'relationships': removed})
        edges = [edge for edge in edges if edge not in removed]
    omitted = sum(edge.person not in registry or edge.of not in registry for edge in edges)
    diagnostics = ['A typed mention without a deceased marker means the person was alive at its date.',
                   'Repeated features are capped by category; document/image source factors remain 1.0.',
                   'Prose and synthetic seal descriptions do not generate relationships.',
                   'Identity probabilities are model estimates, not calibrated historical accuracy.']
    provisional_groups = defaultdict(list)
    for handle, decision in decisions.items():
        if decision.status == 'unresolved':
            group = '@possible-group/' + fingerprint(names.key(decision.mention.reference)).split(':')[1][:16]
            provisional_groups[group].append(handle)
    # These are retrieval alternatives, not identity clusters. Every unresolved
    # node and relationship continues to use its own occurrence handle.
    for group, handles in provisional_groups.items():
        if len(handles) > 1:
            for handle in handles:
                decisions[handle].candidates.append(Candidate(group, [{'name': 'compatible unresolved occurrences; no identity merge', 'score': 0}]))
    evidence = reconstruct(usable, decisions, registry, names, parameters=inputs.matching or None,
                           observations=[o for o in inputs.observations if include_guesses or o.source.kind == 'facts'])
    return BuildResult(view, decisions, edges, conflicts, diagnostics, alternatives, omitted, dict(provisional_groups),
                       {'searchLimit': search_limit, 'probability': parameters(inputs.matching or None)}, evidence)
