# Pass 3: confident linking

Makes the well-supported merges first, so that pass 4 scores against
better-built identities. Uses the [evidence model](evidence-model.md).

## Round

Rounds repeat until nothing merges, at most `maxRounds` (12). Each round:

1. Build frozen profiles of all current identities: titles, places,
   associates, relatives, ranks, chronology and distinctions.
2. Compare every pair of identities with compatible names. Pairs with no
   substantive evidence (only name, date or age) are not stored.
3. Mark a pair `incompatible` when it holds two registry IDs, has different
   fathers or mothers, has a pass-3 block, or lacks the surname support
   required for a record without a surname.
4. A pair with probability of at least `mergeProbability` (0.70) is an option
   for both sides.
5. For each identity, take its options within `ambiguityLogOddsMargin` (1.0)
   of its best. Skip them if they span two registry IDs. Propose a pair only if
   it is also within the margin of the other side's best (reciprocal choice).
   Otherwise the pair is `ambiguous` and left to pass 4.
6. Accept proposals as complete components: a component is refused if two of
   its members compare below `clusterMinimumProbability` (0.35) with negative
   evidence, if it fails the [merge check](algorithm.md#merge-check), or if
   its parts are known relatives. Components in one connected family are then
   checked together; those that stay consistent are kept in a fixed order.
7. Run the [family closure](family-closure.md).

Merged mentions multiply their membership confidence by the pair probability
that linked them to the identity's core.

## Statuses

| Status | Meaning |
| --- | --- |
| `merged` | Probability, margin and cluster checks passed |
| `below-threshold` | Below 0.70; pass 4 may still join it |
| `ambiguous` | Competing candidates within the margin |
| `incompatible` | Blocked, or the complete cluster failed the merge check |

Comparisons store `stage: 3`, the round as `iteration`, every feature and its
sources.
