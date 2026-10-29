# Implementation plan for family reconstruction in Rosenberg

This document turns [the algorithm plan](family-tree-algorithm-plan.md) and
[the research findings](family-tree-algorithm-research.md) into a proposed
implementation for this repository. All new paths, commands, and schemas below
are proposals. Creating this plan does not implement them or modify historical
data.

## 1. Target behavior and scope

Implement a Python reconstruction engine and CLI. It reads source assertions,
resolves participants conservatively, constructs relationships, and replaces the
relationship fields in `data/people.json`. The browser displays the generated
graph and its evidence.

The default run uses facts. An optional run includes guesses, while retaining a
separate facts-only result. Both identity uncertainty and guess dependence remain
visible. Incomplete evidence may yield an incomplete tree.

Existing relationships are excluded from reconstruction. Existing person IDs
remain distinct anchors. Source assertions, text, translations, and citations
stay in their existing JSON entries. Do not automatically create registry
people, rewrite fact participants, or extract new assertions from prose.

Use Python's standard library initially and the existing browser module
structure. There is no need for a graph database, RDF conversion, machine
learning service, separate facts database, or persisted review queue.

## 2. Current integration points

| Existing path | Current behavior relevant to the implementation | Planned treatment |
| --- | --- | --- |
| `scripts/validate_facts.py` | Validates typed facts and guesses, including deaths; provides partial-date and interval functions | Reuse date semantics; extend validation for proposed registry output separately |
| `scripts/search_facts_by_name.py` | Recursively reads facts, renders typed participants, and synthesizes seal descriptions | Extract reusable source traversal; keep search behavior and synthetic seal observations distinct |
| `scripts/search_places_by_name.py` | Counts places in rendered matching records, including names and titles | Reuse recognition behavior, not its broad same-name result set as identity evidence |
| `scripts/place_names.py` | Expands settlement and building variants | Reuse directly |
| `docs/app/screens/tree.js` | Builds a tree from `wife` and `children`; uses IDs or names as keys | Consume explicit graph edges; remove ambiguous name fallback and spouse-component grouping |
| `docs/app/data/entities.js` | Parses the people array and place variants | Validate and expose the new generated relationships |
| `docs/app/data/loader.js` | Loads people and source documents | Make generated graph and available evidence modes accessible |
| `docs/app/screens/router-view.js` | Calls the tree renderer with people and documents | Pass graph view and filtering options |
| `docs/app/screens/entities.js` | Builds person pages and source fact lists | Add generated relationship and identity explanations without changing stored facts |
| `docs/app/viewer.js` | Owns viewer state and includes a legacy loading function | Wire controls and verify the active loading path; avoid unrelated cleanup |
| `docs/serve.py` | Local source listing uses top-level `glob`; published listing is recursive | Align local source discovery with recursive source ingestion |
| `tests/` | Has Python `unittest` suites and Node `.test.mjs` suites | Extend the existing testing approach |

The current tree also derives mentioned years mainly from legacy text matches.
Replace that calculation with typed participant matching and historical date
resolution, keeping mentioned dates separate from living dates.

## 3. Proposed Python structure

Add a focused package under `scripts/family_graph/` and one entry point:

```text
scripts/
  rebuild_family_tree.py
  family_graph/
    __init__.py
    model.py
    sources.py
    dates.py
    names.py
    policy.py
    candidates.py
    constraints.py
    scoring.py
    resolve.py
    graph.py
    export.py
```

Keep modules small; combine adjacent responsibilities if separate files would
only add indirection. The CLI handles arguments and presentation; library
functions accept explicit inputs so tests do not depend on the live dataset.

### Internal records

Use dataclasses for the following concepts:

- `SourceRef`: repository-relative path, zero-based JSON Pointer, assertion
  fingerprint, containing citation, and evidence kind.
- `Assertion`: original object, resolved historical interval, participant
  mentions, and its source reference.
- `Mention`: source reference plus participant field, exact reference string,
  normalized name, titles, and deceased status.
