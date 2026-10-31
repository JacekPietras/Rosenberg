"""Tree positions of source kinship terms (data/kinship.md)."""

from dataclasses import dataclass
import re

from .names import normalize

STEP = re.compile(r'Sp|P|C|S')
INVERSE = {'P': 'C', 'C': 'P', 'S': 'S', 'Sp': 'Sp'}
GENERATION = {'P': 1, 'C': -1, 'S': 0, 'Sp': 0}
SPECIFICITY = ('exact', 'narrow', 'broad')
# Shorter equivalent readings of a step pair: a parent's child is a sibling.
REDUCTIONS = {('P', 'C'): ('S',), ('S', 'S'): ('S',), ('S', 'P'): ('P',), ('C', 'S'): ('C',), ('C', 'P'): ('Sp',)}


def steps(text):
    parts = STEP.findall(text)
    if ''.join(parts) != text:
        raise ValueError(f'data/kinship.md: invalid position {text!r}')
    return tuple(parts)


def reduce(path):
    path = tuple(path)
    changed = True
    while changed:
        changed = False
        for index in range(len(path) - 1):
            pair = path[index:index + 2]
            if pair in REDUCTIONS:
                path = path[:index] + REDUCTIONS[pair] + path[index + 2:]
                changed = True
                break
    return path


def invert(path):
    return reduce(INVERSE[step] for step in reversed(path))


def generation(path):
    return sum(GENERATION[step] for step in path)


@dataclass(frozen=True)
class Positions:
    """A set of tree paths, or a class of them ('any', 'blood', 'in-law')."""
    paths: frozenset = frozenset()
    classes: frozenset = frozenset()

    def contains(self, path):
        return (path in self.paths or 'any' in self.classes
                or 'blood' in self.classes and 'Sp' not in path
                or 'in-law' in self.classes and 'Sp' in path)

    def inverted(self):
        return Positions(frozenset(invert(path) for path in self.paths), self.classes)

    def __or__(self, other):
        return Positions(self.paths | other.paths, self.classes | other.classes)


def parse_positions(text):
    paths, classes = set(), set()
    for item in text.split():
        if item in {'any', 'blood', 'in-law'}:
            classes.add(item)
        else:
            paths.add(reduce(steps(item)))
    return Positions(frozenset(paths), frozenset(classes))


@dataclass(frozen=True)
class Term:
    allowed: Positions
    # A combined term excludes only what every part excludes.
    excluded: tuple
    specificity: str

    def excludes(self, path):
        return bool(self.excluded) and all(item.contains(path) for item in self.excluded)

    def inverted(self):
        return Term(self.allowed.inverted(), tuple(item.inverted() for item in self.excluded), self.specificity)


UNKNOWN = Term(Positions(classes=frozenset({'any'})), (), 'broad')
DIRECT = {('parent', 'person'): ('P',), ('parent', 'of'): ('C',), ('sibling', 'person'): ('S',),
          ('sibling', 'of'): ('S',), ('spouse', 'person'): ('Sp',), ('spouse', 'of'): ('Sp',)}


class Kinship:
    def __init__(self, text=''):
        self.terms = {}
        for line in text.splitlines():
            line = line.split('//', 1)[0].strip()
            if not line:
                continue
            forms, _, meaning = line.partition(':')
            parts = [part.strip() for part in meaning.split('|')]
            if len(parts) != 3 or parts[2] not in SPECIFICITY:
                raise ValueError(f'data/kinship.md: expected "forms: allowed | excluded | specificity" in {line!r}')
            term = Term(parse_positions(parts[0]), (parse_positions(parts[1]),), parts[2])
            for form in forms.split(','):
                if form.strip():
                    self.terms[normalize(form)] = term

    def term(self, text):
        """Meaning of `person is <term> of X`, read from X; combined terms are unions."""
        key = normalize(text)
        if key in self.terms:
            return self.terms[key]
        parts = [part for part in re.split(r'\s+(?:und|and|et|oder|or)\s+', key) if part]
        if len(parts) < 2 or any(part not in self.terms for part in parts):
            return UNKNOWN
        known = [self.terms[part] for part in parts]
        allowed = known[0].allowed
        for term in known[1:]:
            allowed |= term.allowed
        excluded = tuple(item for term in known for item in term.excluded)
        return Term(allowed, excluded, max((term.specificity for term in known), key=SPECIFICITY.index))

    def position(self, assertion, field):
        """Positions of the `field` participant, read from the other participant."""
        kind = assertion.original['type']
        if kind == 'kin':
            term = self.term(assertion.original.get('term', ''))
            return term if field == 'person' else term.inverted()
        path = DIRECT[kind, field]
        return Term(Positions(frozenset({path})), (), 'exact')


def tree_paths(tree, start, max_steps):
    """Reduced paths from `start` to every identity within `max_steps` relationship steps."""
    result = {}
    def walk(node, path, seen):
        if len(path) == max_steps:
            return
        for step, other in sorted(tree.get(node, ())):
            if other in seen:
                continue
            reduced = reduce(path + (step,))
            if reduced:
                result.setdefault(other, set()).add(reduced)
            walk(other, path + (step,), seen | {other})
    walk(start, (), {start})
    return result
