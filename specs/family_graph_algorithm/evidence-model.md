# Evidence model

The pairwise comparison used by passes 3 and 4 (`ProbabilityModel.compare` in
`probability.py`). All values come from `data/matching.json`; the numbers below
are the current configuration. Worked arithmetic is in
[weight-calculation-examples.md](weight-calculation-examples.md).

## Log-odds

```text
L = ln(prior / (1 - prior)) + Σ feature contributions      prior 0.10 → L₀ = -2.197
P = 1 / (1 + exp(-L))
reliability(assertion) = source factor × (guessWeight 0.45 if a guess)
source factor: documents, images 1.0; books, notes 0.5
pair reliability = min(reliability of the two assertions supplying the feature)
positive contribution = base × pair reliability × 2^(-gap / halfLife)
```

`gap` is the distance in years between the two attestation intervals (`0` when
they overlap). For each feature the strongest pair of observations counts once;
repeated extraction adds nothing. The probabilities are uncalibrated.

## Positive features

| Feature | Base | Half-life | Notes |
| --- | --- | --- | --- |
| Office title (`Vogt zu Lauda`) | 8 | 15 | Office word and place; connector and prefix ignored |
| Designation (`genannt X`, `von X`, `zu X`, `dictus de X`) | 6 | 30 | The place or name alone |
| Shared office place | 3 | 15 | Different offices of one place, or an office and a designation of its place; only without an exact office or designation match |
| Age title | 3 | 12 | Same age title |
| Rank (`Ritter`, `Edelknecht`) | 0.75 | 20 | Never enough on its own |
| Other epithet (`Rufus`) | 1 | 15 | |
| Property place | 4 | 20 | Text mentions property, fief, rent, sale … |
| Context place | 2.5 | 20 | |
| Issuance place | 2 | 20 | Place of the document |
| Same-fact associate | 2 | 15 | `X von Y` named in the same fact; total capped at 4 |
| Financial counterparty | 4 | 15 | "was paid/owed … by X" on both sides; replaces the associate weight, same cap |
| Family | see below | 35 | Total capped at 16 |

Titles are compared by meaning: equivalents from `data/titles.md`, place
variants from `data/places.json`. Office words are `Vogt`, `Amtmann`,
`Hofmeister`, `Burggraf`, `Domherr`, `Vizedom`, `Komtur`, `Keller`,
`Schultheiß`. One strongest title per category counts. A title on a
deceased-marked mention or a death record is dated to the
`retrospectiveLookBackYears` (20) before the death bound.

Places: one strongest observation per place; a place in different roles on the
two sides uses the weaker role times `crossRolePlaceFactor` (0.5). Personal
names are removed before place matching, so a surname is not a residence.

### Family

A shared relative is a relative with the same name in the same role on both
sides (parent, child, sibling, spouse, kin), or a co-parent of a common child.

| Relative identified as | Base |
| --- | --- |
| Registry ID | 9 |
| Linked identity | 7.5 |
| Unresolved full spouse name | 9 |
| Other unresolved full name | 4 |
| The same identity as sibling, parent or spouse | max(base, `sharedRelativeWeight` 12) |

The base is multiplied by the relation factor (parent, spouse 1.0; sibling 0.8;
kin 0.5), the pair reliability, the membership confidence of the relative
mentions, and the decay. A bare given name without a resolved identity adds
nothing. A full relative name also adds a rarity bonus,
`min(1.5, ln(0.1 / frequency))` with add-one smoothing over factual name
counts (`matchingBackground`), within the family cap.

Same-named repeated parents of one child are not co-parent evidence.

## Chronology

Each identity has, per reliability level, a latest birth, death bounds, and
first and last living mentions:

- an unmarked typed mention means alive at its date, except the parent in a
  `parent` fact, both people in a `sibling` fact, and a speculative "may have
  been the parent of" guess;
- a deceased marker or a death fact gives a death bound; alternative guessed
  death dates of one passage form one interval;
- a rank, office, `der Ältere`/`der Alte`, being a parent or a spouse means born
  at least `adultAgeYears` (16) before the date;
- a recorded parent's death bounds the child's birth: born at most
  `posthumousBirthYears` (1) after it.

Partial dates are read permissively.

## Penalties

| Situation | Contribution |
| --- | --- |
| Minimum age above `ageComfortYears` 60 | `-(age - 60) / 10 × reliability`, only the increase over both parts |
| A child's implied age above 60, born at most a year after a parent's death | same scale |
| Elder age title before younger | `-5 × reliability` |
| Ritter before Edelknecht | `-1 × reliability` |
| Ritter and Edelknecht on the same day in two sources | `-3 × reliability` |
| Mention after death, incompatible death dates, impossible age | `-20 × reliability` |

Younger before elder and Edelknecht before Ritter are neutral. Time distance
alone is neutral.

## Blocks

**Pass-3 blocks** make a pair ineligible (status `incompatible`, reason
`blocked: …`):

- mention after death, incompatible death dates or impossible age (above
  `maxAgeYears` 80) when the conflicting records are document facts;
  otherwise these are penalties;
- a child born after the parent's death, on document facts;
- Ritter and Edelknecht on the same day in two documents;
- explicitly distinct relationship participants;
- distinct registry IDs; different father or mother.

**Pass-4 hard blocks** are stricter, for every source type:

- any impossible age;
- mention after death or incompatible death dates between facts (guesses
  excluded);
- living mentions spanning more than `bestCandidate.maxLivingSpanYears` (64);
- any child born after the parent's death beyond the age limit;
- the other pass-3 blocks, known relatives, and kinship-term exclusions.

### Known relatives

Two identities related through the tree may only be one person if every
relationship path between them (up to `bestCandidate.maxRelativePathSteps`, 6)
keeps them in one role:

- both in one sibling group (siblings, children of one parent, or of the
  parent's spouse);
- both parents of one sibling group;
- both spouses of one person;
- the spouse of X and the other parent of X's child.

Any other path blocks (`known relatives: C-S`): father and son, grandfather and
grandson, uncle and nephew, cousins, in-laws. Inherited fathers are not part of
these paths.

### Omitted surname

A record without a surname joins a full-name record only with family evidence
or an office or designation title. In pass 4, a kinship position, corroborated
parentage or the widow attachment also count.
