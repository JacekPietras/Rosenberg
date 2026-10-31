# Second pass: attaching leftover records

Implemented in `scripts/family_graph/reconstruction.py` and
`scripts/family_graph/kinship.py`. It extends the
[specification](family-tree-algorithm-plan.md) and keeps its log-odds
convention, rival margin (`1.0`), and blocks. Pass 1 merges at `0.70`; pass 2
attaches at the stricter `0.80`, because its evidence depends on the tree pass 1
built.

## Problem

Pass 1 compares records pairwise using what each record states directly:
titles, places, same-fact associates, and relatives named in the record. Many
records stay unmerged because their decisive evidence only exists once a tree
is built. In the current build:

- 529 relationship records without a registry ID stay unmerged, 386 of them
  with a single mention. 362 share a name with another node, mostly
  Eberhard, Konrad, Arnold, and Hans von Rosenberg.
- 331 lone `title` or `death` mentions have no relationship and appear in no
  card at all.
- 82 `kin` relationships carry a source term (`Vetter` 77×, `Schwager` 24×,
  `nepotes`, `Oheim`, `Base`, `fratrueles`, `Eidam` …) that pass 1 reads only as
  “some relative”.

Example: in 1401 “Arnold von Rosenberg der Ältere” is `Vetter` of
`eberhard_jagstberg`. Eberhard's father, the Vogt zu Lauda, has a brother Arnold
(`arnold_brother_of_vogt_zu_Lauda`). Pass 1 has no evidence (`0`): it cannot
see that a `Vetter` may be a father's brother, nor that the only other Arnold
there, `arnold_boxberg`, is Eberhard's brother and therefore not his `Vetter`.

## Principles

1. **Reference tree.** Pass 1 runs unchanged and is frozen as the reference
   tree `T0`: its identities, their relationships, and their link confidence.
2. **Attach, never join.** Pass 2 attaches a leftover to a `T0` identity. It
   never merges two `T0` identities and never merges two leftovers with each
   other.
3. **No chains.** Every leftover is scored against `T0` only. An attachment
   made in pass 2 never supports another attachment. This keeps results
   independent of input order and stops a chain of guesses.
4. **Same rules.** Every attachment passes the same blocks as pass 1 (death,
   age, distinctions, generations, same-named parents/spouses) on the resulting
   identity, and the same threshold and margin.
5. **Explain the path.** Each attachment records `pass: 2` and the tree path
   used, for example `father's brother of eberhard_jagstberg (via
   vogt_zu_Lauda)`.

## Leftovers

| Kind | Definition | Can use |
| --- | --- | --- |
| Related leftover | Unmerged record without registry ID that has a relationship to a `T0` identity | All pass-2 evidence |
| Detached leftover | Unmerged record whose relatives are also leftovers | Nothing new |
| Lone mention | `title` or `death` mention without a relationship, not grouped into any identity | Nothing new |

Only related leftovers get structural evidence, because the tree can only be
consulted from a known point. Pass 1's last round already compared detached
leftovers and lone mentions against the final tree with all pass-1 evidence, so
pass 2 has nothing to add for them. Example: in `1381-05-25_3.json` Konrad, Ritter,
Vitztum zu Heidelberg, is `Schwager` of Hans von Hirschhorn. Hans is not in the
Rosenberg tree, so this case stays a detached leftover.

## Kinship terms

Source terms are kept verbatim in the facts. Their meanings live in a new
`data/kinship.md` (like `data/titles.md`). Each term lists allowed **tree
positions**, excluded positions, and a **specificity**.

Position notation, read from the named relative X: `P` parent, `C` child,
`S` sibling, `Sp` spouse. `PS` is a parent's sibling (uncle/aunt), `SC` a
sibling's child, `PSC` a cousin, `CSp` a child's spouse.

