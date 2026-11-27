# Pass 1: passage resolution

Rule: same-name occurrences in one passage are one person unless something
distinguishes them ([domain rules](domain-rules.md#what-makes-two-records-different-people)).

## Distinctions within a passage

A **passage** is one document, or one other source entry, at one historical date. Two same-name
mentions of one passage are different people if:

- they are the two participants of one relationship fact;
- they carry different age titles (`der Jüngere`, `der Junge`, `der Ältere`,
  or `der Alte`); each form is kept distinct as specified in
  [`facts.md`](../facts.md#titles);
- one is a knight (`Ritter`, `miles`) and the other a squire (`Edelknecht`,
  `armiger`). `Knecht` alone does not distinguish; a mention with both ranks
  has no rank;
- one has an explicit deceased marker and the other is an unmarked living
  mention. Being named as a parent or sibling and a death fact are neither;
- grouping them fails the [merge check](algorithm.md#merge-check).

## Grouping

For each passage, all same-name groups are solved together:

1. Find the groupings into the **fewest people** that pass the merge check
   (at most 20 000 partitions per name and size, and 200 000 joint
   groupings). Exhausting either budget leaves the passage undecided and its
   competing mentions tied for subsequent tie-breaking.
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

Prose is not turned into relationships, and the algorithm does not read prose.
The `mention` list generated for a document lists the people its entries name beyond
its facts' participants, and its places. The document's company is those people
united with the typed participants (`person`, `of`) of its facts and, in the
with-guesses view, guesses. Every typed participant gets the document's places and
the rest of the company as associates, except the other participant of its own
relation fact (already family evidence) and except when the passage holds
several same-name people with overlapping dates, since their company cannot be
told apart. An informative prose-only name (one whose places and
associates could reach the merge threshold) becomes a context mention: it can
join identities but never creates a family edge. Registry IDs are read only
from typed fields.