- `Candidate`: mention, possible registry or provisional identity, feature
  contributions, exclusions, and supporting source references.
- `IdentityDecision`: accepted, rejected, or unresolved, with alternatives,
  assignment method, dependencies, and evidence mode.
- `Relationship`: relation type, endpoints, kin term where relevant, and
  alternative derivations supporting the edge.
- `BuildResult`: identities, relationships, unresolved assertions, conflicts,
  input fingerprints, and diagnostics.

Keep these internal structures separate from source fact schemas. Do not add
`evidence`, `assessment`, or matching scores to typed source facts.

## 4. Source ingestion and shared utilities

`sources.py` scans JSON recursively only within `data/books`, `data/documents`,
`data/notes`, and `data/images`. Load `people.json` and `places.json` separately.
Sort paths for deterministic traversal. Reject malformed input with its path;
do not silently skip unreadable JSON in a reconstruction run.

Visit each `facts` or `guesses` array exactly once. Retain its enclosing source
entry and historical date context. Prose items are counted and available for
inspection, but do not generate automatic relationships or living constraints.
Never infer a person from a normalized ID-like token: exact case-sensitive IDs
are the only automatic ID references.

Refactor the source walker used by search into a shared utility only after
adding coverage for existing search behavior. Preserve the search command's
public output and matching semantics. Reconstruction should use structured
records, not parse search output. Runtime seal descriptions remain contextual
observations, not new source-supported genealogy facts.

In `dates.py`, centralize or wrap the tested `date_bounds` and
`inherited_date_bounds` semantics. Use one documented internal interval
convention, preferably inclusive calendar-day endpoints, and explicit exclusive
death-bound comparisons. Cover leap days, year/month precision, and all supported
document interval spellings. Never inherit publication dates into book or note
assertions.

In `names.py`, share normalization without the search tool's ID-token alias
expansion. Strip `//` comments before reading variation lines. Preserve family
boundaries and the repository's explicit treatment of Kunz. A normalizer returns
compatible names, not a resolved person.

## 5. Identity policy, titles, and chronology

Start with a versioned `policy.py` containing title classes and deterministic
decision rules. Its declarations are algorithm policy, not historical evidence.
Use source references to justify any identifying office rule. Initially support
the user's explicit Lauda/Dürn separation and general separation of existing IDs.

An identifying office rule must specify the canonical name, title, target ID,
applicable context/date scope, and its evidence basis. Do not infer such a rule
merely from the titles currently stored on a registry record. Unknown title
categories supply no automatic identifying force.

Maintain three title behaviors:

1. Reviewed office discriminators within their declared scope.
2. Relative age designations evaluated near their dated attestations, preserving
   the distinction among Junge, Jüngere, Alte, and Ältere.
3. Rank/status and territorial associations supplying soft evidence.

Missing titles are neutral. Rank progression and changed age epithets are
allowed. A title conflict is a hard exclusion only where a reviewed rule or an
explicit source distinction establishes that consequence.

Build death constraints from typed deaths and participant deceased markers.
For deceased status, derive only a bound compatible with the complete
attestation interval. Mere mentions do not imply life. Initial implementation
must explicitly report that it cannot reject most later mentions using death
alone because structured living-activity evidence is not yet available.

Conflicting anchored deaths are data conflicts. Keep the person ID fixed and
block affected conclusions rather than choosing whichever statement was read
first. Guessed death bounds remain optional and defeasible.

## 6. Candidates, scores, and joint resolution

### Candidate generation

For each unresolved participant, retrieve compatible registry names and
compatible provisional mention groups. Include an unassigned alternative even
when only one registry record matches. Registry uniqueness does not establish
historical uniqueness.

Give no-ID registry records internal handles for a single run; do not treat
shared display names as keys. Do not add permanent IDs or person records during
reconstruction.

### Evidence profiles

