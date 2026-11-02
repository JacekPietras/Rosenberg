# Pass 0: same name and titles in one section

Rule: within one section, records with the same name and the same titles are
one person ([domain rules](domain-rules.md#identity)).

## Before grouping

- Mentions with an exact registry ID are already one identity per ID and do not
  take part.
- Kinship terms are normalized to the first form of their group in
  `data/kinship.md` (`swager` → `Schwager`). Source facts keep their wording.

## Grouping

A **section** is one document file, or one entry of a book, notes or images
file. Typed mentions are grouped by section, normalized name, and the set of
title meanings (`title_category`): `Vogt in Lauda` and `Vogt zu Lauda` are the
same title, and two untitled mentions have the same empty set. A titled and an
untitled mention are not grouped here.

In each group, mentions are taken in date order. A mention joins a cluster only
if the joined identity passes:

- the [merge check](algorithm.md#merge-check);
- the known-relatives check;
- the chronology hard blocks of the evidence model: impossible age, mention
  after death, incompatible death dates, living mentions spanning more than
  `bestCandidate.maxLivingSpanYears`.

A mention that fits exactly one cluster joins it; one that fits none starts a
new cluster; one that fits several stays for later passes.

## Acceptance

Proposals are accepted strictly: when clusters of one family conflict with each
other, none of the conflicting ones is merged, so pass 0 never chooses between
alternatives. Merges are unweighted; their membership confidence is `1.0`.

Example: Bauer section 24's "Eberhard der Ältere" of 1380, 1383, 1385 and 1407
is one person, so his 1407 mention later blocks a join to the Vogt zu Lauda.
