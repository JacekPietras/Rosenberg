# Family reconstruction algorithm

How `scripts/family_graph/` turns source facts into the family graph in
`data/tree.json`. The requirements are in [domain-rules.md](domain-rules.md);
the `tree.json` format is in [`rules/json-formats.md`](../rules/json-formats.md).

## Inputs and output

| Input | Use |
| --- | --- |
| `data/{documents,books,notes,images}/**/*.json` | Typed facts and guesses (assertions) and their prose |
| `data/people.json` | Confirmed registry IDs; fixed, never changed |
| `data/names.md` | Given-name variants and gender sections |
| `data/titles.md` | Equivalent title words and epithets |
| `data/kinship.md` | Tree positions allowed and excluded by kinship terms |
| `data/places.json` | Place variants for titles and context |
| `data/matching.json` | All weights, thresholds and limits |

The output is one evidence view that includes guesses: nodes (identities),
relationships, comparisons with their features and blocks, and `possiblySame`
links. `tree.json` is output only; it is never read back as evidence.

## Terms

- **Mention**: one typed participant (`person` or `of`) of one assertion, or a
  context mention taken from prose.
- **Passage**: one source entry at one historical date (path, entry pointer,
  date). **Section**: one document file, or one entry of a book, notes or
  images file.
- **Identity**: a set of mentions believed to be one person. Mentions with an
  exact registry ID start as one fixed identity per ID.
- **Compatible names**: the same given name (`data/names.md` variants; a final
  `a`/`e` is ignored for names of four letters or more) and the same surname, or
  one side without a surname. Only identities with compatible names are
  compared.
- **Membership confidence**: per mention, the product of the merge
  probabilities (pass 3) or shares (pass 4) linking it to its identity's core.
  Passes 0 and 1 and registry IDs count `1.0`. Relative evidence uses the
  membership confidence of the relative mention it comes from.

## Pipeline

```text
load       assertions, prose context mentions, registry anchors
pass 0     same name and titles in one section                     merges
pass 1     fewest people per passage; cited repeated attestations  merges
closure    father from a sibling; same-named relatives             adds fathers, merges
pass 3     confident pairs above 0.70, in rounds                   merges, then closure
pass 4     best unblocked candidate, no threshold, in rounds       merges, then closure
export     withdraw contradicted inherited fathers; nodes, edges, comparisons
```

| Step | File |
| --- | --- |
| Pass 0 | [pass-0-same-section.md](pass-0-same-section.md) |
| Pass 1 | [pass-1-passage-resolution.md](pass-1-passage-resolution.md) |
| Family closure | [family-closure.md](family-closure.md) |
| Evidence and blocks used by passes 3 and 4 | [evidence-model.md](evidence-model.md) |
| Pass 3 | [pass-3-confident-linking.md](pass-3-confident-linking.md) |
| Pass 4 | [pass-4-best-candidate.md](pass-4-best-candidate.md) |
| Arithmetic | [weight-calculation-examples.md](weight-calculation-examples.md) |

There is no pass 2: matching transaction types across sources was dropped,
because same-day shared places and associates already link a book retelling to
its charter. Pass numbers match the `stage` values in `tree.json`.

## Merge check

Every merge in every pass is checked on the complete identity it would create
(`consistent` in `reconstruction.py`). A merge is refused if:

- it joins two registry IDs;
- names are not pairwise compatible;
- two different age titles occur in one passage;
- document facts alone make it chronologically impossible: mention after
  death, death bounds in conflict, or older than `maxAgeYears`;
- it creates a new same-passage distinction (opposite ranks, deceased and
  living, two separate facts with the same content), a new impossible age, or
  living mentions spanning more than `bestCandidate.maxLivingSpanYears`, on
  any source type;
- the merged person would have two fathers or two mothers that cannot be one
  person ([family-closure.md](family-closure.md#one-father-one-mother));
- two same-named parents or spouses of one person could then not be one person;
- a relationship would link the identity to itself, create an ancestry cycle,
  or break generations (siblings level, a parent exactly one above a child);
- the parts are already known relatives through the tree
  ([evidence-model.md](evidence-model.md#known-relatives)).

Conflicts already inside one existing identity are data problems: they are
reported, and do not block later merges of that identity. Recorded
relationships are used for the cycle, generation and known-relative checks;
fathers inherited from a sibling only take part in the one-father rule.

All proposals of one round are checked together per connected family, so a
pair of individually valid merges cannot jointly break a rule.

## Determinism

Profiles are frozen within a round. Candidates are sorted by score and then by
source keys, so the result does not depend on input order. A rerun with the
same inputs gives a byte-identical `tree.json`.

## Code map

| Concern | File |
| --- | --- |
| Loading, input fingerprints | `sources.py`, `model.py` |
| Names, titles, gender | `names.py`, `scripts/given_names.py` |
| Kinship positions and paths | `kinship.py` |
| Evidence features, chronology, blocks | `probability.py` |
| Passes, merge check, closure | `reconstruction.py` |
| Cycles | `constraints.py` |
| Export and validation | `export.py`, `graph.py` |

Tests: `tests/test_probability.py` (features and blocks) and
`tests/test_family_graph.py` (passes and real-data cases).

## Maintaining this specification

This folder describes the current implementation. Change the domain rule first,
then the pass file, the code and the tests together. Keep worked numbers in
[weight-calculation-examples.md](weight-calculation-examples.md) in step with
`data/matching.json`.