Initially build anchor profiles from explicit-ID facts only. Include dated
titles, deaths, source-stated relatives, and recognized places. A repeated phrase
or duplicated source assertion must not increase confidence repeatedly.

Use place IDs where available and preserve ambiguous alternatives. Classify
places found in names/titles separately from places in assertion content and
document metadata. Do not assign a specific activity role to a place unless
structured evidence supports it. A title's place must not be counted again as an
independent corroborating feature.

Without shared event identifiers, duplicate-source detection will be incomplete.
Deduplicate exact assertions and explicitly shared citations conservatively;
mark uncertain source independence. Do not claim that all different books are
independent witnesses.

### Scoring and decisions

Return named feature contributions, not one opaque number. Use common-name and
common-place frequencies within compatible candidates to reduce their
discriminating weight. Missing data are neutral. Keep initial weights explicit
and versioned; they are ranking heuristics until evaluated on reviewed cases.

Automatic inferred assignments require an evidence threshold, a margin over
alternatives, and independent contextual support beyond the name. No guessed
support can produce a certain identity. Even accepted inferred assignments
retain the label `inferred` in the generated output.

### Joint resolution

Build components of mentions connected by candidate overlap or source-stated
relations. Search consistent assignments within each component, using branch and
bound or bounded enumeration initially. Check anchor separation, self-relations,
directed parentage cycles, and chronological satisfiability.

Exclude the assertion being evaluated and its dependent conclusions when using
relatives as corroboration. Preserve support dependencies to prevent circular
reasoning. Do not use spouse/sibling connectivity as identity transitivity.

If a search limit is reached, mark affected assignments unresolved. Do not label
the best explored assignment a proven unique result. Components with genuinely
competing solutions remain inspectable alternatives.

## 7. Facts and guesses: two independent builds

Always compute a facts-only build. With the optional guesses flag, compute a
second build from the same original inputs plus guesses. Do not seed it with
accepted inferred assignments from the first build.

Each build uses the same engine and policy. Guesses may rank or exclude
candidates within that hypothetical view, but cannot override fixed IDs or
contradict firm factual constraints. Competing guesses may require separate
alternatives instead of one combined answer.

Store per-edge derivations for each view. A derivation contains all assertion
and identity dependencies, including negative evidence if it affected candidate
selection. An edge with a facts-only derivation remains available without
guesses even if another derivation uses guesses.

The optional run may assign a mention differently from the facts-only run.
Represent the two results separately rather than merely adding guessed edges
to an unchanged graph. Never silently erase the facts-only interpretation.

## 8. Proposed people.json relationship format

Keep the top-level people array and all existing identity/biographical fields.
Replace `wife` and `children` with a documented `relationships` array on each
record. Store a relationship once: on the parent for `parent`, and on a
deterministically selected endpoint for symmetric relations. Build reverse
navigation at runtime.

Illustrative output, not historical evidence:

```json
{
  "id": "example_parent",
  "name": "Example parent",
  "relationships": [
    {
      "type": "parent",
      "of": "example_child",
      "derivations": [
        {
          "view": "facts",
          "identity": "anchored",
          "usesGuesses": false,
          "sources": [
            {
              "path": "data/documents/example.json",
              "pointer": "/entries/0/facts/0",
              "fingerprint": "sha256:example"
            }
          ]
        }
      ]
    }
  ]
}
```

Finalize this schema and its invariants in `rules/json-formats.md` before
implementing persistence. Define `view` as `facts` or `with-guesses`, and
`identity` as `anchored`, `reviewed`, or `inferred`, where the edge takes the least
certain endpoint status. A `with-guesses` derivation may have `usesGuesses: false`
when it does not actually depend on a guess. Sources include identity support as
well as the relationship assertion. Preserve alternative complete support sets.

`of` uses an exact existing ID, otherwise a unique registry name. Unresolved or
ambiguous endpoints are not serializable as certain registry references. Keep
their assertions and alternatives in the read-only build result; count omitted
edges explicitly. Do not create duplicate name-only registry records.

