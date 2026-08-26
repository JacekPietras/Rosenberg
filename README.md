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

## Book JSON

```json
{
  "book": "Bauer [1872]",
  "entries": [
    {
      "title": "Section or source title",
      "german": "Original German text",
      "english": "English translation",
      "facts": [
        {
          "date": "1399-02-01",
          "text": "An explicit, atomic historical fact"
        }
      ],
      "diagram": "Optional diagram data"
    }
  ]
}
```

## Letter JSON

```json
{
  "date": "1399-02-01",
  "label": "Schenk",
  "place": "Boxberg",
  "entries": [
    {
      "source": "43 Nr. 5290",
      "url": "http://...",
      "german": "Original text",
      "english": "English translation",
      "facts": ["An explicit, atomic historical fact"],
      "img": [
        {
          "src": "https://.../first-page.jpg",
          "seals": [
            {
              "person": "Eberhard",
              "position": "0.3,0.8",
              "size": 0.05,
              "type": "full"
            }
          ]
        },
        { "src": "https://.../second-page.jpg", "seals": [] }
      ]
    }
  ]
}
```

The optional letter-level `label` is displayed as a red badge in the upper-right of the letter heading. The special label `"important"` gives the letter a reddish background; `"Hessen"`, `"Schenk"`, and `"Mönch"` give it a dimmed background.

Each `img` item is an image node with a `src` URL and an optional `seals` array for annotations on that image. Removed images remain in the JSON with `"deleted": "true"`; the viewer hides them and image import treats their `src` as already known. `position` is the comma-separated normalized center (`x,y`, both from 0 to 1), and `size` is the seal diameter as a fraction of the image height. Optional `width` is a normalized widening modifier from `0` (unchanged) to `1` (maximum widening), `wideningRotation` sets the direction of that widening, and optional `rotation` applies the seal’s second, final rotation. The crop window remains circular and unchanged. The viewer draws the seal and the person’s name beside it. Use an empty array when an image has no recorded seal annotations, or omit the field until annotations are available.

Each seal may have one `type`: `contrepalle`, `swans`, `helm`, or `full`. It can be edited with the local lightbox editor, and the Seals tab can filter by one type at a time. The Seals tab’s `unknown` filter shows seals whose type is not filled; `unknown` is not an editable type.

## Working with the data

To update a document, edit its JSON directly and preserve valid JSON, the existing source text, and the translation. Extract facts only from the document itself. Keep facts concise, atomic, explicit, and in English, while preserving historically meaningful German titles, names, and place names.

Book facts are objects with a `date` and `text` field. The `date` must use ISO precision (`YYYY`, `YYYY-MM`, or `YYYY-MM-DD`) supported by the source; never invent missing date components. Letter facts remain strings as shown in the Letter JSON format above.

`data/people.json` is a JSON array. Each person has a unique `id`; relationship
fields refer to other people by ID. Unknown dates and relationships are `null`
or empty arrays. Dates use ISO precision (`YYYY`, `YYYY-MM`, or `YYYY-MM-DD`).

```json
[
  {
    "id": "Example_person",
    "name": "Example person",
    "titles": ["Vogt zu Lauda", "Ritter"],
    "wife": "Example_spouse",
    "children": ["Example_child"],
    "born": "1300",
    "died": "1360-04"
  },
  {
    "id": "Example_spouse",
    "name": "Example spouse",
    "titles": [],
    "wife": null,
    "children": [],
    "born": null,
    "died": null
  },
  {
    "id": "Example_child",
    "name": "Example child",
    "titles": [],
    "wife": null,
    "children": [],
    "born": null,
    "died": null
  }
]
```

Use underscores in IDs instead of spaces, and preserve distinguishing titles or
territorial designations in both `name` and `titles` when they identify a
particular historical person.

Use `data/names.md` and `data/places.json` when a spelling needs to be recognized or normalized. Do not merge people merely because their names are similar. In particular, do not conflate Münch von Rosenberg with the primary von Rosenberg family.

`data/places.json` is an array of place objects. Each object has a `variations`
array whose first item is the canonical name and whose remaining items are
recognized spelling variants, plus `lat` and `lon` GPS coordinates in decimal
degrees (WGS84):

```json
[
  {
    "variations": ["Uissigheim", "Ussigheim", "Ußinkeim"],
    "lat": 49.679167,
    "lon": 9.5725
  }
]
```

The viewer derives its existing canonical `name` and variant `names` values
from `variations`, so the name-matching behavior remains unchanged.

Before committing, validate the edited JSON with any available JSON-aware editor or validator and review the diff manually.

## Data model and workflow

Rosenberg is a static research dataset. Source documents and translations are stored together, with extracted facts beside the supporting text. There is no separate facts database, report directory, synchronization service, or processing script.

Letter JSON documents have a document-level `date` and an `entries` array. Each entry contains an archival or bibliographic `source`, the original `german` text, its `english` translation, and explicit, atomic `facts` supported by that entry.

The editing workflow is deliberately direct: read the relevant JSON and source text, update the translation or facts in place, preserve source citations and date precision, then inspect the diff. A fact must be directly stated or unambiguously expressed in the source; do not infer relationships, identities, or dates.

Prioritize the von Rosenberg family and its documented network, including von Uissigheim and von Erligheim, their direct relatives, transaction partners, witnesses, offices, and relevant properties. Preserve German and Latin titles where they carry historical meaning, and use full names and epithets when needed to distinguish individuals. Exclude unrelated administrative detail and do not conflate Münch von Rosenberg with von Rosenberg.

## Browser viewer

The `docs/` directory contains a GitHub Pages (https://jacekpietras.github.io/Rosenberg/) browser viewer for the JSON dataset. It discovers books, notes, and letters directly from the repository tree, has separate tabs for each collection plus generated Seals and Tree tabs, and can show English alone or English alongside the original text. The Tree tab renders a family diagram directly from `data/people.json`. Original text is read from each entry's `german` or `latin` field. Publish the repository with GitHub Pages using `/docs` as the source.

The viewer checks for changed or new JSON documents every 30 seconds and refreshes the displayed data automatically. New or removed JSON documents are discovered automatically through GitHub.

Publish the repository with GitHub Pages to use the viewer without running anything locally. The published site will be at the repository root URL.

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

Download mode caches the files locally but keeps the direct archive URLs in the
JSON, so the published viewer continues to work when the gitignored cache is
absent.

Use `--image-dir SUBDIRECTORY` to choose another subdirectory under `data/letters/`. Records without an available digitization produce an error. Check the archive's usage terms and retain the source signature when reusing displayed images.
