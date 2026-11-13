# Pass 4: best-candidate joining

Rule: every identity joins its most probable same-name candidate unless
something forbids it ([domain rules](domain-rules.md#identity)). There is no
probability threshold; the join needs some real evidence.

## Candidates

Every identity with a typed mention takes part, including registry identities
(two registry IDs never join). Candidates are the identities with compatible
names. Each candidate starts from the [evidence model](evidence-model.md) score
of the pair and its pass-4 hard blocks, plus distinct registry IDs, different
father or mother, and known relatives.

## Kinship features

For each relationship of the identity to a relative X, the paths from X to the
candidate (up to `secondPass.maxPathSteps`, 3) are read against the term's
positions in `data/kinship.md`. Direct `parent`, `sibling` and `spouse`
relations are exact positions; an unknown term allows any position.

| Feature | Contribution |
| --- | --- |
| Kinship position: the candidate sits where the term allows | `sharedRelativeWeight 12 × specificity × reliability × membership of X × decay`; specificity exact 1.0, narrow 0.5, broad 0.3; skipped if the shared-relative feature already counts X; family cap 16 |
| Kinship exclusion: every path is excluded (a `Vetter` who is X's brother) | block |
| Only candidate: exactly one unblocked candidate sits in an allowed position | `eliminationWeight 1.5 × weakest relation reliability` |
| Age-title namesake: `der Ältere` (`der Jüngere`) implies a same-named relative in that passage; the candidate is one generation above (below) him | `ageTitleNamesakeWeight 1 × reliability` |
| Widow: a standalone widow record and a same-full-name family spanning several passages with earlier widowhood | `widowhoodNameWeight 5 × weaker reliability` |
| Speculative parent: "may have been the father of X", where the same-named candidate is X's recorded factual parent and X is established | `12 × min(source factor, parent fact reliability) × X's confidence` |

## Choice

1. Remove blocked candidates.
2. A candidate is eligible when the net evidence (`L - L₀`, penalties
   included) is at least `bestCandidate.minJoinEvidence` (0.5) from a positive
   feature other than rank, and, for a record without a surname, there is
   identifying support (family, office or designation title, kinship position,
   corroborated parentage, widow attachment).
3. Take the best eligible candidate. If others are within
   `bestCandidate.attachmentTieLogOdds` (0.25):
   - prefer the only one with family evidence or a kinship position;
   - otherwise the nearest in time, if unique;
   - otherwise the identity stays separate, with `possiblySame` links to each
     tied candidate.
   A record tied in [pass 1](pass-1-passage-resolution.md) does not use these
   tie-breaks.
4. Share of the chosen candidate: `exp(L) / (1 + Σ exp(L_j))` over unblocked
   candidates; the `1` is the identity being a separate person. The joining
   side's mentions multiply their membership confidence by it.

## Round

- All identities are scored against the frozen state of the round.
- Choices are accepted in descending log-odds. Each identity takes part in at
  most one join per round. A choice is re-checked against the live state
  (registry IDs, known relatives, [merge check](algorithm.md#merge-check)); if
  refused, the identity tries its next eligible candidate.
- A choice is skipped when the candidate itself is tied between this identity
  and another.
- After the round the [family closure](family-closure.md) runs. Rounds repeat
  until nothing joins; identities never split, so this ends.

## Output

Comparisons store `stage: 4`, `share`, status (`merged`, `below-threshold`,
`ambiguous`, `incompatible`) and reason. Unblocked candidates with probability
of at least `possibleSameDisplayProbability` (0.5), and tied ones, become the
node's `possiblySame` links. A node's `identityProbability` is the lowest
membership confidence of its mentions.
