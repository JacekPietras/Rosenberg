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
├── titles.md     # Equivalent title words and epithets for matching
├── kinship.md    # Tree positions meant by source kinship terms
└── places.json   # Place-name variants and coordinates
algorithm-spec/   # Family reconstruction rules and algorithm
docs/             # Browser viewer for the dataset
rules/            # Conditional instructions for data work
```

## Rules for data work

Read [`rules/json-formats.md`](rules/json-formats.md) when creating or editing
JSON under `data/`. It describes the book, document, people, and places formats.

Read [`rules/facts.md`](rules/facts.md) before adding, changing, reviewing, or
removing facts. It covers extraction, relevance, normalization, and source
verification.

## Browser viewer

The viewer is published at <https://jacekpietras.github.io/Rosenberg/> (read-only). 
For local testing and modifications under <http://localhost:8000/docs/>, run `./server`

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

The registry and generated tree schemas are documented in [rules/json-formats.md](rules/json-formats.md).
Matching uses an explicit, uncalibrated log-odds model across all source
identities, with global parameters in `data/matching.json`. Records join their
most probable same-name candidate unless something forbids it (death,
impossible age, distinct registry IDs, known relatives, a different father or
mother); undecided candidates are kept as "possibly the same person". The tree
stores comparison probabilities, feature contributions, rejected alternatives,
and provenance; tree and person pages explain them. The rules and passes are
specified in [algorithm-spec](algorithm-spec/), starting with its
[domain rules](algorithm-spec/domain-rules.md).

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

Check given-name and surname variants, then test each surviving full-person
combination. The checker prints each full query and `true` or `false`; progress
appears on standard error:

```text
python3 scripts/archive_search/check_variations.py monasterium 'Eberhard von Rosenberg'
python3 scripts/archive_search/search_monasterium.py Rosinberg --exists
```

The checker accepts a full name with `von`, finds given-name variants in
`data/names.md` and exact matching place variants in `data/places.json`, and
tests the prefixes `von`, `v`, `v.`, `von.`, and `de`. Unknown names use the
spelling supplied. It may take a long time because every surviving combination
is checked with the archive’s normal delays. Successful true and false checks
are saved by archive and exact query in
`.cache/archive_search/variation_checks.sqlite3`, including after an interrupted
run. Subsequent runs reuse them without another request. The cache does not
expire automatically; delete the file to check again, or use `--results-cache`
to select a separate cache. The archive scripts may also have their own search
caches.

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

Equivalent title words and epithets used for identity matching (for example
`Vogt, Voigt, advocatus` or `der Rote, Rufus`) are listed in
[`data/titles.md`](data/titles.md), one group per line with the canonical form
first. They are not personal names and do not belong in `data/names.md`.

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

Run `python3 scripts/facts/validate_facts.py` to validate facts in the data.

