# Probability matching: current user requirements

This document records the user's latest requirements for family reconstruction.
It takes precedence over earlier proposals about optional guesses, registry-only
matching, or writing generated relationships into `people.json`.

**Status:** requirements and implementation gaps, not a claim that the requested
probability model is already implemented. The current implementation is described
in [family-tree-final-implementation.md](family-tree-final-implementation.md).

## Intended result

The user considers the large number of small, disconnected family graphs
unsatisfactory. Reconstruction must actively compare source records and infer
when they describe the same person, including people without a confirmed
registry ID. It must combine several kinds of evidence into an estimated
probability of identity and use sufficiently supported matches to connect the
graphs. Checking existing IDs and joining only obvious family pairs is
insufficient.

The objective is better identity reconstruction, not an arbitrary reduction in
the number of components. Unsupported namesake merges would make a larger
graph less accurate.

## Evidence the user explicitly requested

| Signal | Required matching behavior |
| --- | --- |
| Relation to places, including property | Recognize place names and variations from `data/places.json`. Include property continuity in this place-association probability, rather than as a separate matching system. Distinguish issuance location, territorial titles, residence, property, and other roles where supported. Weight ambiguous or indirect associations less strongly. A surname's place must not be counted again as independent evidence of property or residence. |
| Age-related titles | Use `der Junge`, `der Jüngere`, `der Alte`, and `der Ältere` as dated evidence whose matching contribution weakens with time distance. Matching designations close in time support a match; explicit contemporary distinctions support separation. Allow a younger person to become the elder later. An omitted title is neutral. |
| Other titles and scoped offices | All titles weaken with time distance. Scoped offices such as `Vogt zu Lauda` or `Vogt zu Dürn` carry much stronger identity evidence than generic ranks such as `Ritter` or `Edelknecht`, but their contribution still decays with time. |
| “Called” and “born” designations | Treat source-stated “called …” and “born …” designations as titles with configurable weights. Preserve their meaning in the title; do not introduce a separate alias or birth-name matching subsystem. |
| Death evidence | Conflicting death evidence must reduce the identity probability drastically, or exclude a logically incompatible identity. It must not be a small penalty easily offset by matching generic titles or places. Preserve partial-date precision. A later ordinary mention may be posthumous and must not automatically contradict an earlier death. |
| Family relationships and additional titles | Follow explicit relatives, spouses, parents, and children to compare family context and find further dated titles attached to the candidate person in other assertions. This must work beyond existing registry IDs. A relative's title must not be transferred to the person being matched. |
| Document dates and time distance | Use historical document/assertion dates and intervals. Greater time distance should progressively weaken an otherwise comparable identity hypothesis, rather than merely passing or failing a fixed time window. Publication dates are not historical activity dates. |
| Associates in the same fact | Deterministically recognize personal names of the form `XXX von YYY` appearing in the same individual fact. Repeated overlap among these names can support identity, with a configurable weight. Co-occurrence is association evidence, not a family relationship. |
| Explicit distinctions in formal assertions | Use existing formal facts and guesses to identify participants who must be distinct, including a source-stated parent, child, spouse, or other explicit relationship between two people. Preserve guess reliability when weighing uncertain distinctions. |

Names retrieve candidates; the model must then combine these signals. A matching
name, generic rank, or location alone does not identify someone. Missing
information must be distinguished from contradictory information.

### Title strength and time decay

Time decay applies to **every title category**, including age epithets, ranks,
territorial designations, scoped offices, and “called”/“born” designations. Matching titles decades apart
must contribute less than comparable title attestations close together. An
office designation must not become a timeless identity key: different people
can hold the same office at different times.

Conceptually, the contribution must account for:

```text
title contribution = category strength × temporal decay × source reliability
```

This describes the required factors, not a finalized probability formula.
Scoped offices have much higher category strength than generic ranks. Effective
strengths and decay parameters must be part of the global configuration and
visible in the viewer. Use the dates of the title attestations themselves,
including titles found through family-linked assertions; do not treat all
titles accumulated in a person's profile as equally current.

### Associates, age information, and seals

Associate extraction must operate within a single fact, using deterministic
recognition of `XXX von YYY` personal names. The entire document or an entry's
complete `facts` array must not be treated as one co-occurrence group. Formal
participant fields can supply names directly; textual facts can supply named
co-occurrences without inventing a new typed relationship. Preserve the original
fact reference and apply the existing name normalization rules.

