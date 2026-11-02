# Pass 1: passage resolution

Rule: same-name occurrences in one passage are one person unless something
distinguishes them ([domain rules](domain-rules.md#what-makes-two-records-different-people)).

## Distinctions within a passage

A **passage** is one source entry at one historical date. Two same-name
mentions of one passage are different people if:

- they are the two participants of one relationship fact;
- they carry different age titles (`der Ältere`, `der Jüngere`, `der Junge`,
  `der Alte`);
- one is a knight (`Ritter`, `miles`) and the other a squire (`Edelknecht`,
  `armiger`). `Knecht` alone does not distinguish; a mention with both ranks
  has no rank;
- one has an explicit deceased marker and the other is an unmarked living
  mention. Being named as a parent or sibling, a death fact, and speculative
  "may have been the parent of" guesses are neither;
- they are the subjects of two separate `generic` facts with the same content
  (two "Hans" in one witness list);
- grouping them fails the [merge check](algorithm.md#merge-check).

## Grouping

For each passage, all same-name groups are solved together:

1. Find the groupings into the **fewest people** that pass the merge check
   (search bounded at 200 000 states).
2. Score each grouping by title agreement: per pair of parts in one person,
   one point if they share a rank, office, designation or age title, and one
   more if a death record joins an explicitly deceased mention; the total is
   multiplied by `passageTitleAgreementWeight`.
3. Keep the highest-scoring groupings. Two parts that are together in all of
   them merge. Parts together in only some are **tied**: they stay separate, and
   in pass 4 a tied record joins nothing on time or family tie-breaks.

The pass repeats until it merges nothing more. Merges have membership
confidence `1.0`.

Example: Kreis Mosbach entry 3 (1381-05-25) yields one Konrad Ritter, one
Konrad Edelknecht, one Eberhard Ritter and one Arnold Edelknecht; the untitled
"may have been a brother" Konrad stays unresolved.

## Repeated attestations

After the passage step, two relationship assertions with the same historical
date, the same specific citation (a charter, regest or item number), the same
type, names, titles and kinship term are one attestation: their participants
merge pairwise.

## Prose context

Prose is not turned into relationships. A literal `X von Y` name in a fact's
text attaches that fact's places and associates to a person when it resolves to
exactly one same-name mention of the passage with an overlapping date. A
bracketed registry ID (`[vogt_zu_Lauda]`) attaches directly. An informative
prose-only name (one whose places and associates could reach the merge
threshold, and which occurs once in the fact) becomes a context mention: it can
join identities but never creates a family edge.
