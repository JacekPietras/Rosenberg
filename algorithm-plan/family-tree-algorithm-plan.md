# Family reconstruction specification

This document defines the required matching behavior, known implementation
gaps, and next implementation steps. Requirements describe the target behavior;
the current engine does not yet satisfy the chronology rules below.

## Weight calculation convention

Weights are additive **log-odds contributions**, not percentage points:

```text
L = ln(prior / (1 - prior)) + sum(eligible evidence contributions)
P = 1 / (1 + exp(-L))
reliability(assertion) = source factor × (guess factor if guessed, else 1)
pair reliability = min(reliability(left), reliability(right))
positive contribution = base weight × pair reliability × temporal decay
```

Use each underlying signal once, applying category caps and dependency confidence
before summing. The prior is applied once per comparison, not once per assertion.
Hard constraints govern merge eligibility separately; an ineligible merge must
be reported as a conflict, not displayed as a calculated 0% probability.
Storage, display, and verification rules add no weight.

[Worked calculations](weight-calculation-examples.md) illustrate the arithmetic
and distinguish existing parameter values from proposed temporal behavior.

## Evidence and output

- Compare all source people, including those without registry IDs. A matching
  name retrieves candidates; it does not establish identity.
- Keep exact registry IDs fixed and distinct. ID wording supplies no evidence.
- Read facts and lower-weight guesses under `data/`, preserving source locations,
  historical dates, participant roles, titles, and deceased status. Follow
  `rules/facts.md` and `rules/json-formats.md`; never use publication dates as
  activity dates or rewrite source facts to confirm an inferred identity.
- Always include guesses in the normal result; retain a facts-only audit view.
  Guess dependencies and uncertainty survive every subsequent merge.
- Keep `people.json` as the confirmed ID/name registry. Store generated identities,
  relationships, alternatives, calculations, and parameters in `tree.json`.
- One card per reconstructed identity. Rebuild when evidence, code, or parameters
  change. More connections do not by themselves establish better reconstruction.

Weight effect: facts in documents/images have reliability `1.0`; facts in
books/notes `0.5`. Guesses multiply that factor by `0.45`, giving `0.45` and
`0.225` respectively. Exact IDs are assignments, not positive scoring features;
distinct fixed IDs prohibit merging. Matching names add `0` beyond candidate
retrieval and the configured prior. Registry storage, graph size, and number of
cards add `0`.

## Chronology comes before positive matching

Preserve ISO precision. Internally interpret partial dates as intervals and
`diedBefore` as an exclusive bound. Keep three different kinds of evidence:

| Evidence | Meaning |
| --- | --- |
| Exact death, death interval, deceased designation | Constrains when death occurred; an attestation of deceased status supplies an upper bound, not an exact death date. |
| Dated living activity | Explicit participation requiring life at the historical event date, such as personal issuance, witnessing, or sealing. |
| Ordinary or retrospective reference | Does not establish life at the document date. |

A death fact or `personDeceased`/`ofDeceased` marker alone must never set the
identity-match probability to zero or trigger a death penalty. The marker says
the person was already dead when referenced; it does not say they died on that
date. A deceased participant remains eligible for matching to earlier living
attestations and later deceased or retrospective references. Apply negative
death evidence only to incompatible chronology, not to the presence of death
information. Compatible death evidence is neutral or corroborating.

For example, death in 1330 and a deceased designation in 1357 are compatible.
Deceased by 1300 and deceased by 1357 are also compatible upper bounds: the
second does not imply survival until 1357. Neither case warrants a zero match
probability. An unmarked mention in 1357 does not establish survival either.

Living activity must be supported by the source and attached to the correct
participant. A sale mentioned retrospectively uses its event date, when known,
not the date of the later reference. Property formerly held, a widow naming her
husband, and inherited rights do not establish continued life. An unmarked title
or relationship fact alone is not evidence of life. If a role is ambiguous,
retain that uncertainty; do not silently classify it as active or posthumous.

For each proposed complete identity cluster:

1. Intersect all factual death constraints with factual living-activity dates.
   Reject the merge if no chronology remains possible. For uncertain intervals,
   reject only if every allowed date combination conflicts.
2. A factual death upper bound followed by factual personal activity is a hard
   conflict only when the later activity is independently established for that
   candidate, not inferred from a same-name mention or absence of a deceased
   marker. Rejecting such a contradictory merge is distinct from zeroing the
   probability merely because a participant is deceased.
   Matching names, places, titles, relatives, or many intermediate
   records cannot compensate for it. Fixed IDs with conflicting evidence produce
   a reported data conflict, not an automatic reassignment.
