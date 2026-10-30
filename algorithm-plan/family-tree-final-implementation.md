# Family tree: final implementation

The implemented system reconstructs relationships from typed source assertions,
keeps uncertain identities visible, and exports the complete source-person
graph in `data/tree.json`. The confirmed registry in `data/people.json` contains
only IDs and full names. A Python engine computes the result; the
browser verifies and displays it. Source assertions remain in their original
JSON entries.

This document describes the shipped version, including its conservative limits.
The [algorithm plan](family-tree-algorithm-plan.md),
[research](family-tree-algorithm-research.md), and
[implementation plan](family-tree-implementation-plan.md) explain the preceding
design. The authoritative persisted format is documented in
[the People JSON rules](../rules/json-formats.md#people-json).

## Complete source-person reconstruction and separate storage (engine 3)

The first implementation displayed only nine relationships between existing
registry IDs. That projection was insufficient as the main family tree. The
current viewer uses the `evidence` views in `data/tree.json`,
including source people who have no permanent registry record or ID.

The engine starts with source occurrences, groups repeated participant references
within compatible dated passages, recognizes specifically cited duplicate
attestations, and compares source-stated family context across sources. It can
link repeated full spouse pairs and families with multiple relatives without
requiring either endpoint to have an existing ID. Grounded relatives and
co-parent context supply additional identity evidence; no marriage, sibling
closure, or additional parent edge is invented. Contextual name variants and
omitted surnames require family support and cannot bridge incompatible full
surnames. Matching remains inferred and all supporting source references remain
inspectable. Distinct registry anchors, source distinctions, incompatible deaths,
and parentage cycles constrain complete proposal groups.

The source graph preserves individual or contextual identities when no justified
cross-source match exists. Those nodes are not claims that each occurrence is a
separate historical person. Permanent registry IDs and original fact participants
are unchanged. Node pages show their original typed assertions and source links.
The family selector opens connected groups or all groups; the initial view
focuses the largest connected group containing registry anchors.

A reconstruction checked after this change contains 699 source identities and
483 relationships in the facts view, and 735 source identities and 511
relationships with guesses. These are dataset snapshots and may change as
source evidence or matching policy changes. The nine registry-only relationships
remain a projection, not the extent of the reconstruction.

`reconstruction.py` implements the source-person graph and contextual rounds.
Tree schema 3 stores each view's source references once in an indexed table, avoiding
repeated full citations in every node and derivation. It is documented in the
People JSON rules. The earlier architecture details below describe the initial
registry matching layer; references to omitted endpoints apply to that
projection. The complete source graph is now persisted and displayed.

## Running the reconstruction

Run commands from the repository root:

```sh
# Inspect a facts-only build; write nothing.
python3 scripts/rebuild_family_tree.py

# Compute facts-only and guesses-enabled views independently.
python3 scripts/rebuild_family_tree.py --include-guesses

# Inspect decisions, candidate scores, exclusions, and source references.
python3 scripts/rebuild_family_tree.py --include-guesses --explain vogt_zu_Lauda

# Write the generated tree with both validated views.
python3 scripts/rebuild_family_tree.py --include-guesses --apply

# Write a facts-only tree, removing the previous guesses view.
python3 scripts/rebuild_family_tree.py --apply
```

`--explain` accepts an exact anchor ID, participant reference, or occurrence
handle. `--search-limit N` changes the maximum number of search states per
connected component; the default is 10,000. The limit is recorded in build
metadata. Reaching it leaves the component's affected assignments unresolved.

The default command validates a complete proposed export in memory and prints
coverage and conflicts. Only `--apply` writes `data/tree.json`; rebuilding never writes `people.json`. There are no
generated report files, staging files, separate facts stores, or review queues.

## Architecture and code locations

```text
Source JSON + registry identities + name/place variations
    -> typed assertions and individual participant mentions
    -> exact anchors, contextual candidates, and constraints
    -> independent facts / with-guesses builds
    -> relationships, derivations, alternatives, and coverage
    -> validated tree.json output; unchanged confirmed people.json
    -> browser verification, tree, and person pages
```

The engine uses Python's standard library. Its public library entry points are
`load_inputs(root)` and `build(inputs, ...)`, exported by
[`scripts/family_graph/__init__.py`](../scripts/family_graph/__init__.py).

| File | Responsibility |
| --- | --- |
| [`rebuild_family_tree.py`](../scripts/rebuild_family_tree.py) | Arguments, terminal summaries, explanations, and explicit apply switch |
| [`model.py`](../scripts/family_graph/model.py) | Evidence dataclasses, internal registry handles, and shared fingerprint encoding |
| [`sources.py`](../scripts/family_graph/sources.py) | Recursive ingestion, inherited context, input snapshots, and registry identity projection |
| [`names.py`](../scripts/family_graph/names.py) | Compatible name forms without identifying namesakes |
| [`dates.py`](../scripts/family_graph/dates.py) | Inclusive date intervals and death compatibility, reusing validator date functions |
| [`policy.py`](../scripts/family_graph/policy.py) | Versioned thresholds, title categories, and scoped office rules |
| [`scoring.py`](../scripts/family_graph/scoring.py) | Candidate retrieval, exact-ID evidence profiles, feature scores, and exclusions |
| [`constraints.py`](../scripts/family_graph/constraints.py) | Self-relationship, ancestry-cycle, and combined death checks |
| [`resolve.py`](../scripts/family_graph/resolve.py) | Bounded component search and accepted/unresolved identity decisions |
| [`graph.py`](../scripts/family_graph/graph.py) | Evidence-view orchestration, conflict handling, relationships, and provisional alternatives |
| [`export.py`](../scripts/family_graph/export.py) | Serialization, generated-schema validation, and guarded tree replacement |

Candidate generation lives in `scoring.py`; there is no separate `candidates.py`.
Reconstruction has its own structured source walker. The existing search walker
and search command output were preserved rather than refactored into it.

## Source evidence and dates

The reader sorts and recursively scans JSON files under `data/books`,
`data/documents`, `data/notes`, and `data/images`. It loads the person registry,
name variations, and place registry separately. Malformed JSON, invalid typed
assertions, and invalid historical dates prevent reconstruction.

Each typed assertion retains its original object, historical date and bounds,
containing context, source path, zero-based JSON Pointer, assertion fingerprint,
and whether it came from `facts` or `guesses`. Each `person` or `of` occurrence
becomes a separate mention with its own handle, titles, and deceased status.
Repeated names do not become a shared person automatically.

Legacy strings and prose objects are counted but produce no automatic
relationships, identities, or living constraints. Runtime seal descriptions
also supply no genealogical assertions to this engine.

Document and image assertions can inherit the nearest historical date. Typed
book and note assertions require an explicit historical date; entry and
publication dates are not inherited. Explicit assertion dates override inherited
dates. Year, month, day, and existing inherited interval spellings retain their
source precision, with inclusive calendar-day bounds used internally.

Death constraints distinguish a stated death interval, an exclusive
`diedBefore` bound, and deceased status at an attestation. For example,
`diedBefore: "1394"` ends before 1 January 1394. A deceased marker supplies an
upper bound at the latest possible attestation day. An ordinary later mention
does not prove life and cannot, by itself, contradict an earlier death.

## Identity matching

### Anchors and compatible names

An exact, case-sensitive existing ID fixes the participant to that registry
person. Different IDs remain distinct. Registry relationships and the wording
of IDs contribute no genealogical evidence. The registry contains only IDs and names; titles and dates come from source
assertions.

Names are normalized using `data/names.md` and expanded place variations.
Comments are stripped from variation lines. The normalizer preserves the
distinction between Kunz and Konrad and between Münch von Rosenberg and
von Rosenberg. Matching normalized names retrieves candidates; it does not
establish identity, even when the registry contains just one candidate.

Records without IDs receive distinct internal handles, with collision avoidance
against actual IDs. Unresolved occurrences retain their own source-derived
handles. No permanent IDs or registry records are invented.

### Evidence profiles and scores

Profiles are built from assertions that explicitly name an existing ID. The
facts-only build uses factual observations; the optional build can also use
exact-ID guesses, with their dependencies marked. Inferred assignments are not
fed back into profiles as new independent evidence.

The current feature weights are:

| Feature | Score or effect |
| --- | --- |
| Same normalized name | Retrieval only; no score |
| Applicable reviewed office rule | +20 for its target; excludes other compatible anchors |
| Matching relative-age designation | +1.5 per designation |
| Matching territorial designation | +1 per designation |
| Matching rank/status designation | +0.25 per designation |
| Matching place and context role | +1 divided by the number of compatible candidates whose profiles contain it |
| Matching independently anchored relative and relationship | +8 per distinct relative/relationship feature |
| Incompatible combined death constraints | Candidate exclusion |

Title and place comparisons use a roughly ten-year proximity window. Missing
titles are neutral, and changed rank or age designations do not themselves
exclude a candidate. Unclassified titles supply no generic matching score.

The two default office rules are deliberately narrow:

| Designation and name | Target and scope | Required factual basis |
| --- | --- | --- |
| Eberhard von Rosenberg, Vogt zu Lauda | `vogt_zu_Lauda`, within 1385 | `data/documents/1385_2.json#/entries/0/facts/3` |
| Eberhard von Rosenberg, Vogt zu Dürn | `vogt_zu_Durn`, on 1342-09-03 | `data/documents/1342-09-03.json#/entries/0/facts/0` |

The basis must still exist and explicitly identify the target with the title.
These declarations do not identify every holder of either office across time.

Family support requires the other participant to be an exact ID in both the
evaluated assertion and a supporting relationship. Parent direction and kin
terms must agree. The evaluated passage and an identical attestation are
excluded from ordinary profile corroboration. Repeated title, place, and
relative features are capped rather than accumulated from every quotation.

Place matching reuses expanded place variations and longest-match behavior,
leaving ambiguous matches out of scoring. Its current contexts are document
issuance metadata and a death assertion's circumstances. Surname geography and
places inside titles do not become additional location features. Issuance
context does not establish the participant's physical presence.

These are explainable heuristic scores, not probabilities or measured
historical accuracy.

### Joint decisions and provisional groups

Only unexcluded registry candidates scoring at least 7 enter component search.
Every searched mention also has an unassigned option. Components connect
candidate identities, fixed anchors, and source-stated relationships. Bounded
enumeration rejects assignments producing self-relationships, directed ancestry
cycles, or incompatible combined death constraints.

The resolver retains solutions less than 3 points below the best score. It
accepts an assignment only when all retained solutions agree on that mention's
identity. An accepted contextual match remains `inferred`; an applicable office
rule can produce `reviewed`. Dependence on guesses makes an accepted non-anchor
assignment `inferred`.

Search exhaustion and competing solutions preserve uncertainty. Unresolved
same-name occurrences are also collected into provisional inspection groups
after resolution. Those groups are candidate alternatives, not merged people
or newly resolved identities. Relationships involving unresolved occurrences
remain in the in-memory evidence graph.

## Relationships, guesses, and conflicts

The CLI always computes a facts-only build. With `--include-guesses`, it calls
the same engine again with facts and guesses from the original inputs. It does
not seed the second run with inferred decisions from the first.

Resolved assertions generate directed `parent` edges and symmetric `spouse`,
`sibling`, and `kin` edges. Kin edges preserve the source term. Equivalent edges
retain separate supporting derivations. Marriage supplies no additional parent,
siblings supply no inferred parents or transitive siblings, and attestation
dates do not become relationship start dates.

Conflicting factual deaths or anchored factual ancestry cycles block affected
anchors' conclusions. Conflicting guessed death observations involving an
anchor are removed from usable hypothetical evidence and reported. Parentage
cycles involving exact-ID guesses are removed before identity matching, so a
contradiction cannot block matching in an unrelated family or supply identity
support. Only edges within a cyclic component are affected; bridges between
separate components remain available. Removed relationships are retained as
alternatives. Any remaining cycles after edge construction also remove
guess-dependent edges preferentially. This is
conservative conflict handling, not exhaustive reconstruction of every possible
historical alternative.

Each derivation records its evidence view, endpoint identity status, guess
dependence, and collected source references. A factual relationship can depend
on an inferred identity. Conversely, a relationship in the guesses-enabled
view can have a derivation independent of guesses. The two views are validated
separately.

## Persisted output and replacement

`data/people.json` is the manually curated list of confirmed, separate people.
Every record contains exactly `id` and `name`. IDs remain case-sensitive and
unique; namesakes can share a full name. Reconstruction never adds people or
inferred identities to this file and never rewrites it. Source assertions also
remain unchanged.

`data/tree.json` holds all generated calculation results: schema 3, engine 3,
policy 2, configuration, available views, input fingerprints, coverage, and each
view's complete evidence graph. It includes registry-backed nodes and provisional
source identities. Each view uses a deduplicated table of source references;
mentions, grouping evidence, and derivations reference its zero-based indexes.
The exact format is documented in the Tree JSON rules.

The registry-only count is a diagnostic projection, not the displayed graph.
New source people do not need permanent registry IDs to appear in the tree.
Unresolved identities stay visible with their original source references,
source-stated relationships, and uncertainty.

Fingerprints cover the historical source file set and contents, name and place
inputs, confirmed ID/name records, and engine/shared utility code. Generated
`tree.json` is excluded from inputs. Consequently identical builds reproduce the
same bytes without feeding their own conclusions back into matching.

The exporter validates references, participant assignments, names, derivations,
guess dependencies, and parentage consistency in memory. Before writing only
`tree.json`, it checks that source inputs, registry bytes, and the previous tree
bytes have not changed during computation. A conflicting edit prevents writing.
An unchanged tree is not rewritten. No timestamps or additional facts store are
introduced.

## Browser behavior

[`docs/app/data/relationships.js`](../docs/app/data/relationships.js) is the pure
adapter and evidence verifier. It checks the source file set, input hashes,
individual source pointers and hashes, endpoint references, and both available
graph views. Stale or unverifiable evidence produces a visible message and no
accepted generated edges. The browser does not rerun Python identity matching.

The active loader reads `people.json` and `tree.json` separately and passes the
selected view explicitly. A missing or stale local tree triggers the Python
rebuild and verified reload, with a manual rebuild action available as well. A saved preference
cannot enable an unavailable guesses view. Local and published source discovery
include nested JSON and watch registry/name/place/engine inputs plus the
generated tree for refresh. The output is never ingested as source evidence.
Successful local saves advance a repository revision so the viewer can
reverify evidence before subsequent rendering.

The diagram draws exactly one card for each identity, including multiple
marriages and shared descendants. A layered graph layout replaces the former
branch expansion, which copied people into parent branches and separate
marriage pairs. Spouses share a generation when consistent with recorded
ancestry; conflicting marriage alignment is routed across generations instead
of copying identities. Every parent or spouse connector represents an existing
edge. Children share a bus only when their complete recorded parent sets agree;
marriage supplies no additional parent. Long connectors route around cards.
Dense relationship networks can have crossing lines, without duplicated cards.

The Elisabeth von Erligheim investigation demonstrated the distinction: all 11
typed attestations from 1381–1395 already formed one inferred source identity,
including the spouse and mother attestations. The old diagram rendered her twice
and repeated her children under both parents. The layout now displays that one
identity once. Real-source and synthetic regressions cover identity membership,
unique cards, exact connector endpoints, multiple marriages, shared ancestry,
generation conflicts, namesakes, and both evidence views.

Tree and person pages include a relationship panel with sibling and kin edges,
source links, derivation details, and separate labels for inferred identity and
guess dependence. Inferred parent and spouse connectors are dashed. A summary
badge is needed only when every available derivation has that uncertainty;
individual derivations remain inspectable.

Exact-ID routes select an anchor. Ambiguous name routes list possible registry
people instead of selecting the first namesake. Mention years use direct typed
ID references and historical dates, with a retained image-title mention
fallback. They are displayed separately from life dates. Unresolved source identities are displayed in the graph and have their own
source-attestation pages. Family selection makes the complete graph browsable.

The adapter retains read compatibility for old embedded builds during migration.
New exports only use `tree.json`; the confirmed registry has no relationship or
build fields.

## Initial registry projection result and verification

The read-only run checked while writing this document loaded 1,062 typed
assertions and counted 1,674 factual prose items and 164 prose guesses:

| Evidence view | Exported relationships | Omitted relationships | Unresolved mentions | Conflicts |
| --- | ---: | ---: | ---: | ---: |
| Facts | 9 | 528 | 1,443 | 0 |
| With guesses | 9 | 557 | 1,519 | 0 |

These are a dataset snapshot, not fixed acceptance targets or accuracy scores.
Omitted counts refer to relationship edges that cannot be serialized with
resolved registry endpoints, not to a count of disproven source assertions.

Implementation verification passed 52 Python tests and 47 Node tests, both
source-data validator modes, registry identity-field preservation, byte-for-byte
repeatability, and active loading/evidence verification against a local server.
The browser-module tests exercise adapters and rendering; they are not a full
interactive browser walkthrough.

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.mjs
python3 scripts/validate_facts.py
python3 scripts/validate_facts.py --strict-migration data/books data/notes
git diff --check
```

Focused coverage lives in
[`test_family_graph.py`](../tests/test_family_graph.py),
[`relationships.test.mjs`](../tests/relationships.test.mjs), and
[`tree-layout.test.mjs`](../tests/tree-layout.test.mjs). It includes identity
separation, posthumous mentions, partial dates, circular corroboration, guessed
identity dependencies, conflicts, ambiguity, stale inputs, multiple marriages,
repeated ancestry, and deterministic export. The source-fact validator handles
assertions; generated genealogy validation belongs to the reconstruction CLI.

## Limits and future extensions

Connected families can remain incomplete when source identity is ambiguous.
The viewer exposes those source groups and their attestations instead of
restoring unsupported relationships or forcing namesakes together.

- Structured living-activity assertions are absent, so a later ordinary mention
  cannot safely exclude a deceased candidate.
- Shared historical event IDs are absent. Feature caps and attestation keys
  reduce duplicate influence but do not fully establish source independence.
- Registry candidate profiles do not bootstrap identity from a unique name.
  Contextual source-person grouping does not promote inferred people to the
  confirmed registry.
- Scoring does not extract transactions, property continuity, associates,
  individual seal identities, or residence/activity roles from prose.
- The joint search considers above-threshold registry candidates and an
  unassigned option. It is not an unrestricted search over all possible
  genealogies or all combinations of conflicting guesses.
- Feature scores and thresholds are heuristic. The real-source regression
  cases do not constitute a calibrated historical precision/recall benchmark.

Living activity, stable source/event identifiers, structured place and
transaction roles, richer reviewed identity constraints, and broader historical
evaluation remain separate future work. They require explicit schema and policy
changes before they can become matching evidence.
