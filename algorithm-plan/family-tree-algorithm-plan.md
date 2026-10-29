# Plan: rebuild the family tree from facts and optional guesses

## Objective

Build an evidence graph with identity resolution, then generate the family tree
from that graph. Resolving which person a fact describes comes before creating
relationships between registry records.

Ignore all existing relationships in `data/people.json` during reconstruction.
Keep existing IDs as distinct identity anchors, and reconstruct relationships
entirely from source facts and, optionally, guesses. This document is a plan;
schema extensions described below are proposals, not currently permitted fields.

## 1. Read and normalize evidence

Recursively collect `facts` and, when enabled, `guesses` from books, documents,
notes, images, and nested records under `data/`.

For each assertion, retain an internal record containing:

- Source file, JSON location, citation, and original assertion.
- Whether the assertion belongs to `facts` or `guesses`.
- Historical date or date interval, following the existing inheritance rules.
- Participant references, titles, and deceased status.
- Relationship, title, or death information.

Follow `rules/json-formats.md` and `rules/facts.md`. In particular, book and note
typed assertions require explicit historical dates; publication dates must not
be inherited. Preserve the source precision and existing document intervals.

Use typed assertions directly. Legacy prose remains searchable supporting
material; extracting new formal assertions from prose is a separate review step.

Normalize names using `data/names.md` and places using the existing place
resolver. Preserve meaningful distinctions such as `Kunz` versus `Konrad` and
`Münch von Rosenberg` versus `von Rosenberg`.

Do not collapse matching names into people at this stage. Every unresolved
occurrence starts as a separate mention.

## 2. Establish identity anchors

Resolve an exact, case-sensitive existing person ID first:

```text
person: "vogt_zu_Lauda"
    -> fixed reference to that existing person

person: "Eberhard von Rosenberg"
    -> unresolved mention with several possible identities
```

Treat different existing IDs as distinct people. No chain of uncertain matches
may merge `vogt_zu_Lauda` and `vogt_zu_Durn`.

Existing names and titles can help retrieve candidates, but registry titles and
dates must not become authoritative evidence without source support. Existing
spouses and children must not participate in matching.

Never derive genealogical evidence from an ID's wording: an ID containing
`son_of` is just an identifier.

Use internal handles for registry records without IDs. A shared name is not a
unique identifier, and IDs must not be invented solely to complete the graph.

## 3. Apply different rules to different titles

Use a configurable title policy:

| Category | Examples | Matching behavior |
| --- | --- | --- |
| Reviewed identity discriminator | `Vogt zu Lauda` for the relevant Eberhard | Can identify an anchor within an explicitly established scope |
| Relative age designation | `der Jüngere`, `der Junge`, `der Ältere`, `der Alte` | Dated contextual evidence; may change or disappear |
| Rank or status | `Ritter`, `Edelknecht`, `miles`, `armiger` | Supporting evidence; allows change and omission |
| Territorial association | `zu Boxberg`, `zu Jagstberg` | Dated supporting evidence, with stronger rules only where established |

For identifying designations, encode the actual reviewed rule:

```text
Within this name/context/date scope:
    "Vogt zu Lauda" identifies vogt_zu_Lauda.
```

This supports designations that can always identify a person within the relevant
context without assuming that an office could never have another holder.

For age designations:

- Preserve the source's exact distinction.
- Matching epithets close in time support identity.
- Opposed epithets explicitly distinguishing people in the same passage support
  separation.
- A later change from younger to elder is possible.
- Missing epithets supply no negative evidence.

Rank changes normally affect the score rather than reject a candidate. A first
`Ritter` attestation does not establish the date of knighting.

## 4. Build chronological constraints

Represent partial dates internally as intervals while preserving their original
precision. Maintain separate constraints for:

- Death during a stated day, month, or year.
- Death before an exclusive bound.
- Deceased status at an attestation.
- Explicit evidence of living activity.
- Mere mentions, including retrospective mentions.