3. Conflicting guesses supply strong negative evidence with their lower weight;
   they cannot override a factual contradiction or erase factual evidence.
4. Later posthumous references remain compatible with earlier death. Multiple
   compatible death upper bounds do not prove that later records are posthumous.

Represent reviewed living-activity evidence internally with event dates, source
pointers, and participant bindings. This is required for chronology enforcement,
not a deferred enhancement. Do not invent source JSON fields or infer activity
with an unrestricted prose keyword rule. Missing structured evidence must be
reported and reviewed under the repository rules before any schema/data change.

Weight effect: compatible death bounds and deceased markers contribute `0` by
default, including a missing deceased marker. Mere compatibility earns no bonus.
A separate corroborating death feature would require its own configured rule
and independent evidence; it must not count the same death twice. A conflict
involving uncertain/guessed evidence contributes a negative weight, scaled by
the weaker reliability (`-deathConflictPenalty × pair reliability` for a fully
incompatible guessed chronology). Partial ambiguity must not receive a full
conflict penalty. Proven factual impossibility blocks merging outside the
weighted sum; generic positive signals cannot cancel that constraint.

## Time distance and age designations

Time distance is graded evidence, separate from logical impossibility. Do not
infer numerical ages, birth years, or a maximum lifespan from titles.

- Holding other evidence constant, a greater gap between comparable historical
  attestations must weaken identity support progressively. A 57-year activity
  span needs more distinguishing evidence than a short span; it is not by itself
  impossible.
- Compare the complete dated history of both candidate clusters, not only their
  closest pair of records. Intermediate matches must not reset the clock or
  remove a penalty for the combined span. Count active events separately from
  later references: a 1357 retrospective reference does not extend an activity
  span to 1357.
- Every title category decays with the distance between its own attestations:
  age epithets, rank, office, territory, and called/born designations. Do not
  treat accumulated titles as timeless properties. Scoped offices carry more
  support than generic ranks at comparable distance, but can have successive
  holders.
- `der Jüngere` and `der Ältere` are relative, dated designations. Preserve
  `der Junge` and `der Alte` separately. Matching age designations close in time
  can support identity; their support weakens over decades.
- Earlier younger → later elder is an allowed progression. Do not apply a
  symmetric “opposed age titles” penalty to that sequence. The reverse sequence
  warrants caution but is not automatically impossible without an explicit
  source distinction. Missing designations are neutral.
- When comparing the elder parent and younger child in the same early source
  with a person active much later, evaluate both candidates. Other evidence
  being comparable, the later activity favors the younger generation. This is
  relative ranking evidence, not a numerical age estimate or proof of identity.
  If death/activity already excludes the elder, that exclusion decides the
  comparison regardless of the age-title score.
- A relative's late activity or title must not be transferred onto the person.
  Keep uncertainty about the identity of later attestations visible.

Use interval-aware distances; broad or missing dates must not receive the same
precision or near-date bonus as two exact nearby dates. Missing historical dates
supply no temporal support. Explain the intervals and distance convention used.

Weight effect: title support uses `base × reliability × 2^(-gap / halfLife)`.
Missing titles or dates contribute `0`; younger → elder contributes `0` as a
title mismatch, not the negative `opposedAgePenalty`. An explicit contemporary
source distinction is a merge constraint, not a title-decay calculation.
Any reverse-progression penalty must be a separately explained, configurable
negative contribution rather than an automatic exclusion.

For the revised temporal model, use the complete **active-event span** `S` of
the proposed cluster in years, not the nearest pair, for the temporal penalty:

```text
time contribution = -S / timeDistanceScaleYears
                  - max(0, S - clusterSpanStartYears) / clusterSpanScaleYears
```

Apply this once per proposed cluster comparison, never add earlier pair or
cluster penalties again. With current scales `35`, `60`, and `20`, a 57-year
span contributes `-57/35 = -1.629`. Intermediate records cannot reduce it.
Posthumous references do not enlarge `S`; if fewer than two independently dated
active events exist, this feature is `0`, not evidence of a short life.
Title/context decay still uses the relevant historical attestations' own dates.
For date intervals, report the possible span/contribution range; uncertainty
must not earn an exact-date bonus or be collapsed to the most favorable date.

In an otherwise comparable early parent/child choice, later verified activity
can add `generationPreferenceWeight × reliability × dependency confidence` to
the younger candidate, with `0` for the elder. Apply it only with an explicit
generational distinction and verified later activity, never from name or title
alone. This new parameter requires review/configuration before implementation;
it is not an inferred birth date, and must not duplicate another feature encoding
the same generational evidence. Hard death/activity conflicts still take priority.

## Other matching evidence

