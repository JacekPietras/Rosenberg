"""Bounded joint resolution; uncertain alternatives never merge anchors."""

from collections import defaultdict
from .constraints import valid_assignment
from .model import IdentityDecision
from .policy import MIN_MARGIN, MIN_SCORE


def resolve(assertions, registry, candidates, search_limit):
    mentions = {mention.handle: mention for assertion in assertions for mention in assertion.mentions}
    fixed = {key: mention.reference for key, mention in mentions.items() if mention.reference in registry and registry[mention.reference].get('id') == mention.reference}
    decisions = {key: IdentityDecision(mentions[key], 'accepted', identity, 'anchored', reason='exact case-sensitive source ID') for key, identity in fixed.items()}
    eligible = {}
    for handle, alternatives in candidates.items():
        options = [candidate for candidate in alternatives if candidate.identity in registry and not candidate.exclusions and candidate.score >= MIN_SCORE]
        if options:
            eligible[handle] = options
        decisions[handle] = IdentityDecision(mentions[handle], 'unresolved', None, 'unresolved', alternatives,
            reason='name compatibility retrieves candidates; insufficient distinguishing evidence')

    # Components connect competing candidate identities and explicit source
    # relations. Only candidates with substantive support enter the search.
    neighbors = defaultdict(set)
    def connect(left, right):
        neighbors[left].add(right)
        neighbors[right].add(left)
    for key, options in eligible.items():
        for candidate in options:
            connect(key, '@anchor/' + candidate.identity)
    for key, identity in fixed.items():
        connect(key, '@anchor/' + identity)
    for assertion in assertions:
        if len(assertion.mentions) == 2:
            connect(assertion.mentions[0].handle, assertion.mentions[1].handle)
    components = []
    unseen = set(eligible)
    while unseen:
        stack, component = [min(unseen)], set()
        while stack:
            key = stack.pop()
            if key in component:
                continue
            component.add(key)
            unseen.discard(key)
            stack.extend(neighbors[key] - component)
        components.append(sorted(component & eligible.keys()))

    alternatives_output = []
    for component in components:
        best_score, solutions, visited, limited = float('-inf'), [], 0, False
        assignment = dict(fixed)

        def search(index, score):
            nonlocal visited, limited, best_score, solutions
            visited += 1
            if visited > search_limit:
                limited = True
                return
            if index == len(component):
                if not valid_assignment(assertions, assignment):
                    return
                # Retain near-optimal solutions to enforce a real decision margin.
                if score > best_score:
                    best_score = score
                    solutions = [(value, solution) for value, solution in solutions if score - value < MIN_MARGIN]
                if best_score - score < MIN_MARGIN:
                    solutions.append((score, {key: assignment.get(key) for key in component}))
                return
            key = component[index]
            for candidate in eligible[key]:
                assignment[key] = candidate.identity
                search(index + 1, score + candidate.score)
                if limited:
                    break
            assignment[key] = None
            if not limited:
                search(index + 1, score)
            assignment.pop(key, None)

        search(0, 0)
        alternatives_output.append({'mentions': component, 'limited': limited, 'solutions': [solution for _, solution in solutions]})
        for key in component:
            decision = decisions[key]
            if limited:
                decision.reason = 'component search limit reached; assignments remain unresolved'
                continue
            choices = {solution[key] for _, solution in solutions}
            if len(choices) != 1 or None in choices:
                decision.reason = 'competing consistent solutions remain within the decision margin'
                continue
            identity = next(iter(choices))
            selected = next(candidate for candidate in eligible[key] if candidate.identity == identity)
            # Include competing and negative evidence: it can affect selection.
            dependencies = [source for handle in component for candidate in candidates[handle] for source in candidate.sources]
            dependencies += [mentions[handle].assertion.source for handle in component if handle != key]
            unique = {source.key: source for source in dependencies}
            decision.status, decision.identity = 'accepted', identity
            decision.method = 'reviewed' if selected.reviewed else 'inferred'
            decision.sources = [unique[ref] for ref in sorted(unique)]
            decision.uses_guesses = any(source.kind == 'guesses' for source in decision.sources) or mentions[key].assertion.source.kind == 'guesses'
            if decision.uses_guesses:
                decision.method = 'inferred'
            decision.reason = 'contextual score and margin survive joint logical constraints'
    return decisions, alternatives_output
