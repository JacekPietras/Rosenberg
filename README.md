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
├── names.md      # Historical name variants
└── places.json   # Place-name variants and coordinates
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

## Reconstruct the family graph

Read the reconstruction without changing files:

```text
python3 scripts/rebuild_family_tree.py
python3 scripts/rebuild_family_tree.py --include-guesses --explain vogt_zu_Lauda
```

Use `--apply` to write `data/tree.json`. The normal result always combines facts
and lower-weight guesses; a separate facts-only view is retained for audit.
`--facts-only` explicitly builds only that audit view; the viewer restores the
normal weighted tree automatically. `data/people.json` contains
only confirmed IDs and full names; reconstruction never changes that registry. The tree includes people found in typed
source assertions, including people without registry IDs. Source-local family
groups and contextual links across sources remain distinguishable from fixed
registry identities. Ambiguous namesakes stay separate. The family-group
selector opens connected families or the complete graph; source-person pages
show original attestations. Counts describe source identities, some of which
may later prove to be the same person. The diagram displays each identity once,
including people with multiple spouses or shared descendants. The viewer exposes source
links, identity uncertainty, and the available evidence modes. The local viewer
automatically rebuilds relationships when source edits make them stale, then
reloads and verifies the result, preserving the existing evidence views and
search configuration. A **Retry rebuild** button appears only if automatic
rebuilding fails. Restart an already running local server once after updating
the viewer to enable automatic rebuilding. The published read-only site links to the local
viewer when a rebuild is needed.

The registry and generated tree schemas are documented in [rules/json-formats.md](rules/json-formats.md).
Matching uses an explicit log-odds model across all source identities.
`data/matching.json` holds its global parameters, also visible in the viewer.
Documents/images have source weight 1.0; books/notes 0.5; guesses receive an
additional factor of 0.45. Title evidence decays with time, scoped offices carry
more weight, and conflicting deaths impose a large penalty. Place/property
context, formal family relationships, and deterministic same-fact associates
contribute additional evidence. Informative prose-only actors can supply
context records without creating family edges. Confirmed IDs in textual facts
are recognized directly. A capped full-relative-name rarity adjustment uses
factual source frequencies; it is not a historical population estimate.
The diagram defaults to parent/child and spouse lines; **show kins** reveals
sibling and other kin lines as well. Children with the same recorded parents
share a branch. In the default view, married parents use only the identifiable
father's stem for shared children; both parent assertions remain in the evidence
panel and return when **show kins** is enabled. The initial merge threshold is 85%, with
competing-candidate and cluster checks. Estimates are **uncalibrated**, not
measured historical accuracy. The tree stores comparison probabilities, feature
contributions, rejected alternatives, and provenance; tree and person pages
explain them. Ordinary mentions do not prove life. Seal comparison remains
human work; no numerical-age model or automatic seal matching is introduced.

## Archives

Archive catalogs and related research portals are collected in [`data/notes/archives.md`](data/notes/archives.md).

### Landesarchiv images

Download missing cached document images with:

```text
python3 scripts/download_missing_document_images.py
```

To link a Landesarchiv permalink to its digitized pages:

```text
python3 scripts/download_landesarchiv.py \
  'https://www.landesarchiv-bw.de/plink/?f=4-1723539'
```

Use `--mode download` to cache the files locally, or `--image-dir SUBDIRECTORY`
to choose a subdirectory under `data/documents/`. Retain the archive source
signature and follow its usage terms.

### Bavarikon images

Parse image URLs from a Bavarikon object page with:

```text
python3 scripts/parse_bavarikon.py 'https://www.bavarikon.de/object/...'
```

The script handles Bavarikon's Anubis proof-of-work check directly and uses
only Python's standard library.

Add `--download` to cache discovered images under
`data/documents/img-temp/bavarikon/`.

## Search facts

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

## Search places mentioned in a person's facts

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
[`data/names.md`](data/names.md).

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

### English name review

Check English text in documents and books for personal names that use a known
name or place variation, or a non-standard `de` connector. The checker reports
the source location and a suggested normalized form; it does not edit files.

```text
python3 scripts/validate_english_names.py
python3 scripts/validate_english_names.py data/documents/1397-04-29.json
```

By default, it scans `data/documents/` and `data/books/`. Pass JSON files or
directories to check a specific selection.