Do not introduce estimated ages, life-stage models, or inferred birth ranges.
The dataset does not provide enough age information for that proposed signal.
Use historical time distance between documents/assertions instead. Age epithets
remain weighted titles, not numerical age estimates.

Seal comparison is human work. Do not implement automatic image comparison or
automatic identity matching from visual similarity of seals or arms.

### Death as strong negative evidence

A proposed identity with conflicting death chronology must receive a drastic
probability reduction. Mutually exclusive, reliable death dates can require
rejection rather than merely a lower score. The model must distinguish a
precise death date, a death interval, a `diedBefore` bound, and a designation as
already deceased. Guessed death evidence has lower reliability but still
contributes a negative signal when it conflicts.

Compatible records should not be penalized merely because one records a death.
Later references to a deceased person remain possible; an ordinary document
mention alone does not establish that the person was alive on that date.

Unsupported prose interpretation must not silently become a source fact. Where
needed evidence exists only in prose, identify the missing structured evidence
and follow the repository's source-review and schema rules before adding it.

## Guesses are always included, with lower weight

The normal generated tree must always take `facts` and `guesses` into account.
Guesses are not an optional on/off enhancement to the normal reconstruction.
They must contribute less confidence than comparable factual evidence.

The model must distinguish:

- Confidence in the source assertion itself.
- Estimated probability that two participant records identify the same person.
- Confidence in a relationship after considering both its assertion and its
  endpoint identity matches.

Guess dependence must propagate through later identity matches and relationship
derivations. A guessed link must not become factual support merely because it
was accepted in an earlier iteration. Repeated copies of a guess must not
outweigh an explicit factual distinction.

A facts-only result may remain useful for internal validation or comparison;
it does not satisfy the requirement for the normal displayed tree.

## Agreed source weights

Apply the following source factor to every assertion from the corresponding
source category:

| Source directory | Source factor | Requirement |
| --- | --- | --- |
| `data/documents/` | `1.0` | Full source weight; never automatically lower this source factor. |
| `data/images/` | `1.0` | Full source weight; never automatically lower this source factor. |
| `data/books/` | `0.5` | Every fact contributes 50% less evidence than comparable document/image evidence. |
| `data/notes/` | `0.5` | Every fact contributes 50% less evidence than comparable document/image evidence. |

This source factor is separate from whether an assertion is a fact or a guess.
Guesses are always included and receive an additional, lower reliability
factor. A guessed assertion in a book or note therefore receives both the
`0.5` source factor and the guess factor. Title/time decay also remains a
separate contribution; it does not change the source category's fixed factor.

The factor scales an assertion's evidence contribution; `0.5` does not mean
halving the final probability that two records describe the same person.
Do not add automatic document/image source discounts based on perceived source
independence, copying, or catalogue status. Reusing the same assertion during
feature extraction or iterative propagation must not create fresh evidence.

## Probability estimates and global parameters

For every substantive candidate comparison, estimate:

```text
P(same person | names, places, dated titles, death evidence,
                family context, historical dates, source reliability)
```

Do not relabel the current arbitrary matching score as a calibrated probability.
An initial model may use explicitly documented assumptions, but its output must
be labelled an **estimated, uncalibrated probability** until evaluated against
reviewed identity decisions. Correlated signals extracted from one assertion
and the algorithm's own propagated conclusions must not be counted as fresh,
independent evidence. Apply the fixed source-category weights specified above.

The probability parameters must have one authoritative global configuration and
be visibly available in the viewer, rather than hidden in separate code paths.
The configuration must define, as applicable:

- Prior probability or baseline assumptions for retrieved candidates.
- Fact and guess reliability weights, with guesses weighted lower.
- Source-category factors: documents/images `1.0`, books/notes `0.5`.
- Place/property, age-title, rank, office, “called”/“born” title, associate, and
  family-context contributions.
- Time-distance decay for document context and every title category, including
  scoped offices, with treatment of uncertain date intervals.
- Drastic death-conflict penalties, source reliability, and logical exclusions.
- Merge threshold and required separation from competing candidates.
- Limits and safeguards for iterative propagation and cluster consistency.

Show the effective values, model version, and calibration status globally in the
tree interface. Record them with the generated result. Parameter changes must
invalidate the previous build and trigger automatic reconstruction.

**Agreed numerical values:** documents/images have source factor `1.0`;
books/notes have source factor `0.5`. Other numerical defaults, including the
additional guess factor, remain implementation work to choose, document, and
evaluate.

## Apply matching to all source people

Use a common evidence model for source-to-source and source-to-registry
comparisons. Registry IDs are fixed identity anchors, not the boundary of the
search space. Different confirmed IDs must remain separate.

