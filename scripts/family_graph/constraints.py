"""Hard logical constraints; absence of a title or living evidence is neutral."""

from collections import defaultdict


def cycle_nodes(edges):
    """Return nodes in directed cycles, allowing repeated ancestry (a DAG)."""
    children = defaultdict(set)
    for parent, child in edges:
        children[parent].add(child)
    index, low, stack, active, cyclic = {}, {}, [], set(), set()

    def visit(node):
        index[node] = low[node] = len(index)
        stack.append(node)
        active.add(node)
        for child in children[node]:
            if child not in index:
                visit(child)
                low[node] = min(low[node], low[child])
            elif child in active:
                low[node] = min(low[node], index[child])
        if low[node] == index[node]:
            component = set()
            while True:
                child = stack.pop()
                active.remove(child)
                component.add(child)
                if child == node:
                    break
            if len(component) > 1 or node in children[node]:
                cyclic.update(component)

    for node in list(children):
        if node not in index:
            visit(node)
    return cyclic


def valid_assignment(assertions, assignment):
    from .dates import compatible_deaths
    edges = []
    observations = defaultdict(list)
    for assertion in assertions:
        for mention in assertion.mentions:
            if assignment.get(mention.handle) is not None:
                observations[assignment[mention.handle]].append(mention)
        if len(assertion.mentions) != 2:
            continue
        left, right = [assignment.get(mention.handle) for mention in assertion.mentions]
        if left is None or right is None:
            continue
        if left == right:
            return False
        if assertion.original['type'] == 'parent':
            edges.append((left, right))
    return not cycle_nodes(edges) and all(compatible_deaths(mentions) for mentions in observations.values())
