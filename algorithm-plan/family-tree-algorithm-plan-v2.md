# Family reconstruction specification, version 2

Replaces [family-tree-algorithm-plan.md](family-tree-algorithm-plan.md) and
[second-pass-plan.md](second-pass-plan.md) once implemented. Worked arithmetic
stays in [weight-calculation-examples.md](weight-calculation-examples.md) and
must be updated with the new prior.

## Why a new version

Version 1 guards only against false merges. Its blocks, penalties, unanimity
rule, rival margins and "attach, never join" all push toward splitting, and
every regression case asserts a non-merge. Discounts multiply (source × guess ×
link confidence × decay) against a 5% prior, so some record types can never
reach the threshold. Example: the four 1381 Boxberg purchasers in Kreis Mosbach
produce five separate `Konrad von Rosenberg` siblings of `vogt_zu_Lauda` and his
brother Arnold, none linked to the documented Konrad, Ritter, Vitztum zu
Heidelberg, who issued his own Boxberg charter on the same day.

Observed causes in version 1:

- Kreis Mosbach entry 3 has 11 Konrad occurrences. Nothing distinguishes the
  Ritter from the Edelknecht, so the grouping search finds hundreds of minimal
  groupings and exceeds its search limit; no occurrence is merged and the
  passage's factual titles and context reach no identity.
- Bauer 1395: "1 Arnold + 2 Eberhards" and "2 Arnolds + 1 Eberhard" are both
  three-person groupings, so Arnold der Junge is not unanimous and stays split.
- A shared relative between two book guesses reaches at most
  `12 × 0.225 = +2.7` (`+2.0` with link confidence `0.74`), below the `+3.79`
  needed; such records can never merge.
- Link confidence is the cluster minimum, so one weak merge into a registry
  person discounts every family feature of everyone related to him.
- Titles on "the late …" mentions are decayed from the posthumous date.
- No feature links a book retelling to the charter it retells.

Version 2 keeps the log-odds model and every block, and adds:

1. **Two error directions.** False splits are errors, measured and tested like
   false merges.
2. **Passage first.** Same-name occurrences in one passage are one person by
   default, split only when forced.
3. **Evidence carries its own reliability.** Guess and link discounts apply only
   to features derived from the guessed claim or uncertain link.
4. **Prior 0.10** instead of 0.05.
5. **Best candidate for everyone.** Every identity, however many sources it
   has, joins its most probable same-name identity unless a hard block forbids
   it, so separate family trees join through it. Known relatives (father and
   son, uncle and nephew, cousins) never join; two records of one sibling group
   may. The threshold only decides
   which merges happen first.
6. **Same-named relatives in one role are one person** unless blocked.

## Stages

```text
0. Same document/section  same name and same titles (or both untitled), any year (merges)
1. Passage resolution     occurrences → passage people (merges)
3. Confident linking      pairs above 0.70, threshold-based (merges)
4. Best-candidate joining every identity → most probable unblocked
                          identity, no threshold (merges)
```

Stage 2 (matching transaction types across sources) was dropped: same-day
shared places and same-fact associates already link a book retelling to its
charter, and best-candidate joining needs no extra feature to reach a
threshold. Stage numbers are kept as they appear in `tree.json`.

Blocks are checked on every proposed complete identity at every merging stage.
The known-relatives block (stage 4) applies to every merge, in every stage.
Results must not depend on input order.

## Reliability

```text
source factor: documents/images 1.0, books/notes 0.5
claim reliability(assertion) = source factor × (guessWeight 0.45 if guess)
feature reliability = min over the two sides of the claim reliability of the
                      assertions that supply that feature
link factor = membership confidence of the specific relative mention used
```

- A feature uses the reliability of the assertions that produce it, not the
  weakest assertion of the identity. A guessed sibling relation is scored at
  `0.225` in a book; the same person's factual title in that passage at `0.5`.
- **Membership confidence** of a mention is the maximum, over paths of accepted
  merges from that mention to the identity's registry mention (or, without one,
  to its stage-1 passage person with the most occurrences), of the product of
  the merge probabilities on the path. Stage-1 merges and registry IDs count
  `1.0`. It replaces the cluster minimum.

## Pass 0: same document or section

Normalize kinship terms to the first form in each group in `data/kinship.md`
before comparing or grouping relationships (for example, `swager` becomes
`Schwager`). Generated relationships use that form and retain all supporting
source references; source facts keep their original terms.