Death excludes a match only when the new assertion requires the person to have
been alive afterward. A widow's 1393 mention of her husband is compatible with
his death in 1387; `data/documents/1393-06-23_2.json` illustrates this distinction.

An unmarked relationship or title mention does not prove life. Until living
activity is formally represented, chronological exclusions must be conservative.

Follow the existing exclusive-bound semantics for `diedBefore`. For example,
`1394` means before 1 January 1394. Do not substitute an attestation date for a
death date.

When date intervals overlap, reject only if no compatible chronology remains.
Estimated deaths from `guesses` remain defeasible constraints. Conflicting
source-supported bounds must be reported rather than silently reconciled.

## 5. Generate and score identity candidates

For each unresolved mention, consider compatible registry identities and
compatible unresolved mention groups. Always retain an unresolved or possibly
another person alternative.

Apply hard exclusions first, then score the remaining candidates:

| Evidence | Suggested role |
| --- | --- |
| Explicit ID | Fixed assignment |
| Reviewed identifying designation | Strong identification within its scope |
| Distinctive, independently resolved relatives | Strong support |
| Compatible office chronology | Strong or moderate support |
| Repeated property or transaction continuity | Moderate support |
| Specific associates or seal evidence | Supporting evidence |
| Time-sensitive title agreement | Supporting evidence |
| Place overlap | Supporting evidence |
| Same name alone | Candidate retrieval only |

Initially call the result a matching score, not a probability. Percentages become
meaningful only after calibration against reviewed identity decisions.

Require sufficient evidence and a clear margin over alternatives before
accepting an inferred assignment. Otherwise preserve competing candidates.
Inferred assignments must retain their uncertainty and must not rewrite source
facts into claims of certain identity.

## 6. Use places without contaminating evidence

Reuse the place matching behavior behind
`scripts/search_places_by_name.py --count`, with one restriction: build an
anchor's initial place profile only from explicitly identified mentions,
equivalent to `--direct`.

Otherwise every Eberhard could inherit places from all unresolved Eberhards,
making the matching circular.

Improve the basic counts by:

- Counting independent historical events rather than repeated quotations.
- Giving distinctive places more weight than common places.
- Comparing places within relevant time periods.
- Separating personal activity, property location, document issuance, and title
  scope.
- Distinguishing a surname's place from evidence of actual presence.
- Leaving ambiguous place names unresolved.

Geographical distance is usually a weak signal. Property ownership does not
establish physical presence. Place evidence used in a title rule must not be
counted again as independent corroboration.

## 7. Resolve connected evidence together

Avoid a greedy algorithm that permanently merges the highest-scoring pair first.
Solve connected groups of ambiguous mentions together using candidate
assignments and constraints. A bounded search over the best alternatives is a
reasonable starting implementation.

Check each proposed solution for:

- Merging distinct anchors.
- Self-parentage or ancestry cycles.
- Impossible chronological combinations.
- Violating explicit source distinctions.
- Contradictory assignments within a source passage.

Use family relationships to support identity only when their other endpoints are
independently grounded. An inferred identity must not create a relationship that
then serves as independent proof of that same identity.

Conflicting anchored evidence produces a conflict requiring review rather than
silently overriding an ID. Preserve alternative solutions when evidence does
not distinguish them.

## 8. Generate relationships with uncertainty preserved

After resolving identities, convert assertions into graph edges:

- `parent`: directed parent to child.
- `spouse`: symmetric relationship.
- `sibling`: symmetric relationship.
- `kin`: symmetric connection retaining the source term.

Do not infer a second parent from marriage, parents from siblings, sibling
transitivity, or a precise relationship from `Vetter`. Relationship attestation
dates do not establish relationship start dates.

Each edge retains its supporting source locations and distinguishes:

1. Whether the relationship assertion is a fact or guess.
2. Whether either endpoint required uncertain identity matching.

A source-supported parent assertion with an uncertain Eberhard endpoint remains
an uncertain graph edge. Deduplicate equivalent edges while retaining all
supporting assertions and their dependencies.

