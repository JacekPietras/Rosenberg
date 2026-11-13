# Rosenberg Research Data

Digitized historical sources about the von Rosenberg family and related
Franconian/Odenwald families. Source text, English translation, and extracted
facts are kept together in `/data`.

## Repository layout

```text
data/
├── books/        # Structured source books
├── notes/        # Research notes
├── documents/    # Historical source documents
├── images/       # Armorial and effigy image collections
├── calendar.md   # Liturgical calendar and dated annotations
├── people.json   # Confirmed separate people: ID and full name only
├── tree.json     # Generated family graph and calculation results
├── matching.json # Global probability model parameters
├── names.md      # Historical given-name variants under # Men / # Women
├── name-connectors.md # Variants of terms introducing an alternate surname
├── distinctFamilies.md # Family labels excluded by default in document filters
├── titles-age.md     # Younger/older title classes and their forms
├── titles-office.md  # Offices, ranks and epithets with equivalent variants
├── kinship.md    # Tree positions meant by source kinship terms
└── places.json   # Place-name variants and coordinates
docs/             # Browser viewer for the dataset
specs/            # Conditional instructions for data work
  family_graph_algorithm/ # Family reconstruction rules and algorithm
```

## Rules for data work

Read [`specs/json-formats.md`](specs/json-formats.md) when creating or editing
JSON under `data/`. It describes the book, document, people, and places formats.

Read [`specs/facts.md`](specs/facts.md) before adding, changing, reviewing, or
removing facts. It covers extraction, relevance, normalization, and source
verification.

## Browser viewer

The viewer is published at <https://jacekpietras.github.io/Rosenberg/> (read-only). 
For local testing and modifications under <http://localhost:8000/docs/>, run `./server`

The local server stops after 20 seconds without a viewer heartbeat. It appends
shutdown reasons and UTC timestamps to `server.log` in the repository root,
including heartbeat timeouts, viewer-requested restarts, termination signals,
and unexpected errors. A forced kill or power loss cannot be recorded by the server.
The document classification (`?`) action starts the local Kev server on demand
when it is not already available. A Kev process started by the viewer server is
stopped when that server exits, including after the heartbeat timeout.

## Family Graph

### Reconstruct the family graph

Read the reconstruction without changing files:

```text
python3 scripts/rebuild_family_tree.py
python3 scripts/rebuild_family_tree.py --explain vogt_zu_Lauda
```

Use `--apply` to write `data/tree.json`. The result combines facts and lower-weight guesses. `data/people.json` contains
only confirmed IDs and full names; reconstruction never changes that registry. The tree includes people found in typed
source assertions, including people without registry IDs. Source-local family
groups and contextual links across sources remain distinguishable from fixed
registry identities. Ambiguous namesakes stay separate. The family-group
selector opens connected families or the complete graph; source-person pages
show original attestations. Counts describe source identities, some of which
may later prove to be the same person. The diagram displays each identity once,
including people with multiple spouses or shared descendants. The viewer exposes source
links, identity uncertainty, and the available evidence modes. The local viewer
checks for stale relationships when the family tree screen is opened and rebuilds them only if needed, then
reloads and verifies the result, preserving the existing evidence views and
search configuration. A **Retry rebuild** button appears only if automatic
rebuilding fails. Restart an already running local server once after updating
the viewer to enable automatic rebuilding. The published read-only site links to the local
viewer when a rebuild is needed.

The registry and generated tree schemas are documented in [specs/json-formats.md](specs/json-formats.md).
Matching uses an explicit, uncalibrated log-odds model across all source
identities, with global parameters in `data/matching.json`. Records join their
most probable same-name candidate unless something forbids it (death,
impossible age, distinct registry IDs, known relatives, a different father or
mother); undecided candidates are kept as "possibly the same person". The tree
stores comparison probabilities, feature contributions, rejected alternatives,
and provenance; tree and person pages explain them. The rules and passes are
specified in [specs/family_graph_algorithm](specs/family_graph_algorithm/), starting with its
[domain rules](specs/family_graph_algorithm/domain-rules.md).

The diagram defaults to parent/child and spouse lines; hovering over or focusing
a person reveals their sibling and other kin lines as well. Children with the same recorded parents
share a branch. In the default view, married parents use only the identifiable
father's stem for shared children; both parent assertions remain in the evidence
panel and appear when either connected person is hovered over or focused.

### Inspect saved graph connections

Inspect connections in the saved graph without rebuilding or writing files:

```text
python3 scripts/print_graph_connections.py vogt_zu_Lauda
python3 scripts/print_graph_connections.py '@evidence/KEY' --details
python3 scripts/print_graph_connections.py 'data/documents/1397-04-29.json#/entries/0/facts/0'
```