Within one document file, or one book, notes or image section (entry),
occurrences with the same normalized name and the same set of titles by meaning
are one person, whatever their dates. Two untitled occurrences have the same
(empty) set, which matters most for women, who are rarely titled. A titled and
an untitled occurrence are not merged here; later stages decide.

Occurrences are taken in date order and added to the first group they can join
without a block: explicit distinctions, known relatives, generation and cycle
checks, death conflicts between facts, impossible age, and living mentions
spanning more than `maxLivingSpanYears`. These merges are not weighted: their
membership confidence is `1.0`, and later stages score the combined, richer
profiles.

Example: Freiburger entry 182 says Eberhard died in 1519 and, separately (dated
1527), that he died before 1528; Bauer section 24's "Eberhard der Ältere" of
1380, 1383, 1385 and 1407 is one person, so his 1407 mention blocks a later join
to the Vogt.

## Stage 1: passage resolution

A **passage** is one source entry at one historical date: path, entry pointer,
date. Occurrences are typed `person`/`of` mentions in its facts and guesses, and
literal names in its prose under the version 1 rule (a literal name occurring
more than once in one fact is not added, because it may distinguish namesakes).

### Hard distinctions within a passage

Two occurrences are different people if:

- they are the two participants of one relationship fact;
- they carry different age designations (`der Ältere`/`der Jüngere`/`der Junge`/`der Alte`);
- one carries a knightly rank and the other a squire rank (`Ritter`/`miles` versus `Edelknecht`/`armiger`). `Knecht`
  alone does not distinguish, since it can mean a servant;
- one carries an explicit `personDeceased`/`ofDeceased` marker and the other is
  an unmarked mention. A `death` fact is not a marker: its occurrence joins the
  deceased-marked group if there is exactly one, otherwise it is grouped
  normally;
- they are the subjects of two separate facts of the same type with the same
  content (two "Hans" in one witness list);
- merging them breaks generations (parent one above child, siblings equal),
  creates a self-relationship, or creates an ancestry cycle.

A single mention carrying both ranks (`Ritter`, `armiger`) is a data problem; its
rank is ignored for distinctions and penalties and reported for review.

The rank distinction was checked on current data: all four same-passage rank
conflicts (Kreis Mosbach 3, `1381-07-26`, `1323-03-17` father Ritter and son
Knecht) are genuinely different people.

### Grouping

1. Solve for groupings of same-name occurrences into the **fewest people** the
   hard distinctions allow, using a constraint solver that always returns a
   result (no enumeration limit that yields "nothing").
2. Score each grouping by title agreement inside each group: identical rank,
   office or designation `+1` per pair; a title on one side only `0`.
3. Take the highest-scoring groupings. Merge every pair that is together in
   all of them. Occurrences split across top groupings stay unresolved within
   the passage and go to stage 3 as separate records. A death-fact occurrence
   attached to the deceased-marked group (see above) is fixed before scoring
   and is not re-grouped.

Kreis Mosbach entry 3 then yields one Konrad Ritter, one Konrad Edelknecht, one
Eberhard Ritter, one Arnold Edelknecht, and the untitled "may have been a
brother" Konrad unresolved. Bauer 1395 yields three people because the father
carries `personDeceased`.

### Prose context

Prose context attaches to a passage person when the literal name resolves to
exactly one passage person. A passage person keeps every occurrence's titles,
places and associates, each at its own claim reliability.

## Stage 3: identity linking

### Prior

Fixed `priorProbability` `0.10` (initial `L = -2.197`; `0.70` needs `+3.045`).
A name-frequency scaling of the prior, computed once from the inputs, is an
open question.

### Evidence

Positive evidence: `base × feature reliability × link factor × decay`.

| Category | Base | Half-life |
| --- | --- | --- |
| Office (`Vogt zu Lauda`, `Vizedom zu Heidelberg`) | 8 | 15 |
| Designation (`genannt X`, `von X`, `zu X`) | 6 | 30 |
| Shared place of office/designation only | 3 | 15 |
| Age title | 3 | 12 |
| Rank | 0.75 | 20 |
| Other epithet | 1 | 15 |
| Property place | 4 | 20 |
| Context place | 2.5 | 20 |
| Issuance place | 2 | 20 |
| Associate (cap 4) | 2 | 15 |
| Financial counterparty | 4 | 15 |
| Family, registry relative | 9 | 35 |
| Family, linked relative | 7.5 | 35 |
| Family, unresolved spouse full name | 9 | 35 |
| Family, other unresolved full name | 4 | 35 |
| Shared identified relative in same role | 12 | 35 |

