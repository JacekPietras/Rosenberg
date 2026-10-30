# Family reconstruction specification

This document defines the matching behavior implemented by engine 6
(`weighted-log-odds-v3`).

## Weight calculation convention

Weights are additive **log-odds contributions**, not percentage points:

```text
L = ln(prior / (1 - prior)) + sum(eligible evidence contributions)
P = 1 / (1 + exp(-L))
reliability(assertion) = source factor × (guess factor if guessed, else 1)
pair reliability = min(reliability(left), reliability(right))
positive contribution = base weight × pair reliability × 2^(-gap / halfLife)
```

Use each underlying signal once, applying category caps before summing. The
prior is applied once per comparison. Blocks decide merge eligibility separately;
a blocked merge is reported as a conflict, not displayed as a 0% probability.

[Worked calculations](weight-calculation-examples.md) illustrate the arithmetic.

## Evidence and output

- Compare all source people, including those without registry IDs. A matching
  name retrieves candidates; it does not establish identity and adds `0`.
- Keep exact registry IDs fixed and distinct. Distinct fixed IDs block merging.
- Read facts and guesses under `data/`, following `rules/facts.md` and
  `rules/json-formats.md`. Never use publication dates as historical dates or
  rewrite source facts to confirm an inferred identity.
- Include guesses in the normal result; retain a facts-only audit view.
- Keep `people.json` as the confirmed ID/name registry. Store generated
  identities, relationships, alternatives, calculations, and parameters in
  `tree.json`. One card per reconstructed identity.
- Source factors: documents/images `1.0`, books/notes `0.5`; guesses multiply by
  `0.45`, giving `0.45` and `0.225`.

## Blocks and conflicts

A **block** makes a merge ineligible regardless of positive evidence. A
**conflict penalty** is a large negative contribution,
`-deathConflictPenalty × pair reliability` (`20` currently).

| Situation | Both sides document/image facts | Otherwise (book/note fact or guess) |
| --- | --- | --- |
| Mention after death | Block | Penalty |
| Incompatible death dates | Block | Penalty |
| Impossible age | Block | Penalty |
| Explicit distinction | Block | Block |

### Death

- Every mention in any fact type without `personDeceased`/`ofDeceased` means
  the person was alive at that fact's historical date.
- A death fact or a deceased marker gives a death bound. A deceased marker at a
  date means death occurred before or at that date; it is not a death date.
- Within a proposed identity, keep the earliest death bound. An unmarked mention
  dated after it is a mention after death. Several `diedBefore` bounds never
  conflict with each other; `diedOn` dates that disagree, or a `diedOn` after a
  `diedBefore` bound, are incompatible death dates.
- Later mentions marked deceased remain compatible with earlier death.
- Compatible death information contributes `0`; it is neither a bonus nor a
  penalty.
- Partial dates are intervals. A conflict exists only if every possible date
  combination conflicts.

Because unmarked mentions count as living, facts must set the deceased markers
whenever the source identifies a participant as dead.

### Explicit distinctions

Two participants of the same fact are different people. Two people with the
same name distinguished in one entry (for example `der Ältere`, `der Jüngere`
and `der Junge` together) are different people. No chain of merges may join
them, create self-relationships, or create ancestry cycles.

## Estimated age

Each proposed identity has an estimated birth interval `[earliest, latest]`,
derived only from source-stated evidence. No point estimate of birth is made.

| Evidence at date `d` | Constraint |
| --- | --- |
| Any unmarked mention | Born no earlier than `d - maxAgeYears` |
| Rank or office title (Ritter, Edelknecht, Vogt …) | Born no later than `d - adultAgeYears` |
| Parent in a `parent` fact | Born no later than `d - adultAgeYears` |
| Spouse in a `spouse` fact | Born no later than `d - adultAgeYears` |
| `der Ältere` / `der Alte` | Born no later than `d - adultAgeYears` |
| `der Jüngere` / `der Junge`, child in a `parent` fact | No age constraint |

Parameters: `adultAgeYears` `16`, `maxAgeYears` `80`, `ageComfortYears` `60`,
`ageScaleYears` `10`.

For a proposed identity:

1. Intersect all constraints. An empty interval is an impossible age (see the
   table above).
2. Otherwise compute the minimum age the identity must have at its last unmarked
   mention: `minAge = last mention - latest birth`. Use the most permissive
   reading of partial dates.
3. Age penalty = `max(0, minAge - ageComfortYears) / ageScaleYears ×
   reliability`, taking the strongest value over reliability levels (each level
   uses records of that reliability or higher).
4. A comparison contributes only the increase of the merged identity's penalty
   over the larger penalty of its two parts, so years already accepted inside
   one identity are not charged again.

Mentions marked deceased do not extend the last mention. Time distance itself
adds no penalty; long gaps lower the score only through the age contribution and
through the fading of title, place, associate, and family evidence.

Example: someone called `der Ältere` in 1300 and mentioned alive in 1357 must be
at least 72 in 1357 (`-1.2`; end of 1300 to start of 1357). A `der Jüngere` from 1300 has no adult constraint
and needs only age 57 (`0`). This favors the younger candidate without
inventing a birth year.

## Titles