| Term | Allowed positions | Excluded | Specificity |
| --- | --- | --- | --- |
| `patruus` | `PS` (father's side) | `S`, `P`, `C`, `Sp` | exact |
| `Bruderstochter` | `SC` | `S`, `P`, `C`, `Sp` | exact |
| `Eidam` | `CSp` | blood relatives | exact |
| `Ahnherr` | `PP` or earlier | `S`, `C`, `Sp` | narrow |
| `Vetter` | `PS`, `SC`, `PSC` | `S`, `P`, `C`, `Sp` | narrow |
| `Base` | `PS`, `SC`, `PSC` | `S`, `P`, `C`, `Sp` | narrow |
| `Oheim` | `PS`, `SC` | `S`, `P`, `C`, `Sp` | narrow |
| `Nichte` | `SC`, `SpSC` | `S`, `P`, `C`, `Sp` | narrow |
| `nepotes` | `SC`, `CC` | `S`, `P`, `Sp` | narrow |
| `fratrueles`, `fratruales` | `SC`, `PSC` | `S`, `P`, `C`, `Sp` | narrow |
| `Schwager` | `SpS`, `SSp`, `SpSSp` | blood relatives | narrow |
| `consanguineus` | any blood path up to 3 steps | `Sp`, in-laws | broad |
| `Vetter und Schwager` | union of both terms | only what both exclude | broadest part |
| unknown term | any path up to 3 steps | none | broad |

- Paths use only `T0` relationships, at most 3 steps.
- Sex is not modeled: `Base` and `Vetter` have the same positions.
- Each path implies a generation offset (`PS` +1, `SC` −1, `PSC` 0, `CSp` −1,
  `CC` −2). The existing generation-consistency check applies to it.

## Evidence

Contributions are scaled by the leftover assertion's reliability and decay like
family evidence (`familyHalfLifeYears`, gap to the candidate's nearest mention).
The relative X's link confidence also applies. If pass 1 already counted a
family feature for X, the position match for X is not added again.

### 1. Position match

A same-named `T0` identity sits in a position the term allows:

```text
contribution = sharedRelativeWeight × specificity factor × reliability × decay
specificity factor: exact 1.0, narrow 0.5, broad 0.3
```

This is the shared-relative rule of pass 1 extended to longer paths. Only the
strongest path per candidate counts.

### 2. Position contradiction

The candidate sits only in excluded positions (for example a `Vetter` who is
X's brother). This is treated as an explicit distinction: a block for documents
and a `-deathConflictPenalty × reliability` penalty for books and guesses.
Unknown and broad terms never contradict.

### 3. Only candidate

Among same-named `T0` identities, exactly one sits in an allowed position and
is not blocked (death, age, distinction, contradiction).

```text
contribution = eliminationWeight (proposed 1.5) × reliability
```

The weight is moderate on purpose: the tree is incomplete, and a namesake from
an unrecorded branch is always possible. It applies only to related leftovers,
and is cancelled when another leftover with the same name and an overlapping
lifespan is related to the same family.

### 4. Age-title namesake

`der Ältere` / `der Alte` at a date implies a younger same-named relative alive
then (and the reverse for `der Jüngere` / `der Junge`). If that namesake is in
`T0` and the candidate sits one generation above (or below) it, add
`ageTitleNamesakeWeight` (proposed `1`). The namesake itself is already
excluded by the existing distinction rule.

### 5. Pass-1 evidence

Titles, places, associates, age, and death are computed exactly as in pass 1
against the candidate's full `T0` identity. Lone mentions rely on these alone.

## Algorithm

1. Build `T0` with pass 1. Compute for every `T0` identity its relationship
   paths up to 3 steps.
2. Collect leftovers. For each related leftover `L` with relative `X` in `T0`:
   - read the term's positions (direct `parent`/`sibling`/`spouse` facts have
     exact positions);
   - candidates are same-named `T0` identities at allowed or excluded
     positions, plus pass-1 candidates.
3. Score every candidate (sections 1–5). Leftovers are scored independently of
   each other.
4. Propose the best candidate if it passes the threshold and leads by the
   margin; otherwise `L` stays unresolved, with its best candidates recorded.
5. Apply all proposals to `T0` together. If several leftovers attached to the
   same identity conflict with each other (blocks on the combined identity),
   reject all of the conflicting proposals and record them as competing. This
   keeps the result independent of order.
Single round. Repeating pass 2 to a fixed point would find more but breaks
principle 3.

## Effect on current data

| Leftover | Best candidate | Evidence | Result |
| --- | --- | --- | --- |
| Arnold der Ältere, 1401, `Vetter` of `eberhard_jagstberg` | `arnold_brother_of_vogt_zu_Lauda` (`PS`) | position `+4.6`, only candidate `+1.5`, age-title namesake `+1`; `arnold_boxberg` contradicted (brother) | 98.5%, attached |
| Arnold, armiger, 1387, `consanguineus` of the Vogt | brother (`S`) vs. son `arnold_boxberg` (`C`) | brother: position `+2.56`, rank `+0.75`; son: position `+2.33`, age `-0.7` | brother 62.5%, below threshold: unresolved |
| Konrad, Ritter, Vitztum, 1381, `Schwager` of Hans von Hirschhorn | — | Hans not in `T0` | detached, unchanged |

The 1387 Arnold stays unresolved because `consanguineus` fits both brother and
son. If you consider that wrong, raise the broad factor or the elimination
weight rather than add a special rule.

## Output

- `tree.json` comparisons gain `pass` (`1`/`2`) and, for pass 2, `path`, `term`,
  and `position`.
- A node's `identitySources` marks mentions attached in pass 2.
- Unattached leftovers keep their best candidates and the reason (below
  threshold, margin, competing, contradicted), for review in the viewer.
- New configuration in `data/matching.json`:

```json
"secondPass": {
  "maxPathSteps": 3,
  "specificityFactors": {"exact": 1.0, "narrow": 0.5, "broad": 0.3},
  "eliminationWeight": 1.5,
  "ageTitleNamesakeWeight": 1.0
}
```

## Required regression cases

1. `Vetter` of X attaches to X's father's brother; never to X's brother.
2. A `consanguineus` fitting both brother and son stays unresolved.
3. A `Vetter` pointing only at X's brother is blocked (documents) or penalized
   (books).
4. An attachment that creates a mention after death or an impossible age is
   blocked.
5. Two leftovers that cannot be one person, both proposed for the same identity,
   are both rejected as competing.
6. Pass-2 attachments do not support other attachments: adding a second
   leftover that only fits through the first stays unresolved.
7. Results are identical under reversed input order.
8. Detached leftovers and lone mentions receive no structural evidence.

Cases 1–3 and the kinship-term parsing are tested in `tests/test_probability.py`.
Cases 4–8 rely on the shared pass-1 checks and are not yet tested separately.

## Open questions

1. Are the kinship meanings above right, especially `Oheim` (uncle and
   nephew), `nepotes` (nephew or grandson), and `fratrueles` (nephew or
   cousin)?
2. Specificity factors `1.0 / 0.5 / 0.3` and elimination `1.5`: acceptable?
3. Should lone `death` mentions be attachable? A wrong death attachment blocks
   later merges; a right one prevents posthumous merges.
4. Book retellings of a documented event (same day, same participants, such as
   Kreis Mosbach on the 1381 Boxberg sale) could be matched as one event. This
   needs no tree and belongs in pass 1. Should it be designed separately?