The schema is for generated relationships, not typed source facts. It must allow
`kin.term`, multiple spouses, evidence references, and both views. Do not invent
relationship start dates from attestation dates. Store `relationships: []` on
people with no exportable relations.

The first version may show detailed scores only in CLI explanations; persisted
derivations must still contain enough evidence to reconstruct and inspect the
decision. Fingerprints detect stale pointers or edited assertions. If a source
changes, require a rebuild rather than interpreting a stale pointer as evidence
for a different assertion. Do not auto-relocate duplicate fingerprints.

## 9. CLI behavior and safe replacement

Proposed commands:

```sh
# Default: inspect a facts-only reconstruction; write nothing.
python3 scripts/rebuild_family_tree.py

# Compare independent facts-only and guesses-enabled results.
python3 scripts/rebuild_family_tree.py --include-guesses

# Explain identities and relationships involving this anchor.
python3 scripts/rebuild_family_tree.py --include-guesses --explain vogt_zu_Lauda

# Replace relationship fields after computing and validating the complete result.
python3 scripts/rebuild_family_tree.py --apply
python3 scripts/rebuild_family_tree.py --include-guesses --apply
```

Print counts and explanations to the terminal; do not introduce generated
reports, staging files, review queues, or a parallel facts store. `--apply` is
the explicit mutation switch, not an interactive permission prompt.

On apply:

1. Read and fingerprint all relevant inputs and policy.
2. Build from a projection of registry identities excluding all relationships.
3. Validate the proposed graph and serialized registry entirely in memory.
4. Verify inputs have not changed during computation.
5. Replace relationship fields, preserving record order and unrelated values.
6. Write `people.json` once and review the Git diff.

Do not clear the file before the result is ready. A fatal validation error
prevents writing. Local ambiguity leaves affected edges unexported and visible
in diagnostics; it does not require rejecting unrelated valid components.
Anchored contradictions must never be serialized as accepted relationships.

A facts-only apply removes previously generated guesses-view relationships.
An apply with guesses stores both independently built views. Repeated identical
runs must produce identical bytes; avoid timestamps and volatile scores in
persisted output. Do not overwrite intervening user changes.

## 10. Viewer integration

Add a pure relationship adapter, proposed as
`docs/app/data/relationships.js`. It resolves exact IDs, permits unique names,
builds reverse indexes, filters derivations by view, and exposes provenance.
It must never use first-match or last-match fallback for ambiguous names.

Update the tree renderer to consume graph edges. Retain existing layout ideas
where possible, but replace the current union of spouse-connected components:
several marriages do not make every spouse one parental unit. Connect each
parent only to explicitly supported children. Repeated ancestry may create
multiple visual occurrences of one person, while person identity stays shared.

Display parent and spouse structure with sibling/kin connections available as
separate connectors or a relationship panel. Preserve the source kin term.
Avoid forcing all edge types into the same hierarchical layout.

Provide a facts/with-guesses control when both generated views exist. Also
distinguish anchored/reviewed identities from inferred assignments. An edge
based on a factual assertion can still need an uncertainty marker for identity.
Show source links and derivation details on selection.

In `loader.js`, `router-view.js`, and viewer state/preferences, pass the selected
view explicitly. Ensure preferences cannot silently enable unavailable guesses.
Person pages retain source assertions and add generated relationships as a
separate section.

Align recursive file discovery in `docs/serve.py` with the published repository
listing. Stale evidence should be visibly marked and excluded from accepted
graph display until rebuilt. Do not implement the Python matching algorithm
again in JavaScript; the browser consumes its result and validates references.

During development, support legacy relationship rendering only when the
generated schema is absent. Once a record has generated relationships, do not
combine them with its old `wife` or `children` values.

## 11. Implementation sequence and completion criteria

### Phase 1: source model and exact-ID baseline

Implement shared date/name utilities, source traversal, internal records, exact
IDs, and typed relationship construction. Add the read-only CLI. Preserve all
unresolved mentions and report prose coverage separately.

