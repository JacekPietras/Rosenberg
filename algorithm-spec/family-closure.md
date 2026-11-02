# Family closure

Runs after pass 1 and after every round of passes 3 and 4 (`family_closure` in
`reconstruction.py`). It applies the parent and sibling rules of
[domain-rules.md](domain-rules.md#parents-and-siblings) in three steps:
withdraw contradicted inherited fathers, inherit fathers from siblings, merge
same-named relatives. Any merge or added father starts another round.

## Gender

A person's gender is the section of his given name in `data/names.md`:
`# Men` is `man`, `# Women` is `woman`, any other header or an unlisted name has
none. A parent without a gender takes no part in the one-father rule and is
never inherited.

## One father, one mother

Checked in every merge (`different_parent`). For each part of a proposed
identity, collect the identities of its fathers and of its mothers, recorded or
inherited. Two parts conflict when, for one gender, no father of one part could
be one person with a father of the other. Two father identities could be one
person when they are the same identity, or when:

- their names are compatible;
- they do not hold two registry IDs;
- their documents are not chronologically impossible together;
- the evidence model's chronology hard blocks allow them (impossible age,
  mention after death, incompatible death dates, living span).

A conflict blocks the merge with reason `different father: … / …` (or
`mother`). Conflicts already inside one part are data problems and are not
re-checked. Same-named fathers that pass are joined by the same-named-relatives
step below.

Example: vogt_zu_Lauda has the recorded father vogt_zu_Durn (1300–1364). A 1443
record "Eberhard, sibling of Kunz" has the inherited father Eberhard (1380–1444).
The two fathers cannot be one person, so the 1443 record stays separate.

## Father from a sibling

For each recorded `sibling` fact between X and Y (both directions):

1. X and Y have one and the same surname (every surname form of the identity
   agrees).
2. For each **recorded** parent F of X: F has that surname, F's gender is `man`,
   F is not Y, and F is not already Y's parent.
3. Y's fathers (recorded or inherited) must all have F's given name and could be
   one person with F; otherwise Y keeps his own father.
4. Add the inherited `parent` assertion F → Y. Its source is the weaker of the
   parent and sibling assertions (facts before guesses, then lower reliability);
   both are kept as its basis.
5. Withdraw it at once if it would create an ancestry cycle or break
   generations. A considered (parent, sibling, Y) combination is never retried.

An inherited father:

- adds family evidence to Y's profile and can make separate records of F join
  through the same-named-relatives step;
- counts in the one-father rule;
- is not used for explicit distinctions, chronology (posthumous births, a
  parent's age at his children's mentions), cycles, generations, known-relatives
  paths or kinship positions;
- is never passed on to another sibling;
- is exported as a `parent` edge with `inference: "sibling"`, unless the same
  recorded edge exists.

## Withdrawal

Before inheriting, and once more before export, an inherited father is removed
when later merges made it contradictory:

- the father and the child became one identity;
- the child has another father (recorded, or inherited and kept earlier) that
  could not be one person with it;
- with the recorded relationships it creates a cycle or breaks generations (only
  checked when the recorded relationships are consistent themselves).

## Same-named relatives

For every `parent`, `sibling` and `spouse` assertion (recorded or inherited)
whose own mention has membership confidence of at least `mergeProbability`:
group the relatives by (identity, role, given name). Two relatives in one group
whose names are all compatible are proposed as one person (two Konrad brothers
of the Vogt, two fathers named Eberhard). The proposals pass the
[merge check](algorithm.md#merge-check); those that fail stay separate and are
decided by pass 4. Merges have membership confidence `1.0`.