## 9. Make guesses an optional overlay

Use one matching engine with two evidence policies:

```text
Facts-only:
    facts supply assertions and identity evidence

Include-guesses:
    facts + guesses supply assertions and identity evidence
    guess-dependent conclusions remain marked
```

Guesses must not override fixed identities or make conflicting factual evidence
disappear. If a guessed death excludes a candidate, or a guessed relationship
identifies a participant, every dependent conclusion retains that dependency.

Disabling guesses must reproduce the facts-only result deterministically.
Uncertain source identity and guessed relationship content remain separately
visible.

## 10. Rebuild people.json after validating the result

Compute the complete replacement in memory before changing the file:

1. Remove old relationship fields from the output records.
2. Populate only relationships supported by the selected evidence policy.
3. Validate references, uncertainty handling, and graph consistency.
4. Review the resulting diff.

Keep old relationships available only for a before/after comparison, never as
input evidence. Preserve existing IDs, names, unrelated fields, and source data.

The current `wife` and `children` fields cannot represent the complete result.
Propose a documented relationship array supporting multiple spouses, siblings,
kin terms, evidence references, and uncertainty. Update the schema and viewer
before exporting this new structure; do not silently introduce unsupported
fields or discard relationships that the old structure cannot represent.

Unresolved mentions remain visible in the evidence graph using internal handles.
Do not force them into existing people or invent permanent IDs merely to make
the export complete. Ambiguous name-only references must never select the first
matching registry record.

## 11. Data improvements with the greatest value

These require explicit schema extensions. Current typed fact formats reject
additional fields.

- **Living activity assertions:** formally identify someone acting at a
  historical date, distinct from merely being mentioned.
- **Reviewed identity constraints:** record that two mentions are the same person
  or different people, with evidence and scope.
- **Stable source-entry identifiers:** preserve evidence references when arrays
  are reordered.
- **Shared historical event identifiers:** connect a charter, its printed
  edition, and later quotations so they do not count as independent
  corroboration.
- **Structured person-place roles:** distinguish residence, property, office
  scope, issuance, and burial.
- **Structured transactions and associates:** expose continuity currently buried
  in prose.
- **Seal observations:** distinguish family arms from evidence identifying an
  individual seal.
- **Temporal scope for designations:** distinguish attestation on one date from
  evidence of holding an office throughout a period.

Existing undated title lists in `data/people.json` remain summaries, not
substitutes for dated source attestations. Keep source assertions alongside
their source text and citations; do not create a separate facts database.

## 12. Implementation order

1. **Evidence reader and graph:** typed facts, dates, provenance, explicit IDs,
   and unresolved mentions.
2. **Conservative matching:** reviewed title rules, chronology, direct-ID place
   profiles, and explainable scores.
3. **Joint resolution and guesses:** alternative assignments, conflict handling,
   and dependency tracking.
4. **Export and viewer:** revised relationship schema, relationship replacement,
   and uncertainty display.

The first deliverable is a read-only prototype explaining candidate matches and
proposed relationships. Once the decisions are inspectable and reliable, the
same engine performs the relationship rebuild.

## 13. Acceptance checks

- An unresolved Eberhard can match Lauda while Lauda and Dürn remain distinct.
- A younger designation can disappear or later become elder.
- `Edelknecht` followed by `Ritter` remains compatible.
- Posthumous mentions remain compatible with death.
- Explicit living activity after a firm death bound is rejected.
- Partial dates, intervals, and exclusive death bounds preserve their semantics.
- Repeated editions do not inflate confidence.
- Ambiguity remains unresolved when evidence cannot distinguish candidates.
- Disabling guesses removes every guess-dependent conclusion.
- Changing old `people.json` relationships does not change the generated result.
- Inferred relationships cannot provide circular identity corroboration.
- Distinct people with the same name cannot be conflated by export or rendering.
- Conflicting assertions remain traceable to their sources.
- Repeated runs with the same inputs and policy produce the same result.
