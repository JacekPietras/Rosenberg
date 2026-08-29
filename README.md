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

## Browser viewer

The viewer is published at
<https://jacekpietras.github.io/Rosenberg/>. For local testing, run:

```text
python3 docs/serve.py
```

Then open <http://localhost:8000/docs/>. The local viewer supports seal
annotation editing and soft image removal; GitHub Pages is read-only.

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
