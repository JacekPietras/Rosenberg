# Family tree: current implementation

Engine 4 / policy 3 implements the
[probability-matching requirements](probability-matching-requirements.md).
The normal tree always uses facts and lower-weight guesses. Probability values
are explicit model estimates, **not calibrated historical accuracy**.

## Run and configure

```sh
python3 scripts/rebuild_family_tree.py
python3 scripts/rebuild_family_tree.py --apply
python3 scripts/rebuild_family_tree.py --explain 'Elisabeth von Erligheim'
python3 scripts/rebuild_family_tree.py --facts-only
```

The CLI is read-only without `--apply`. Normal builds compute a separate
facts-only audit and an independently built weighted view. `--include-guesses`
remains accepted for compatibility; guesses are now included by default.
`--facts-only` is an explicit audit command. The normal viewer always selects
the weighted view and regenerates a facts-only artifact before displaying it.

`data/matching.json` is the authoritative global configuration. The viewer's
**Matching parameters (global)** panel shows all effective settings. Changes to
this file, source data, or matching code invalidate the previous result and
trigger a verified local rebuild. Only a failed rebuild exposes a retry button.

Initial assumptions include:

| Parameter | Value |
| --- | --- |
| Compatible-name prior | 0.05 |
| Merge threshold | 0.85 |
| Reciprocal candidate margin | 1.0 log-odds |
| Documents / images source factor | 1.0 |
| Books / notes source factor | 0.5 |
| Additional guess factor | 0.45 |
| Scoped-office title contribution | 8.0 before decay/reliability |
| Generic-rank contribution | 0.75 before decay/reliability |
| Death-conflict penalty | 20.0 before reliability |
| Explicit-distinction penalty | 20.0 before reliability |

These values encode assumptions and tested behavior; they are not fitted
probability estimates. All other category weights, half-lives, temporal scales,
caps, and iteration limits are in the configuration and global viewer panel.

## Source ingestion and context

The reader recursively scans JSON under books, documents, notes, and images.
Typed assertions retain their historical dates, source references, names,
titles, death status, and participant fields. Name normalization preserves
Kunz/Konrad and Münch/non-Münch distinctions. Books and notes require explicit
historical assertion dates; publication dates never supply them.

Dated textual facts and guesses supply supporting context through deterministic
recognition of `XXX von YYY` personal names. Context attaches only when the name
selects a unique source participant in the same dated passage. Co-occurrence is
within one fact, not an entire entry. Recognized places use `places.json` and its
variations; personal names are stripped before matching geographical context so
surname places do not become evidence of property ownership or residence.
Property words select the property-place feature. No family relationships or
titles are extracted speculatively from prose, and no source assertions change.
Undated or ambiguous text is not attached automatically.

## One source-to-source probability model

Exact case-sensitive registry IDs seed fixed identities. Source-local repeated
participants and specifically cited duplicate attestations can be grouped when
consistent. Different registry IDs always remain separate. Registry biography,
legacy genealogy, and the wording of IDs supply no identity evidence.

The source matcher compares all compatible-name groups, including groups with
no registry IDs. It starts from a compatible-name prior and adds explained
log-odds contributions, then applies the logistic function:

```text
logOdds = log(prior / (1 - prior)) + sum(contributions)
probability = 1 / (1 + exp(-logOdds))
```

Features include dated titles, place/property associations, same-fact associates,
formal family context, death conflicts, explicit participant distinctions,
document time distance, and the combined span of attestations. The latter is a
temporal consistency penalty, not an invented biological age or lifespan.

Every title category decays with time, including age epithets, ranks, territorial
scope, offices, and called/born designations. Scoped offices are much stronger
than generic ranks. Missing titles are neutral; changing from younger to elder
or Edelknecht to Ritter is not automatically a contradiction. Opposed age titles
supply a time-decaying negative feature; explicit source distinctions remain
constraints. Death intervals preserve precision, exclusive diedBefore bounds,
and deceased status. A later ordinary mention is not proof of life.

An assertion's source factor is multiplied by its guess factor when relevant.
For a pair of observations, the weaker effective reliability scales the feature.
There is no additional document/image discount based on catalogue type or
perceived independence. Features are capped by category, place, associate,
or relative so repeated extraction does not invent additional support.