Combine dated evidence rather than using a single title or place as an identity
key. Use places/property, scoped offices, ranks and designations, same-fact
associates, and explicit family relationships. Resolve place variants using
`places.json`; distinguish property, residence, issuance, and title scope where
supported. A surname place is not independent geographical support.

Associates are deterministically recognized within one fact, not across an
entire entry. Co-occurrence never creates kinship. Seal comparison remains human
work; do not introduce automatic visual identity matching.

Full relative names can supply limited context. Independently identified
relatives are stronger evidence than common unresolved names. A relative's title
belongs to that relative. Do not bootstrap certainty by matching parents through
children and then reusing those inferred parents to confirm the children.
Repeated feature extraction, copies of an assertion, or iterative propagation
must not manufacture independent corroboration or change fixed source factors.

Weight effect: use the configured place-role base (`property 4`, `context 2.5`,
`issuance 2`), title-category base (`office 8`, `rank 0.75`, `age 3`), or associate
base (`2`), each scaled by reliability and its temporal decay. Cross-role place
matches additionally multiply by `crossRolePlaceFactor` (`0.5`). These are current
configuration values, not historical likelihood ratios established by research.
An office's place cannot earn a second independent place bonus for the same
observation. Surname-only geography and unsupported associations contribute `0`.

Family support uses the appropriate configured base: independently anchored
relative `9`, provisionally linked relative `7.5`, unresolved full relative name
`4`. Scale by reliability, time decay, and the confidence of any inferred link.
Use only the strongest applicable category per relative, cap total family
support (`16` currently), and cap any relative-name rarity adjustment separately.
Circular support and repeated extraction add `0`; human seal review adds no
automatic numerical contribution. Caps limit contributions, not source factors.

## Decisions and explanations

Use one global configuration in `data/matching.json`, visible in the viewer and
recorded with each build. Retain agreed defaults: documents/images `1.0`,
books/notes `0.5`, additional guess factor `0.45`, compatible-name prior `0.05`,
and merge threshold `0.85`. Source factors scale evidence, not final probability.
Other feature weights, decay settings, span penalties, and candidate margins
must be explicit and configurable. Hard factual conflicts are not adjustable
penalties. Estimates remain **uncalibrated** until evaluated against reviewed
identity decisions; a high percentage is not historical confirmation.

Apply chronology and explicit-distinction checks before scoring, and repeat
them on every proposed complete cluster, including source-local grouping and
transitive merges. No chain may merge distinct anchors, violate participant
distinctions, create self-relationships, or create ancestry cycles. Evaluate
competing candidates together; retain an unresolved alternative when evidence
or the winning margin is insufficient. Results must not depend on input order.

Explain every substantive decision with source pointers, dates/intervals,
activity versus reference roles, positive and negative contributions, complete
cluster span, competing candidates, and rejection reasons. Uncertain endpoint
identities remain uncertain even when the relationship assertion is factual.
Generate only source-stated relationships; do not infer another parent from
marriage or kinship from business association.

Weight effect: `prior=0.05` gives initial log odds `-2.944`; `P=0.85` requires
final log odds about `1.735`. Therefore roughly `4.679` net positive evidence is
needed from that baseline. Crossing the threshold is necessary but insufficient:
the current rival margin is `1.0` log-odds unit and cluster constraints must also
pass. Candidate probabilities are pairwise estimates, not normalized shares
that must sum to one. Explanations, output formatting, and component counts do
not change any contribution.

## Required regression cases

1. **1300 elder versus Vogt zu Dürn:** `1300-05-17.json` identifies the elder
   father as already deceased. Later verified personal activity of the Vogt
   (for example the 1328 sale/sealing) excludes that father from his identity.
   The source parent assertion remains valid and its unresolved name unchanged.
2. **1300 younger versus later activity:** compare the younger son as a separate
   candidate. If activity through 1357 is established for the Vogt, account for
   the full 57-year span. It favors the younger over the elder on generational
   chronology, but does not alone identify the younger as the Vogt. The 1357
   entries contain an issuer and a deceased namesake; their identities must be
   established separately, not assumed from the date or shared name.
3. **Progression:** younger in an early source and elder decades later is
   compatible. Same-time explicit elder/younger distinctions keep people apart.
4. **Bridge:** a chain of nearby attestations cannot hide a long combined span
   or join a deceased person to later living activity.
5. **Posthumous reference:** a widow's later reference to a deceased husband
   remains compatible. A later reference without active participation must not
   extend his activity span. An exact death followed by a later deceased marker,
   and two compatible deceased upper bounds decades apart, must remain eligible
   matches with no death-conflict penalty. Exercise both `personDeceased` and
   `ofDeceased`; absence of either marker is not proof of life.
