# Family reconstruction algorithm

How `scripts/family_graph/` turns source facts into the family graph in
`data/tree.json`. The requirements are in [domain-rules.md](domain-rules.md);
the `tree.json` format is in [`json-formats.md`](../json-formats.md).

## Inputs and output

| Input | Use |
| --- | --- |
| `data/{documents,books,notes,images}/**/*.json` | Typed facts and guesses (assertions) and their prose |
| `data/people.json` | Confirmed registry IDs; fixed, never changed |
| `data/names.md` | Given-name variants and gender sections |
| `data/titles-age.md` | Age titles with equivalent variants |
| `data/titles-office.md` | Offices, ranks, and epithets with equivalent variants; also used by policy and name recognition |
| `data/kinship.md` | Tree positions allowed and excluded by kinship terms |
| `data/places.json` | Place variants for titles and context |
| `data/matching.json` | All weights, thresholds and limits |
| `data/distinctFamilies.md` | Case-insensitive document labels excluded from collection |

The output is one evidence view that includes guesses: nodes (identities),
relationships, comparisons with their features and blocks, and `possiblySame`
links. `tree.json` is output only; it is never read back as evidence. It keeps
only merged and ambiguous comparisons; the rest go to the gitignored
`.cache/tree-debug.json`.

Before validation or collection, the loader skips every document JSON marked
`"deleted": true` and every document whose top-level `label` contains a
case-insensitive match from `data/distinctFamilies.md`. Skipped documents add
no facts, guesses, or prose observations to the reconstruction.

For included documents, each entry's English text is scanned with the shared
person-name lists and contributes contextual mentions, with provenance at the
entry's `/english` pointer. This rule does not apply to books, notes, images,
or other source types: their contextual name mentions continue to come from
facts only. Prose mentions may support identity matching and contextual links,
but never create family relationship assertions. See
[document English recognition](person-name-text-migration.md).

An explicit fact date, including a generic fact's date, overrides the enclosing
document or entry date for its assertions and fact-text context. Entry English
text retains the enclosing date.

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

| Step | Effect | Specification |
| --- | --- | --- |
| Load | Assertions, prose context mentions, one identity per registry ID | this file |
| Pass 0 | Same name and titles in one section are merged | [pass-0-same-section.md](pass-0-same-section.md) |
| Pass 1 | Fewest people per passage; cited repeated attestations merged | [pass-1-passage-resolution.md](pass-1-passage-resolution.md) |
| Closure | Father from a sibling; same-named relatives merged | [family-closure.md](family-closure.md) |
| Pass 3 | Pairs above 0.70 merged in rounds, each followed by closure | [pass-3-confident-linking.md](pass-3-confident-linking.md) |
| Pass 4 | Best unblocked candidate joined in rounds, each followed by closure | [pass-4-best-candidate.md](pass-4-best-candidate.md) |
| Export | Contradicted inherited fathers withdrawn; nodes, edges, comparisons written | [`json-formats.md`](../json-formats.md) |

Passes 3 and 4 share the [evidence model](evidence-model.md); its arithmetic is
worked through in [weight-calculation-examples.md](weight-calculation-examples.md).

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

The rebuild command emits flushed `PROGRESS:` messages for loading, candidate
resolution, and reconstruction. Pass 3 and pass 4 report each completed round;
they also report round starts and compatible-pair counts as comparisons run.
The local viewer displays the latest progress message while rebuilding.

Name variants before `von` are normalized component by component; for example,
`Ludwig Münch von Rosenberg` and `Ludwig Mönch von Rosenberg` have the
same name key, while a different intervening name remains distinct.