Accepts a person ID, evidence node key, exact full name, or source JSON pointer
(optionally ending in `/person` or `/of`). Prints family connections, supporting
sources, identity comparisons, and possible identity matches. Use `--depth 2`
for another family hop, `--details --comparison-limit 0` for all comparison
evidence, or `--json` for the full selected graph. Stale source fingerprints are
reported; evidence keys refer to the saved build and can change after rebuilding.

## Archives

Archive catalogs and related research portals are collected in [`data/notes/archives.md`](data/notes/archives.md).

### Archive record import

Archive record importers and their shared storage code live in
`scripts/archive_records/`. `archive_record_download.py` routes an archive catalog record to a source-specific
parser. These commands create or update document JSON entries with catalog
metadata and image links when available; they do not download image files into
the local cache:

```text
python3 scripts/archive_records/archive_record_download.py 'RECORD_URL'
python3 scripts/archive_records/archive_record_download.py --list
```

GDA Bayern, Landesarchiv Baden-Württemberg, Landesarchiv NRW, Regesta Imperii, Arcinsys Hessen, and Monasterium are supported.
Their downloaders create a date-named document JSON entry labeled `to review`,
with the catalog citation, German catalog text, and image links when available.
Regesta Imperii URLs can be HTML record links, persistent `/id/` links, or CEI
REST source links. Review the generated entry before using it as a completed
document record.

### Batch document label triage

`scripts/triage_documents.py` conservatively proposes branch labels from
explicit personal-name forms in document text. It recognizes Schenk, Mönch,
Rorschach, and Wok/Vok von Rosenberg attestations, named Rosenberg residences
at Boxberg, Haltenbergstetten, Schüpf, or Bartenstein, and the modern Orsini-
Rosenberg house. The last case proposes `deleted: true` and removes only the
managed family labels. It leaves mixed branch signals and indirect/place-only
mentions alone. URLs are excluded from matching. The default scans only active
`to review` documents and prints each candidate; it does not write files.

```text
python3 scripts/triage_documents.py
python3 scripts/triage_documents.py --limit 20
python3 scripts/triage_documents.py --all-labels
python3 scripts/triage_documents.py --apply
```

`--apply` writes only the document's `label` and, for the Orsini-Rosenberg
house, `deleted` field. Review the dry-run candidates first. Remaining records
are summarized by archive hostname and decade to support further triage.

### Exploratory Kev label benchmark

See [KEV.md](scripts/kev/KEV.md) for this Mac's setup, startup, API usage, and queue commands.

`scripts/kev/kev_benchmark.py` sends source text from document JSONL cases to a
local Kev `/v1/systemone` server. Each document is evaluated independently for
the seven categories `franconian`, `schenk`, `monch`, `rorschach`, `czech`,
`orsini`, and `unrelated`. The six family categories may overlap; `unrelated`
means none of those families is substantively relevant and cannot coexist with
a positive family category. Place or surname mentions alone do not establish
family relevance. Cases contain
`path` and `expected` fields, with optional `id`, `note`, and `source_quote`.
The runner reads source text, citations, and document date/place, never
existing labels, facts, guesses, or model decisions.

```text
python3 scripts/kev/kev_benchmark.py --cases /path/to/cases.jsonl
python3 scripts/kev/kev_benchmark.py --cases /path/to/cases.jsonl --model kev-latest --limit 10
```

For this local pilot, start `scripts/kev/run_kev_local.sh` from a normal macOS
Terminal so Kev can access Metal. The isolated runtime and model cache are
under `/private/tmp/rosenberg-kev` and `/private/tmp/rosenberg-kev-models`;
temporary directories may be cleared by the operating system. The launcher
binds only `127.0.0.1:8009` and pins `jaredpalmer/kev-4b@v1.0`.

The prepared 100-case pilot is in the ignored local directory
`reports/kev-benchmark/cases.jsonl`, with setup provenance in `setup.json`.
These are Luna-curated reference labels, not human-verified ground truth or
a representative sample of ambiguous records. Run it with
`python3 scripts/kev/kev_benchmark.py --cases reports/kev-benchmark/cases.jsonl --output reports/kev-benchmark/results.jsonl`.

The default server is `http://127.0.0.1:8009`; `--output` selects the resumable
JSONL result file (default `/tmp/rosenberg-kev-benchmark.jsonl`). A sidecar
`.summary.json` reports accuracy and confusion at 0.5, Brier score, and
exploratory abstention coverage/error at several thresholds. Results resume
only when the source fingerprint, full question/reference definition, case ID,
and actual server model configuration still match. Raw responses and model
cards are retained with request IDs. Confidence figures
are exploratory and not validated for this corpus. Oversized states and other
HTTP errors are recorded; source documents are never modified.

