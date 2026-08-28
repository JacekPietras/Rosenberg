# Rosenberg Research Data

This repository contains digitized historical sources about the von Rosenberg family and related Franconian/Odenwald families. Source text, English translation, and extracted facts are kept together in JSON files.

## Layout

```text
data/
├── books/        # Structured source books (images in img/)
├── notes/        # Research notes displayed as a book-style collection (images in img/)
├── letters/      # Letters and documents (cached images in img/)
├── calendar.md   # Liturgical calendar and dated annotations
├── people.json   # People and relationships
├── names.md      # Historical name variants
└── places.json   # Historical place-name variants and coordinates
```

## Data JSON formats

Schemas and editing details for book, letter, people, and place JSON are in
[`rules/json-formats.md`](rules/json-formats.md). Read that file when working
with files under `data/`.

## Fact extraction

Rules for extracting, normalizing, reviewing, and verifying facts are in
[`rules/facts.md`](rules/facts.md). Read that file before changing any `facts`
array.

## Data model and workflow

Rosenberg is a static research dataset. Source documents and translations are stored together, with extracted facts beside the supporting text. There is no separate facts database, report directory, synchronization service, or processing script.

Letter JSON documents have a document-level `date` and an `entries` array. Each entry contains an archival or bibliographic `source`, the original `german` text, its `english` translation, and explicit, atomic `facts` supported by that entry. See [`rules/json-formats.md`](rules/json-formats.md) for the data schemas and [`rules/facts.md`](rules/facts.md) for extraction rules.

The editing workflow is deliberately direct: read the relevant JSON and source text, update the translation or facts in place, preserve source citations and date precision, then inspect the diff. A fact must be directly stated or unambiguously expressed in the source; do not infer relationships, identities, or dates.

Prioritize the von Rosenberg family and its documented network, including von Uissigheim and von Erligheim, their direct relatives, transaction partners, witnesses, offices, and relevant properties. Preserve German and Latin titles where they carry historical meaning, and use full names and epithets when needed to distinguish individuals. Exclude unrelated administrative detail and do not conflate Münch von Rosenberg with von Rosenberg.

## Browser viewer

The `docs/` directory contains a GitHub Pages (https://jacekpietras.github.io/Rosenberg/) browser viewer for the JSON dataset. It discovers books, notes, and letters directly from the repository tree, has separate tabs for each collection plus generated Seals and Tree tabs, and can show English alone or English alongside the original text. The Tree tab renders a family diagram directly from `data/people.json`. Original text is read from each entry's `german` or `latin` field. Publish the repository with GitHub Pages using `/docs` as the source.

The viewer checks for changed or new JSON documents every 30 seconds and refreshes the displayed data automatically. New or removed JSON documents are discovered automatically through GitHub.

For local testing, run `python3 docs/serve.py` from the repository root and open `http://localhost:8000/docs/`. The local server has no dependencies, provides the JSON file listing, and enables seal-annotation editing and soft image removal from the image lightbox. On GitHub Pages the viewer remains read-only. Removing an image marks its JSON node as deleted; it does not delete the underlying cached file.

## Downloading Landesarchiv images

For faster local viewing, download every remote image referenced by the letter JSON files that is not already in the local cache:

```text
python3 scripts/download_missing_letter_images.py
```

Cached files are stored in `data/letters/img/`, which is ignored by Git. The viewer uses a cached file locally when available and falls back to the original URL, so the published GitHub Pages site continues to work without the cache.

Use the dependency-free linker with a Landesarchiv permalink. It follows the catalogue page, discovers all digitized pages, and stores direct inline image URLs in the matching letter JSON entry:

```text
python3 scripts/download_landesarchiv.py \
  'https://www.landesarchiv-bw.de/plink/?f=4-1723539'
```

No local image files are created in the default `links` mode. The `img` nodes contain direct `bild.php` URLs hosted by Landesarchiv Baden-Württemberg. To download the files into `data/letters/img/` while retaining those public archive URLs in JSON, use:

```text
python3 scripts/download_landesarchiv.py \
  --mode download \
  'https://www.landesarchiv-bw.de/plink/?f=4-1723539'
```

Download mode caches the files locally but keeps the direct archive URLs in the JSON, so the published viewer continues to work when the gitignored cache is absent.

Use `--image-dir SUBDIRECTORY` to choose another subdirectory under `data/letters/`. Records without an available digitization produce an error. Check the archive's usage terms and retain the source signature when reusing displayed images.