Family profiles use exact anchors, linked relatives, full relative names, and
co-parent context. They collect the candidate's titles from relationship facts;
they never transfer a relative's title onto the candidate. Accepted links retain
confidence and dependencies for later frozen rounds. Evidence about rival
candidates is retained when it affects selection, including negative guessed
evidence. The algorithm's earlier conclusion is not independent corroboration.

Candidates must pass the configured threshold and reciprocal margin. Complete
candidate components and connected source families are checked jointly before
merging, preventing input order from selecting an arbitrary incompatible pair.
Checks preserve distinct IDs, compatible factual deaths, explicit distinctions,
no self-relationships, and acyclic parentage. Strong negative pair evidence also
constrains transitive clusters. Competing matches remain unresolved. Guessed
death contradictions remain available as weighted evidence rather than silently
disappearing; incompatible guessed ancestry alternatives remain excluded from
the active graph with their source provenance retained.

The older registry candidate resolver remains a diagnostic layer. Its inferred
assignments never seed the source matcher or bypass the global probability
configuration. The displayed graph and CLI identity explanations use the new
source model. Registry relationship coverage counts the actual source graph.

## Persisted results and verification

`people.json` remains exactly the confirmed ID/name registry. Reconstruction
writes only `tree.json`, using schema 4. It never changes source assertions or
creates permanent IDs for inferred people. Input snapshots include matching
parameters and engine/shared utility code; the output is never its own input.
Intervening source, registry, configuration, or tree edits prevent an overwrite.
Identical builds reproduce identical bytes and do not rewrite an unchanged tree.

Each view stores a deduplicated indexed source table, source-person nodes,
explicit relationships, and substantive candidate comparisons. Comparisons
retain original mention handles, the model round, estimated probability,
log-odds, named feature contributions, source references, guess dependence,
status, and a reason. Status distinguishes accepted matches, below-threshold
pairs, ambiguity, incompatible clusters, and earlier comparisons superseded by
later cluster evidence. Name/time-only pairs with no substantive context are
not persisted. Full calculations remain in the tree; the viewer displays a
bounded list and the CLI can explain a selected identity.

Node confidence records the weakest accepted link in its cluster. Exact/local
grouping defaults to 1; that is not a probability of historical existence or
permanent confirmation. Derivations distinguish assertion evidence weight from
endpoint identity probability, which remains null when correspondence is open.

Python and browser verification check versions, input/source fingerprints,
participant assignments, exact anchors, supported names and kin terms,
guess dependencies, parentage consistency, effective configuration, and
probability arithmetic. Browser validation does not rerun identity matching.
Older viewer artifacts retain migration read support.

## Diagram

Each identity has exactly one card, including multiple marriages and shared
descendants. A layered graph layout aligns spouses when ancestry permits and
routes long edges around cards. Every connector represents an existing parent
or spouse assertion. Shared buses require identical recorded parent sets;
marriage never supplies another parent. Dense graphs may have crossing lines,
without duplicate cards. Source-person and registry pages show provenance and
identity-comparison explanations. Inferred identities remain labelled.

Elisabeth von Erligheim is a real-source regression: all 11 typed spouse/mother
attestations form one source identity in both audit and weighted results, and
that identity is drawn once. Arnold's wife Else remains a distinct fixed ID.

## Validation and remaining limits

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.mjs
python3 scripts/validate_facts.py
python3 scripts/validate_facts.py --strict-migration data/books data/notes
git diff --check
```

Tests cover signal direction and strength, all title decay categories, agreed
source factors, always-included weaker guesses, posthumous mentions, drastic
death penalties, same-fact boundaries, property associations, explicit
distinctions, namesakes, rival-evidence provenance, probability export and
verification, parameter-triggered rebuilds, deterministic output, registry
preservation, and unique cards in both views.

More connections are not themselves an accuracy measure. Remaining groups
include namesakes and records without enough distinguishing evidence. Half-weight
book/note evidence can also leave groups separate that the former unweighted
heuristics joined. This is a model to evaluate against reviewed positive and
negative identities, not a calibrated historical benchmark. No numerical-age
model, speculative prose relationship extraction, or automated seal comparison
is introduced. Seal comparison remains human work.