The local pilot's frozen prompt, source checks, validation assessment, and
audit receipts live under the ignored `reports/kev-improvement/` directory.
Once the validation gate passes, `python3 scripts/kev/kev_process_review_queue.py
--apply` scores the remaining active review documents locally and applies
only the enabled family labels. Without `--apply`, it only scores and checks
proposals. It checks source and frozen artifact hashes, preserves all other
document fields, and performs no deletions. `backlog-status.json` records the
current stage and final counts; `backlog-progress.log` records scoring progress.
The job is resumable. Keep the local Kev server running until it completes.

### Kev family classification

`scripts/kev/kev_classify_documents.py` provides a reusable dry scorer for a single
ten-way family choice: nine families (`franconian`, `schenk`, `monch`,
`rorschach`, `czech`, `lengenfelder`, `orsini`, `brandenburg`, `kamptal`) plus `other` for
all non-target material, including places, modern people, and other noble houses.
The family definitions are in [KEV.md](scripts/kev/KEV.md).
It accepts one document with `--document`, scored JSONL cases or, by default, scans only
active `to review` documents. The model receives date, place, citations, titles,
and complete German/Latin/summary text; English translations, labels, facts, guesses, and URLs
are excluded. It writes resumable, append-only JSONL with source and prompt
fingerprints, model identity, exact input hash/length, raw response, choice, and
probabilities. Errors are recorded and retried on a later run. It never applies
labels.

```text
python3 scripts/kev/kev_classify_documents.py --document data/documents/1397-04-29.json
python3 scripts/kev/kev_classify_documents.py --cases reports/kev-benchmark/cases-scored.jsonl --config reports/kev-improvement/frozen-config.json --output reports/kev-improvement/results.jsonl
python3 scripts/kev/kev_classify_documents.py --documents-dir data/documents --limit 20
```

An explicit `--config` overrides the default criteria and may retain the older
task, including its original categories. The current task requires fresh validation
before label application.
The frozen prompt and development selection are documented in
`reports/kev-improvement/selection.md`.

`scripts/kev/kev_label_review_documents.py` runs the single-document classifier for
each active document whose only label is `to review`. It adds every family label
whose probability is strictly above 25%, retaining `to review`; `other` is not
a document label. It applies labels by default and changes only the top-level
`label` value. Use `--dry-run` to print proposals without changing documents,
`--limit` to restrict the batch, or `--results PATH` to choose the classifier's
resumable JSONL results file.

`scripts/kev/kev_apply_labels.py` can consume a parent-approved validation gate
artifact and classifier JSONL. It defaults to a dry run and writes JSONL audit
receipts. `--apply` is required to update only eligible top-level document
labels; source text, facts, and nested fields are checked and preserved.

### Search archives

Archive search scripts are in `scripts/archive_search/`. For example:

```text
python3 scripts/archive_search/search_arcinsys_hessen.py 'Eberhard von Rosenberg'
python3 scripts/archive_search/search_landesarchiv_bw.py 'Konrad von Rosenberg'
python3 scripts/archive_search/search_landesarchiv_nrw.py 'Eberhard von Rosenberg' --list-only
python3 scripts/archive_search/search_regesta_imperii.py 'Eberhard von Rosenberg' --list-only
python3 scripts/archive_search/search_monasterium.py 'Eberhard von Rosenberg' --list-only
```

Use `--list-only` to list results without importing them. Use `--limit` to
restrict the number processed.

Screen given-name, title and place variants, then run a normal archive search
for each surviving combination. These searches import new records
and skip URLs already saved in `data/documents/`; progress appears on standard error:

```text
python3 scripts/archive_search/check_variations.py monasterium 'Eberhard von Rosenberg'
python3 scripts/archive_search/check_variations.py monasterium 'von Rosenberg'
python3 scripts/archive_search/check_variations.py landesarchiv_bw 'von Rosenberg' --skip-result-id 61710
python3 scripts/archive_search/check_variations.py monasterium 'Vogt zu Lauda'
python3 scripts/archive_search/check_variations.py regesta_imperii 'von Rosenberg' --exists-only
python3 scripts/archive_search/search_monasterium.py Rosinberg --exists
```

Use `--exists-only` with `check_variations.py` to screen the surviving full
queries for results without listing or importing records.