| Category | Examples | Base | Half-life (years) |
| --- | --- | --- | --- |
| Office | `Vogt zu Dürn`, `Amtmann zu …` | 8 | 15 |
| Called/born designation | `genannt …`, `dictus …` | 6 | 30 |
| Territory | `zu Boxberg` | 3 | 15 |
| Age | `der Ältere`, `der Jüngere`, `der Alte`, `der Junge` | 3 | 12 |
| Rank | `Ritter`, `Edelknecht` | 0.75 | 20 |
| Other | epithets like `Rufus` | 1 | 15 |

- Matching titles contribute `base × pair reliability × decay`. Missing titles
  contribute `0`.
- An office's place cannot earn a separate place contribution for the same
  observation.
- Rank: Edelknecht earlier → Ritter later is normal and contributes `0`. Ritter
  earlier → Edelknecht later contributes `-rankRegressionPenalty × pair
  reliability` (`1` proposed).
- Age titles: `der Jüngere`/`der Junge` earlier → `der Ältere`/`der Alte` later
  contributes `0`. The reverse is unlikely: `-opposedAgePenalty × pair
  reliability` (`5`). Same-entry distinctions are blocks, not penalties.
  Preserve `der Junge`/`der Alte` separately from `der Jüngere`/`der Ältere`.

## Places, associates, and family

- **Places** (resolved via `places.json`): `property 4`, `context 2.5`,
  `issuance 2`, half-life `20`. Cross-role matches multiply by `0.5`. One
  strongest observation per place. A surname place adds `0`.
- **Associates:** a non-family person named in the same fact, `2` each, capped
  at `4`, half-life `15`. Co-occurrence never creates kinship.
- **Family:** `identification base × relation factor × pair reliability ×
  decay`, using the strongest applicable category per relative and capped at
  `16` total.

| Relative identified as | Base |
| --- | --- |
| Registry ID | 9 |
| Linked reconstructed identity | 7.5 × link confidence |
| Unresolved full spouse name | 9 |
| Other unresolved full name | 4 |

An unresolved spouse pairs two families' names, so it is more distinctive than
a relative's name that repeats across generations.

| Relation | Factor |
| --- | --- |
| Parent/child | 1.0 |
| Spouse | 1.0 |
| Sibling | 0.8 |
| Other kin | 0.5 |

Family half-life `familyHalfLifeYears` (`35`). The name rarity adjustment stays
separately capped. A relative's title or late activity belongs to the relative.
Do not confirm children through parents inferred from those same children;
repeated extraction or iteration adds `0`.

## Decisions

- One global configuration in `data/matching.json`, recorded with each build.
  Prior `0.05`, merge threshold `0.85`, rival margin `1.0` log-odds. Estimates
  are **uncalibrated**.
- `prior 0.05` gives initial log odds `-2.944`; `P = 0.85` needs `1.735`, so
  about `4.679` net positive evidence is required.
- Check blocks on every proposed complete identity, including transitive merges,
  before accepting a merge.
- A record that fits several candidates (for example father, son, or cousin of
  the same name) is compared with all of them. Leave it unresolved when the
  leader's margin is below `1.0`. Probabilities are pairwise, not shares.
- Results must not depend on input order.
- Explain every decision with source pointers, dates, contributions, birth
  interval and minimum age, blocks, and rival candidates. Generate only
  source-stated relationships.

## Required regression cases

1. **1300 elder versus Vogt zu Dürn:** `1300-05-17.json` marks the elder father
   deceased. Any later unmarked mention of the Vogt blocks merging that father
   into his identity. The parent fact and its unresolved name are unchanged.
2. **1300 younger versus Vogt:** the younger son remains a candidate. The 1357
   issuer and deceased namesake are matched separately.
3. **Age titles:** younger → elder decades later is compatible; elder → younger
   is penalized; same-entry elder/younger/junge are blocked from merging.
4. **Age:** a merge needing age above 80 is blocked (facts) or penalized
   (books/guesses); age between 60 and 80 is penalized progressively.
5. **Death:** deceased-marked later mentions remain compatible; two compatible
   `diedBefore` bounds remain compatible; an unmarked mention after death blocks
   (documents) or is penalized (books/guesses).
6. **Ranks:** Edelknecht → Ritter has no penalty; Ritter → Edelknecht has the
   rank penalty; missing rank is neutral.
7. **Family:** parent/child outweighs sibling outweighs other kin; circular
   support adds `0`.
8. **Controls:** greater distance weakens title/place/family support; guesses
   and books contribute less; distinct IDs and distinctions are inspectable.

Each regression asserts the sign and magnitude of the relevant contribution,
not only the final merge.

## Implementation status

Implemented in `scripts/family_graph/` (`probability.py`, `reconstruction.py`,
`graph.py`) with the configuration in `data/matching.json`. Regression tests are
in `tests/test_probability.py` and `tests/test_family_graph.py`.

- The 1300 deceased elder is no longer part of `vogt_zu_Durn`.
- Proposed merges are blocked for impossible age, mention after recorded death,
  and explicit distinctions; the viewer shows them as blocked.
- A confirmed ID whose own document facts conflict is reported as `REVIEW`
  during rebuild. Currently: `vogt_zu_Lauda` (died before 23 June 1387) is
  named without a deceased marker as father in `1395-01-27.json`.

```sh
python3 scripts/rebuild_family_tree.py
python3 scripts/rebuild_family_tree.py --include-guesses --explain vogt_zu_Durn
```

Do not lower merge thresholds or add person-specific exceptions to obtain an
expected result.