After supported matches, combine the person's dated attestations and family
context so other comparisons can use that information. Preserve provenance and
uncertainty throughout. The algorithm must not count its own earlier conclusion
as fresh, independent corroboration.

Evaluate competing candidates and the compatibility of complete clusters. A
chain of individually plausible pair matches must not join incompatible
namesakes, contradict explicit source distinctions or death constraints,
create a self-relationship, or create an ancestry cycle. Unresolved alternatives
must remain inspectable rather than being resolved by input traversal order.

Identity matching connects existing source-stated relationships. It must not
invent a second parent from marriage, parents from siblings, or kinship from
business association or geographical proximity.

## Storage and explanation

- `data/people.json` remains only confirmed person IDs and full names.
- Generated identities, relationships, matching calculations, effective
  parameters, probabilities, alternatives, and evidence belong in `data/tree.json`.
- Reconstruction must not rewrite historical source assertions to make inferred
  identities appear confirmed.
- Explain a match or non-match using the contributing signals, negative
  evidence, source references, competing alternatives, and the threshold used.
- Explain the remaining disconnected groups; do not use component count alone
  as an accuracy measure.

## Display and rebuild requirements already established

Display exactly **one card per reconstructed identity**, including shared
descendants and multiple marriages. Separate unresolved namesakes may still
have separate cards. Connect relationships to the existing card rather than
copying the person into another branch.

Rebuild automatically when source data, matching code, or global parameters
change. A verified graph has no permanent rebuild button; show a retry action
when automatic reconstruction fails.

The Elisabeth von Erligheim investigation illustrates why identity and layout
must be checked separately: her 11 typed mentions already formed one identity,
but the previous layout drew duplicate cards. Fixing that display behavior did
not implement the broader probability model requested here.

## Gaps found in the current matcher

| Current behavior | Remaining requirement |
| --- | --- |
| Place and title scores mainly compare mentions with existing registry anchors. | Apply them to all candidate source-person pairs and clusters. |
| Source-person clustering mainly uses family context. | Combine family evidence with places, titles, deaths, and temporal evidence. |
| Death compatibility is mostly a logical constraint. | Apply drastic probability reductions for conflicting death evidence, retaining valid hard exclusions and posthumous mentions. |
| Time comparison mainly uses fixed windows. | Introduce explicit temporal decay for document context and all titles, with much stronger base weights for scoped offices. |
| Matching scores are heuristic and uncalibrated. | Implement an explicit estimated-probability model and evaluate its quality. |
| Facts and guesses are separate selectable views. | Always include guesses in the normal result, with lower weight. |
| The requested source-category factors and same-fact associate signal are not implemented. | Keep document/image source factors at `1.0`, apply `0.5` to books/notes, and use deterministic same-fact name co-occurrence. |
| Thresholds and feature weights live in code. | Centralize effective parameters and show them globally in the viewer. |

Passing the existing software tests does not establish that these requested
features are implemented or that inferred historical identities are correct.

## Acceptance checks for the next implementation

1. Source people without registry IDs can be linked by combined place, title,
   chronology, and family evidence; no person-specific exception is needed.
2. Tests show how each requested signal changes the estimate, including
   counterexamples involving namesakes, title changes, time distance, partial
   death dates, and posthumous mentions. Holding other evidence constant, a
   matching title contributes less at greater time distance; a scoped office
   contributes much more than a generic rank at comparable distance; conflicting
   death evidence causes a drastic probability reduction or valid exclusion.
3. Comparable guessed evidence contributes less than factual evidence and is
   present in the normal reconstruction without enabling a separate mode.
4. Repeated extraction from one assertion and iterative identity propagation
   cannot inflate confidence through circular support. Separate document/image
   assertions retain their full source factor; book/note assertions receive
   exactly half the source weight of otherwise comparable assertions.
5. Ambiguous candidates and contradictory clusters stay separate even when a
   merge would reduce the number of disconnected graphs.
6. The viewer displays the global parameters and can explain individual match
   estimates. Parameter changes cause an automatic verified rebuild.
7. Report before/after graph coverage and fragmentation alongside reviewed
   positive and negative matching cases. More connections alone are not proof
   of improvement.
8. Output is reproducible, preserves the confirmed registry and source files,
   retains evidence and guess dependence, and displays each identity once.
9. “Called” and “born” designations use weighted title matching, property
   continuity uses place matching, and associates use deterministic personal-name
   co-occurrence within one fact. No numerical-age model or automated seal
   comparison is introduced.