**Complete when:** nested books/notes/documents/images and their dates are read
correctly; changing old registry relationships cannot change the result; search
and validator regressions pass.

### Phase 2: conservative contextual matching

Implement title policy, chronological constraints, direct-ID place profiles,
candidate explanations, and provisional identities. Keep this read-only.

**Complete when:** reviewed title rules can identify a mention, names alone
cannot, Lauda/Dürn stay separate, posthumous mentions remain valid, and inferred
matches expose their supporting evidence and alternatives.

### Phase 3: collective resolution and guesses

Implement bounded component search, dependency-aware family evidence, separate
facts/guesses builds, and conflict handling.

**Complete when:** circular corroboration cannot inflate confidence, search
limits leave uncertainty, optional evidence does not contaminate facts-only
results, and repeated editions do not multiply known shared evidence.

### Phase 4: schema and viewer support

Document the generated schema, implement its validator and serializer, add the
browser adapter, and update the tree/person pages with fixtures. Add recursive
local discovery and evidence-view controls.

**Complete when:** the browser correctly handles multiple marriages, identical
names, kin/sibling relationships, uncertain endpoints, repeated ancestry, and
stale evidence. Real `people.json` still need not be rewritten for this phase.

### Phase 5: relationship replacement

Enable `--apply`, reconstruct the live dataset, inspect excluded/conflicting
cases, and review the smallest data diff. Do not manually restore unsupported
old relationships to make the result look complete.

**Complete when:** old relationship fields have been replaced, output is
idempotent, source files are unchanged, both evidence modes behave as documented,
and every exported edge has valid supporting derivations.

## 12. Verification

Add focused Python suites for source traversal, identity resolution, and export,
plus browser adapter tests. Use synthetic cases for logical boundaries and a
small reviewed set of real source cases for historical evaluation. Do not treat
the old registry genealogy as the expected answer.

Required cases:

- IDs match case-sensitively and remain distinct; ID wording supplies no kinship.
- A single matching registry name is still potentially ambiguous.
- Missing titles are neutral; younger/elder and Edelknecht/Ritter can change.
- A later deceased mention is compatible with an earlier death.
- Explicit living activity, once formally supported, conflicts with earlier
  firm death bounds; partial-date overlap alone is not a contradiction.
- Spouses do not imply shared parentage; siblings do not imply full siblinghood
  or transitive sibling edges; kin terms are preserved.
- Guess-dependent identity changes remain separate from the facts-only graph.
- Duplicate citations, dependent features, and circular family evidence cannot
  supply false independence.
- Parentage cycles are rejected; repeated ancestry through different branches
  is allowed.
- Ambiguous endpoints are omitted with an explanation, not assigned to a first
  same-name record.
- Changed inputs prevent apply; stale evidence fingerprints are detected.
- Applying twice yields the same file and never changes source assertions.

Use the repository's existing test commands and extend them as modules land:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.mjs
python3 scripts/validate_facts.py
python3 scripts/validate_facts.py --strict-migration data/books data/notes
git diff --check
```

Record pre-existing validation failures before implementation so improvements
can be assessed without unrelated source edits. Add CLI graph/output validation
to the reconstruction command rather than suggesting that `validate_facts.py`
already checks genealogy consistency.

For viewer changes, exercise local and published-style loading, duplicate-name
navigation, mode toggles, source navigation, and layout fixtures. Update existing
Node tests deliberately when the renderer's public input changes.

## 13. Deliberately deferred data extensions

The first implementation must work conservatively with today's schemas. Later,
document and implement source-entry/event identifiers, living-activity
assertions, reviewed identity constraints, structured place roles, transactions,
and individual seal observations as separate targeted changes.

Living-activity assertions and shared event identifiers have the highest value:
they respectively enable safe death-based exclusion and better control of
duplicated evidence. Until then, expose those limitations in explanations rather
than filling missing evidence with assumptions.