Relation factors, caps (family `16`), relative-name rarity, title equivalence
(`data/titles.md`), place variants (`places.json`) and the rule that each signal
counts once are unchanged from version 1.

### Retrospective titles

A title on a mention with an explicit deceased marker, or on a death record,
describes the person's past. Its attestation interval is
`[death bound - retrospectiveLookBackYears (20), death bound]`. Decay uses the
distance between attestation intervals. "The late Konrad, Vizedom zu Amberg"
(1401) is therefore compared as an office held 1381–1401, but does not match a
father who held the same hereditary office 50 years earlier at full weight.

### Parents named after their death

The parent in a `parent` fact, and both people in a `sibling` fact, are not
living mentions: "Albrecht, son of Eberhard" (1555) and "Kunz, brother of
Eberhard" (1555) are compatible with Eberhard's death in 1519. The parent must
still have been an adult. The relation instead bounds the child: born at most
`posthumousBirthYears` (`1`) after the parent's death bound. That bound enters
the child's birth interval, so the ordinary age penalty and impossible-age block
apply (a father dead in 1300 makes a son alive in 1375 at least 74).

The 64-year living span and an impossible age (any source type) are checked on
every proposed identity in every stage.

### Penalties, blocks and age

New: same-date opposite ranks across sources (Ritter/miles versus
Edelknecht/armiger on compatible day-precision dates) contribute
`-sameDateRankConflictPenalty (3) × reliability`, and block when both sides are
document facts.

Unchanged from version 1: mention after death, incompatible death dates,
impossible age (block when both sides are document facts, otherwise
`-20 × reliability`); explicit distinctions always block; opposed age titles
`-5`; Ritter → Edelknecht `-1`; progressive age penalty above 60; same-named
parents or spouses of one person must be one person; generation consistency.

### Decision

Stage 3 makes the well-supported merges first, so that stage 4 scores against
better-built identities. Everything it leaves separate goes to stage 4.

- Merge threshold `0.70`, rival margin `1.0` log-odds, cluster minimum `0.35`.
- Rounds repeat until no merge (`maxRounds` `12`). Profiles are frozen within a
  round; all proposals of a round are checked together.
- A candidate within the rival margin `1.0` of another is not merged in stage
  3; stage 4 then decides with its own tie rule.

## Same-named relatives

Two same-name people standing in the same role to one identified person (both
siblings of Z, both parents of Z, both spouses of Z, both children of Z) are one
person unless a hard block separates them. This is applied after every merging
round as a merge, not as evidence, when both relative mentions belong to Z with
membership confidence `≥ 0.7`. Otherwise it is the `sharedRelativeWeight`
feature. Guesses are treated like facts here; their lower weight only matters
where weights are used. If they cannot be one person, each is joined in
stage 4 to the best of the blocked alternatives.

Example: after stage 1, `vogt_zu_Lauda` has Konrad Ritter and Konrad Edelknecht
as siblings (Kreis Mosbach), distinct by rank in one passage. Freiburger 53's
"Konrad, brother of Eberhard" cannot join both; stage 4 chooses between them.

## Stage 4: best-candidate joining

Every identity takes part, whatever its number of sources, including registry
identities (two registry IDs never join each other). Guesses are treated exactly
like facts, only with their lower weight (`guessWeight`). Joining two identities
joins their families; the same-named-relatives rule then merges their
same-named fathers, brothers or spouses unless blocked, so separate trees grow
together. The current build has 258 disconnected family trees, the largest with
25 people.

### Hard blocks

Only these prevent a join, for every source type:

