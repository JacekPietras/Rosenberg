# Rosenberg Research Data

Digitized historical sources about the von Rosenberg family and related
Franconian/Odenwald families. Source text, English translation, and extracted
facts are kept together in the JSON data.

## Repository layout

```text
data/
├── books/        # Structured source books
├── notes/        # Research notes
├── letters/      # Letters, document
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
JSON under `data/`. It describes the book, letter, people, and places formats.

Read [`rules/facts.md`](rules/facts.md) before adding, changing, reviewing, or
removing facts. It covers extraction, relevance, normalization, and source
verification.

Keep edits targeted. Preserve valid JSON, source citations, source text,
translations, existing structure, and the source's date precision.

## Agent skills

Codex discovers repository skills under `.agents/skills/`. The archival catalog
research workflow is [`archive-name-research`](.agents/skills/archive-name-research/SKILL.md).
Repository-wide instructions are in [`AGENTS.md`](AGENTS.md).

## Browser viewer

The viewer is published at
<https://jacekpietras.github.io/Rosenberg/>. For local testing, run:

```text
./server
```

The command opens <http://localhost:8000/docs/> in your browser. The local
viewer supports seal annotation editing, image tags and named regions, and soft
image removal. Its header has a local-only button to restart the server and
reload the viewer; GitHub Pages is read-only.

## Landesarchiv images

Download missing cached letter images with:

```text
python3 scripts/download_missing_letter_images.py
```

To link a Landesarchiv permalink to its digitized pages:

```text
python3 scripts/download_landesarchiv.py \
  'https://www.landesarchiv-bw.de/plink/?f=4-1723539'
```

Use `--mode download` to cache the files locally, or `--image-dir SUBDIRECTORY`
to choose a subdirectory under `data/letters/`. Retain the archive source
signature and follow its usage terms.

## Bavarikon images

Parse image URLs from a Bavarikon object page with:

```text
python3 scripts/parse_bavarikon.py 'https://www.bavarikon.de/object/...'
```

The script handles Bavarikon's Anubis proof-of-work check directly and uses
only Python's standard library.

Add `--download` to cache discovered images under
`data/letters/img-temp/bavarikon/`.