6. **Intervals and uncertainty:** overlapping partial dates remain possible;
   factual impossibility excludes; guessed conflict lowers support. Missing or
   broad dates must not generate false temporal precision.
7. **Controls:** unchanged evidence at greater time distance gives less support;
   guesses contribute less than facts; circular family support cannot inflate
   confidence; rivals, distinct IDs, and source distinctions remain inspectable.

Validate deterministic output, provenance, unchanged source/registry files, and
one card per identity. Passing software tests or reducing fragmentation does
not establish historical accuracy.

Weight effect to verify: each regression must assert the sign and magnitude
(or configured formula) of the relevant contribution, not only the final merge.
Compatible deceased markers add `0`; greater active span increases the penalty;
longer title gaps reduce support; younger → elder has no mismatch penalty;
guesses scale evidence down; duplicate/circular evidence adds `0`. Impossible
factual chronology must fail eligibility even with a high raw score.

## Current implementation and known gaps

The current engine reads source facts and guesses, anchors exact registry IDs,
and compares source identities with an uncalibrated log-odds model. Global
parameters live in `data/matching.json`; generated calculations and audit views
live in `data/tree.json`. Source assertions and `people.json` are not rewritten.
The viewer displays evidence, alternatives, and one card per identity.

The 1300 Eberhard case exposes a serious chronology gap:

- `dates.py` compares death intervals against one another, without a complete
  death-versus-living-activity check.
- Ordinary mentions do not prove life, but that safeguard must not prevent
  source-supported active participation from excluding an already dead person.
- The current symmetric opposed-age-title feature does not adequately represent
  younger → elder progression.
- Pairwise proximity and contextual matches can support a cluster whose full
  chronology needs much stronger scrutiny. A combined-span penalty exists;
  its presence alone does not establish adequate temporal behavior.

Consequently, generated percentages and merges, including the 1300 deceased
elder assigned to `vogt_zu_Durn`, require review. Passing existing checks does
not establish compliance with the revised chronology requirements.

Read-only inspection:

```sh
python3 scripts/rebuild_family_tree.py
python3 scripts/rebuild_family_tree.py --include-guesses --explain vogt_zu_Durn
```

`--apply` writes a rebuilt tree. Rebuilding with the unchanged matcher does not
fix the chronology flaw.

Weight effect: these gaps mean current computed weights are not yet compliant
with the revised spec. In particular, nearest-pair timing can under-penalize a
long cluster span, and a symmetric age penalty can unfairly lower a plausible
younger → elder match. The new generation preference is not in the current
configuration. Do not describe the worked target calculations as current engine
output or silently change global parameters while documenting them.

## Implementation steps

These changes are pending:

1. **Evidence model:** distinguish dated living activity, deceased status/death
   intervals, and ordinary/posthumous references. Bind each observation to the
   correct participant and historical event. Preserve uncertainty and source
   pointers; review any required source-schema extension separately.
2. **Constraints:** extend `scripts/family_graph/dates.py` and all grouping/merge
   paths to check death against living activity across complete clusters. Apply
   factual conflicts as exclusions, guessed conflicts as weighted evidence, and
   report contradictory anchored evidence.
3. **Temporal scoring:** use complete activity spans as well as pair distances.
   Keep later references separate from activity. Prevent bridging records from
   concealing long spans. Specify interval/missing-date behavior and expose
   effective temporal settings in the global configuration.
4. **Age designations:** replace symmetric opposed-title handling with dated,
   directional comparison. Allow younger → elder; compare early parent/child
   candidates against later activity without inferring numerical ages.
5. **Evidence propagation:** retain dependencies and evaluate rivals jointly.
   Common relative names and already inferred family links must not become
   independent proof. Repeat constraints after every proposed merge.
6. **Export and viewer:** explain activity/reference classifications, full spans,
   hard conflicts, temporal contributions, and unresolved alternatives. Version
   changed semantics so stale trees rebuild.
7. **Validation:** add the regression cases above; review the
   1300/Vogt assignments before and after rebuilding. Preserve the parent fact,
   sources, and registry. Run appropriate Python and viewer checks, inspect the
   generated diff, and report unresolved evidence rather than forcing a merge.

Do not lower merge thresholds or add person-specific exceptions to obtain the
expected result.

Weight effect: implement and test eligibility before changing scoring. Then
replace temporal/age contributions using the formulas above; add any reviewed
new parameters to the one global configuration. Preserve agreed source factors,
prior, and merge threshold. Export each effective contribution and its evidence
so example arithmetic can be reproduced. Verification and rebuilding add no
confidence by themselves.