- distinct registry IDs;
- explicit distinctions (same relationship fact, same-passage distinctions,
  kinship-term contradiction such as a `Vetter` who is the candidate's brother);
- mention after death and incompatible death dates, when both sides are facts.
  When either side is a guess, these are penalties (`-deathConflictPenalty ×
  reliability`) like any other guessed evidence. Alternative guessed death
  dates from one passage ("died 1383, 1387 or 1388") form one interval, their
  union;
- impossible age: an empty birth interval (`maxAgeYears` `80`, adult titles and
  roles as in version 1);
- too large a time difference: living mentions of the combined identity
  spanning more than `maxLivingSpanYears` (`64`, equal to `maxAgeYears -
  adultAgeYears`); this applies to untitled spans too and to every source type,
  while the age rules remain as in stage 3;
- **known relatives**: identities are grouped into **sibling groups** (sibling
  facts plus shared parents, closed transitively; a child of one spouse and a
  child of the other share parents). Two identities may join only if every
  relationship path between them in the current tree is compatible:
  - both are in the same sibling group (the Vogt's Konrad records, even when
    one is the brother of Eberhard and another the brother of Arnold);
  - both are parents of the same sibling group or person, or both spouses of
    the same person;
  - a path through a kin-term edge (`Vetter`, `Oheim`, `Schwager`,
    `consanguineus` …) is compatible when the candidate's position from the
    named relative is allowed for that term in `data/kinship.md`, and blocks
    when it is excluded (a `Vetter` who is the relative's brother).

  Any other path blocks: father and son, grandfather and grandson, uncle and
  nephew, cousins, in-laws;
- self-relationships, ancestry cycles, broken generations, two same-named
  parents or spouses that cannot be one person.

Penalties that are not blocks in stage 3 (opposed age titles, rank regression,
same-date opposite ranks across sources, age between 60 and 80) lower the score
but do not prevent a join.

### Scoring and choice

1. Candidates are all identities with a compatible name. Each candidate gets
   the stage-3 log-odds plus stage-4 kinship evidence: position match
   (`sharedRelativeWeight × specificity`), only candidate (`1.5`), age-title
   namesake (`1`), from the second-pass plan.
2. Blocked candidates are removed.
3. The identity joins the highest-scoring remaining candidate. **No
   probability threshold applies**, but the join needs some real evidence: net
   evidence (`L - ln(prior / (1 - prior))`, penalties included) of at least
   `minJoinEvidence` (`0.5`), from at least one feature other than rank. A
   shared title, place, relative or associate is enough; the same
   name and date alone, or a shared `Ritter`, is not. Candidates without such
   evidence are shown as "possibly the same person" only.
4. Ties: if the top candidates are within `attachmentTieLogOdds` (`0.25`),
   prefer the one with shared family evidence, then the one nearest in time.
   If still tied, the identity stays separate with "possibly the same person"
   links to each tied candidate. Identity size is never a tie-break.
5. An occurrence left unresolved by a stage-1 tie (for example the untitled
   Kreis Mosbach Konrad) attaches only if its leader exceeds the runner-up by
   `attachmentTieLogOdds`; the time and family tie-breaks do not apply to it.
6. An identity with no unblocked candidate that has enough evidence stays
   separate.

### Rounds and order

- All identities are scored against the frozen state of the round; each
  proposes its best unblocked candidate.
- Proposals are accepted in descending log-odds, ties broken by sorted source
  paths and pointers. Each is checked against the blocks on the identity it
  would create, including everything already accepted in the round; a blocked
  proposal is skipped and its identity proposes again next round. The order
  depends only on scores and source keys, not on input order.
- Joins in one round support the next (a brother joined in round 1 is an
  identified relative in round 2), at their share.
- Proposals A → B and B → A count as one.
- The highest proposal of a round is checked against the frozen state only, so
  it is always accepted unless blocked there, in which case it is not
  proposed. Every round therefore makes at least one join or ends stage 4.
  Identities never split, so their number only decreases; stage 4 ends after at
  most as many rounds as there are identities.

### Confidence

Each join records its candidates, their log-odds, and a **share**:
`exp(L_i) / (1 + Σ exp(L_j))` over unblocked candidates, where the `1` is the
identity being a separate person. A lone candidate with just enough evidence
therefore gets a share of about `0.15`, not `1.0`. The share is the membership
confidence of the joined occurrences. The viewer draws joins with a share
below `0.7` as uncertain. Joins are always visible and reversible by adding a
fact or distinction.

## Achievability

Applies to stage 3 (confident merges). Anything below the threshold still
joins in stage 4 when unblocked. The build checks this table
against the configuration (prior `0.10`, link factor `1`) and fails if a "must
reach" row cannot.

| Pair | Evidence | L | Must reach 0.70 |
| --- | --- | --- | --- |
| Document ↔ document, same office 15 years apart | office `+4.0` | 1.80 | yes |
| Book fact ↔ document, same day, shared property place and rank | `+2.0 +0.375` | 0.18 | no (joins in stage 4) |
| Book fact ↔ document, same office 10 years apart, shared context place | `+2.52 +0.87` | 1.19 | yes |
| Two book identities 14 years apart, one property place and one associate | `+1.23 +0.52` | -0.45 | no (joins in stage 4) |

## Output

- `tree.json` keeps nodes, relationships, comparisons and sources as now.
  Comparisons gain `stage` (3 or 4); stage-4 comparisons also carry `share`.
- Each node lists unresolved candidates with probability
  `possibleSameDisplayProbability` (`0.5`) or more; the viewer draws them as
  "possibly the same person" instead of unrelated duplicates.
- The build reports the number of identities **per name and century**, before
  and after stage 4, to show whether common names (Eberhard, Konrad, Hans von
  Rosenberg) collapse into too few people.
- The build reports **split diagnostics**: same-name occurrences of one passage
  left in different nodes, with the reason (forced distinction, tied grouping).

## Required regression cases

Precision (from version 1, unchanged):

1. 1300 elder versus Vogt zu Dürn: the deceased elder father is not merged.
2. 1300 younger versus Vogt: the younger son stays a candidate.
3. Age titles: younger → elder compatible; elder → younger penalized;
   same-entry designations blocked.
4. Age above 80 blocked (facts) or penalized (books/guesses).
5. Death: deceased-marked later mentions compatible; unmarked mention after
   death blocked or penalized.
6. Ranks: Edelknecht → Ritter neutral; Ritter → Edelknecht penalized.
7. Family: parent/child > sibling > other kin; circular support adds `0`.
8. Controls: distance weakens support; guesses and books contribute less.
9. Stage 4: `Vetter` never attaches to a brother; the 1387 `consanguineus`
   Arnold attaches to the better of brother and son (brother); a record whose
   only candidates are blocked stays separate.
10. Input order reversal gives an identical tree.

Precision (new):

11. Freiburger entry 65 (1401): the living Konrad, Vizedom zu Heidelberg, and
    Anna Marschalk's late husband Konrad are two people.
12. A death fact next to an unmarked same-name mention without an explicit
    marker (Kreis Mosbach 38, 1387; Neumaier 27, 1354) does not split them.
13. The deceased 1300 elder Eberhard (`1300-05-17.json`) is not joined to
    `vogt_zu_Durn` in stage 4 either.
14. Known relatives never join: father and son of one name, two brothers of
    one name with different ranks in one passage, and two cousins of one name
    (`Vetter`) stay separate however high their score.

Recall (new):

15. Kreis Mosbach entry 3 (1381-05-25) yields exactly one Konrad Ritter, one
    Konrad Edelknecht, one Eberhard Ritter and one Arnold Edelknecht, plus the
    untitled Konrad unresolved.
16. Kreis Mosbach Konrad Ritter joins the documented Konrad, Ritter, Vitztum zu
    Heidelberg (`1381-05-25_4.json`) in stage 4: same-day Boxberg property and
    rank, no block.
17. Freiburger entry 53 Konrad (1381, no rank) joins one of the two Konrad
    siblings of the Vogt, never a third node. Without transaction matching the
    evidence for the Vitztum and for Konrad Edelknecht is close; the current
    data joins him to Konrad Edelknecht.
18. Bauer 1395 entry 60: the late Eberhard (father, explicit marker), Arnold der
    Junge and his brother Eberhard are exactly three people; Arnold is one node.
    The 1395 Arnold reaches `arnold_boxberg` through the shared brother; the
    1394 Arnold of the same entry (a separate
    passage) through `zu Boxberg` `≈ +2.93` and `der Junge` `≈ +1.44` (`L ≈ 2.17`).
19. "The late Konrad, Vizedom zu Amberg" (1401) gets the office feature with no
    decay against Vizedom zu Amberg attestations in 1381–1401. While the
    `1401-03-18.json` conflict below remains, the merge is blocked and
    reported.
20. `vogt_zu_Lauda` has exactly two Konrad sibling nodes: the Vitztum cluster
    (Kreis Mosbach Ritter, `1381-05-25_4.json`) and Konrad Edelknecht. Holds
    without the `1381-05-25.json` data fix. Konrad
    Edelknecht joins his best candidate:
    Freiburger 54 Konrad, Ritter, 1382–1390 (Edelknecht → Ritter is neutral)
    or the 1387 `consanguineus` Konrad (position `≈ +0.81`); the case asserts
    the sibling count and records which one wins.
    The 1387 `consanguineus` Arnold reaches `arnold_brother_of_vogt_zu_Lauda`
    through kin → sibling, and the 1401 `Vetter` Arnold through
    `Vetter` → child → sibling; both paths are allowed positions and do not
    block.
21. The achievability table holds for the shipped configuration.
22. Same-named relatives: two Konrad siblings of one identity merge unless
    blocked; a third Konrad sibling record attaches to the better of two
    blocked ones.
23. Best candidate: an identity with only weak evidence (one place) joins its
    best unblocked candidate, whether it has one source or many; a record whose only candidate died earlier
    stays separate; a record sharing only name, date or rank with its candidate
    (the tournament-book "Hans was alive" in 1271) stays separate with a
    "possibly" link; a tie within `0.25` with no family evidence stays separate
    with "possibly" links.
24. No identity with an unblocked, sufficiently evidenced candidate is left
    separate except by a tie
    (checked by the split diagnostics). The build reports the number of
    disconnected family trees before and after stage 4.
25. Share: a lone candidate with net evidence `0.5` gets share `≈ 0.15`; the untitled
    Kreis Mosbach Konrad (tied between Ritter and Edelknecht) stays separate.
26. Stage 4 gives an identical result under reversed input order.

Each case asserts the sign and magnitude of the deciding contributions, not only
the final merge.

## Configuration changes

```json
"model": "weighted-log-odds-v6",
"priorProbability": 0.1,
"sameDateRankConflictPenalty": 3.0,
"retrospectiveLookBackYears": 20.0,
"passageTitleAgreementWeight": 1.0,
"possibleSameDisplayProbability": 0.5,
"bestCandidate": {"maxLivingSpanYears": 64.0, "attachmentTieLogOdds": 0.25,
                  "minJoinEvidence": 0.5, "maxRelativePathSteps": 6}
```

`secondPass.mergeProbability` is removed: stage 4 has no threshold. The other
`secondPass` keys remain as kinship-position, elimination, age-title and widow
weights used by stage 4.

## Known data issues found while designing

- `1381-05-25.json` (purchase charter): Konrad, Ritter, and Konrad, Edelknecht,
  appear only inside the content of facts about the Vogt and Arnold. Typed
  title and purchase facts for both Konrads would add evidence; no required
  case depends on them.
- `1401-03-18.json`: Konrad der Ältere, Vizedom zu Amberg, alive after
  `1401-03-05.json` records that Konrad, Vizedom zu Amberg, died before
  1401-03-06.
- `1387-06-22.json`: one Konrad mention carries both `Ritter` and `armiger`.

## Open questions

1. Should the prior scale with name frequency (computed once from the inputs),
   so rare names start higher than Konrad or Eberhard?
2. Is `retrospectiveLookBackYears 20` right, or should it be the last attested
   living date?
3. A contemporaneous prior (`1 / (known distinct namesakes + c)`) was rejected:
   it gives poorly attested names the highest prior, changes between rounds,
   and has a cliff at the window edge. Revisit only with a stable definition.

## Implementation

Implemented in `scripts/family_graph/reconstruction.py` (stages, same-named
relatives, known-relatives block, membership confidence) and `probability.py`
(parameters, hard blocks, rank conflict, guessed death intervals). The old
second pass is replaced by stage 4; its kinship-position, widow and
speculative-parent evidence are stage-4 features. Tests:
`tests/test_probability.py` (rules) and `tests/test_family_graph.py`
(`test_real_vogt_zu_lauda_family_has_no_duplicate_konrad_or_arnold`).
`rebuild_family_tree.py` prints the family-tree count, the most common names
per century, and passages whose same-name occurrences stay in several
identities. Nodes carry `possiblySame` for undecided candidates.

Result on current data: 677 → 488 identities, 258 → 146 family trees (largest
25 → 70); Eberhard von Rosenberg 65 → 26 nodes.

In pass 0, an occurrence that fits more than one group of its section stays for
the later stages, and groups that conflict with each other are both left
unmerged, so pass 0 never chooses between alternatives.
