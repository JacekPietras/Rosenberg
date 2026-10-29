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
├── people.json   # People and relationships
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