The checker accepts `von` or `zu` and a place, optionally preceded by a name or title.
It finds given-name variants in `data/names.md`, title variants in
`data/titles-age.md`, `data/titles-office.md`, and exact matching place variants in `data/places.json`. It
checks each surviving place with the prefixes `von`, `v`, `v.`, `von.`,
and `de`, as well as without a connecting word. Titles also use `zu` and `des`.
It uses only surviving particle-place pairs in full queries. Unknown names and titles use the
spelling supplied. It may take a long time because every surviving combination
is searched with the archive’s normal delays. Successful true and false checks
are saved by each archive search script, for direct searches and variation checks,
by archive and exact query in `data/archive_search/ARCHIVE.json`,
including after an interrupted run. Subsequent runs reuse them without another
request. Normal searches also skip queries saved as empty; queries saved as
positive still search for records. These files can be committed and published
with the rest of the data.
Results do not expire automatically; remove an entry to check it again, or use
`--results-file` to select a different results file. Archive scripts may also
have their own search caches.
For Landesarchiv BW, repeat `--skip-result-id ID` to omit specific catalogue
results from variation-check imports. Its downloader uses the direct catalogue
page when a search result's permalink does not resolve to that record, and the
search continues past individual results it cannot resolve or import while
reporting them. Use `--resume-after-result-id ID` to continue the first
Landesarchiv BW import after an interrupted catalogue result.

Monasterium skips normal searches containing a dot, since those duplicate the
undotted query. For `--exists`, it checks or reuses the undotted query instead.

All archive search scripts accept `--exists` and print `true` or `false` without
listing or importing records. They stop once the archive reports whether results
exist, reuse complete cached searches where supported, and observe their normal
request delays. Some archives require session setup before a search. Search behavior is archive-specific, so
an absent spelling only rules out combinations if the archive's matching rules
make that inference valid.

### Selected archive image

Follow the [archive image skill](.agents/skills/archive-image-download/SKILL.md)
to download a selected archive image.

## Facts

### Search facts

Search every `facts` array in JSON files under `data/` by person ID, full or
partial person name, surname, or place. This includes documents, books, images,
notes, and nested research records. Name searches recognize spelling variants
listed in `data/names.md`. Recognized person IDs in facts display the person's
full name followed by the ID in brackets. An ID search also includes same-name
facts without a recognized ID, marked `[not recognised]` after the name.

Use `--direct` with a person ID to return only facts containing `[that_id]`, skipping name-only matches.

```text
python3 scripts/search_facts_by_name.py vogt_zu_Lauda
python3 scripts/search_facts_by_name.py vogt_zu_Lauda --direct
python3 scripts/search_facts_by_name.py 'Eberhardi v. Roßenberg'
python3 scripts/search_facts_by_name.py Eberhard
python3 scripts/search_facts_by_name.py Rosenberg
python3 scripts/search_facts_by_name.py 'Eberhard von Rosenberg'
python3 scripts/search_facts_by_name.py Boxberg
```

### Search places mentioned in a person's facts

List unique canonical names from `data/places.json` mentioned in matching facts:

```text
python3 scripts/search_places_by_name.py 'Eberhard von Rosenberg'
python3 scripts/search_places_by_name.py vogt_zu_Lauda --direct
python3 scripts/search_places_by_name.py vogt_zu_Lauda --direct --count
```

The search uses the same person matching as the fact search, including name
variants and the optional `--direct` ID filter. Place names appearing in a
person's name or title are included as well. Use `--count` to show how many
matching fact records mention each place; repeated mentions in one record count once.

## Variations

### Names

Straightforward personal-name spelling variations are listed in
[`data/names.md`](data/names.md), one group per line with the canonical form
first, sorted under `# Men`, `# Women`, and `# Other` (non-given names). The
section gives the gender used by the family-tree reconstruction.

### Titles

Age titles are grouped under younger/older headings in
[`data/titles-age.md`](data/titles-age.md); each line keeps one title and its
direct variants. Offices, ranks, and epithets use the same one-group-per-line
format in [`data/titles-office.md`](data/titles-office.md). Titles are not
personal names and do not belong in `data/names.md`.

### Kinship terms

The tree positions a source kinship term can mean (for example `Vetter`: a
parent's brother, a sibling's son, or a cousin, never a brother, parent, or child)
are listed in [`data/kinship.md`](data/kinship.md). Facts keep the source term
verbatim; this file only guides matching.

### Places

Place-name variations are recorded in [`data/places.json`](data/places.json).
They help with place searches and with recognizing surnames formed as “von
<place name>”. The JSON file is long and has a more complex structure, so use
the script to list canonical place names and their recognized variations:

```text
python3 scripts/list_place_variations.py
python3 scripts/list_place_variations.py 'Boxberg'
```

Pass a place name or spelling variation to show only matching entries. Churches are excluded by default. Include them with `--include-churches`.

## Facts

### Fact validation

Run `./lint` to run all data linters. Use `./lint --all` to include documents
normally skipped by document validation, including deleted documents. Individual
checks live in `scripts/linters/`.

### Document validation

Run `./lint` to check document JSON files. Entries without English text are
reported as warnings; documents marked `"deleted": true` and documents with
the `Czechia`, `Schenk`, or `Mönch` labels are skipped by default. Use
`./lint --all` to include them.

