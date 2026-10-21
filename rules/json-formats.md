# Data JSON formats

Read this file when creating or editing JSON under `data/`. Preserve each
document's source text, English translation, extracted facts, citations, and
existing structure. Edit JSON directly; do not use a separate facts database.

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

Book facts are objects with `date` and `text` fields. The date must use only
the ISO precision supported by the source: `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`.
Never invent missing date components.

## Letter JSON

```json
{
  "date": "1399-02-01",
  "label": ["Schenk", "important"],
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

Letter facts remain strings. Letter documents have a document-level `date`
and an `entries` array. Each entry retains `source`, `german`, `english`, and
`facts`; `facts` is an array of strings.

The optional letter-level `label` may be a string or an array of strings. Each
label is displayed as a red badge. The special label `"important"` gives the
letter a reddish background; `"Hessen"`, `"Schenk"`, and `"Mönch"` give it a
dimmed background.

Each `img` item has a `src` URL and an optional `seals` array. Removed images
remain in the JSON with `"deleted": "true"`; the viewer hides them and image
import treats their `src` as already known. `position` is the comma-separated
normalized center (`x,y`, both from 0 to 1), and `size` is the seal diameter
as a fraction of the image height. Optional `width` is a normalized widening
modifier from `0` to `1`, `wideningRotation` sets its direction, and optional
`rotation` applies the seal's second, final rotation. The crop window remains
circular and unchanged. Use an empty `seals` array when an image has no
recorded annotations, or omit the field until annotations are available.
Optional image-level `tags` is an array of strings. Optional `regions` is an
array of named rectangles with a `name` and normalized `x`, `y`, `width`, and
`height` values from 0 to 1. The viewer displays regions as labeled outlines.
When no separate preview `focus` exists, the first region supplies the preview
focus coordinates.

Each seal may have one `type`: `contrepalle`, `swans`, `helm`, or `full`.
The Seals tab's `unknown` filter shows seals whose type is not filled;
`unknown` is not an editable type.

## Images JSON

`data/images/images.json` is an object with a `title` and an `entries`
array. An entry's optional `label` is a string or an array of strings, such as
`"effigy"` or `["effigy", "new"]`. Each label is displayed separately and can be
used to filter the Images view. Preserve the `armorial` or `effigy` label when
adding review labels such as `new`. Armorial entries may
include a `title`, `date`, `folio`, `source`, and `url`. The `title` contains
the armorial name and additional details only. Store dates as `YYYY` or
`YYYY-YYYY`, and store the optional folio separately without a `fol.` prefix.
The viewer displays the date in brackets after the title; it does not add the
folio to the displayed title. `url` is the image URL or local filename. The
displayed title supplies the image's accessible name.
Optional `tags` is an array of strings used to filter the Images view.
Optional `regions` is an array of named rectangular image areas. Each region
has a `name` and normalized `x`, `y`, `width`, and `height` values from 0 to 1.
Regions are displayed as labeled outlines and can be added or renamed in the
local image viewer. The first region supplies the preview framing.
If an image is stored locally, place it directly in `data/images/` and
reference its filename in `img`. The viewer also accepts Google Drive thumbnail
URLs in `img` for images that remain hosted in Drive.

```json
{
  "title": "Images",
  "entries": [
    {
      "title": "Family arms",
      "date": "1370-1414",
      "folio": "332v",
      "label": "armorial",
      "source": "Source citation",
      "url": "family-arms.png"
    }
  ]
}
```

For all image records, including effigies and Drive collections, keep dates
out of `title` and store them separately in `date` as `YYYY` or `YYYY-YYYY`.
The viewer appends the date in brackets during display. Legacy `year` fields
are accepted as a display fallback. A Drive collection is one image entry with
`type: "link"`, `title`, and `url` set to the Drive folder URL. The folder
contents are the collection; keep its member image files in that Drive folder
and do not add a separate image entry or `img` array for each member. Optional
`preview` or `coverImage` URLs can select a folder image for the collection
card. Add `date`, `label`, `source`, and `placeId` when they describe the
collection. Effigy collections may also include `sketchfabUrl`. Effigy
Sketchfab records use `title`, `id`, `url`, and optional `date` and `preview`
image URL. An optional `placeId` refers to the matching place ID in
`data/places.json`.

## People JSON

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
  }
]
```

Use underscores in IDs instead of spaces. Preserve distinguishing titles or
territorial designations in both `name` and `titles` when they identify a
particular historical person.

## Places JSON

`data/places.json` is an array of place objects. Each object's `variations`
array starts with the canonical English name, followed by recognized historical
spelling variants. `lat` and `lon` are decimal-degree WGS84 coordinates. An
optional medieval place `category` may be `castle`, `church`, or `city`; omit it
when uncertain.

```json
[
  {
    "id": "uissigheim",
    "variations": ["Uissigheim", "Ussigheim", "Ußinkeim"],
    "lat": 49.679167,
    "lon": 9.5725
  }
]
```

The viewer uses the first variation as the canonical name for display. All
listed variations are used when finding and linking related place content.

## Editing requirements

Keep source, translation, and facts together in the same entry. Preserve valid
JSON, source citations, and date precision. Consult `data/names.md` before
normalizing personal names. For place-name variants, run
`python3 scripts/list_place_variations.py` from the project root (add
`--include-churches` when relevant). Read the matching `data/places.json`
record before adding or changing its variations. Do not merge similar people or
places without clear correspondence. Validate edited JSON and review the diff
manually.
