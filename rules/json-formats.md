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

Letter facts remain strings. Letter documents have a document-level `date`
and an `entries` array. Each entry retains `source`, `german`, `english`, and
`facts`; `facts` is an array of strings.

The optional letter-level `label` is displayed as a red badge. The special
label `"important"` gives the letter a reddish background; `"Hessen"`,
`"Schenk"`, and `"Mönch"` give it a dimmed background.

Each `img` item has a `src` URL and an optional `seals` array. Removed images
remain in the JSON with `"deleted": "true"`; the viewer hides them and image
import treats their `src` as already known. `position` is the comma-separated
normalized center (`x,y`, both from 0 to 1), and `size` is the seal diameter
as a fraction of the image height. Optional `width` is a normalized widening
modifier from `0` to `1`, `wideningRotation` sets its direction, and optional
`rotation` applies the seal's second, final rotation. The crop window remains
circular and unchanged. Use an empty `seals` array when an image has no
recorded annotations, or omit the field until annotations are available.

Each seal may have one `type`: `contrepalle`, `swans`, `helm`, or `full`.
The Seals tab's `unknown` filter shows seals whose type is not filled;
`unknown` is not an editable type.

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
    "variations": ["Uissigheim", "Ussigheim", "Ußinkeim"],
    "lat": 49.679167,
    "lon": 9.5725
  }
]
```

The viewer uses only the first variation as the canonical name for English
highlighting; historical variants remain available as data but are not
expanded at runtime.

## Editing requirements

Keep source, translation, and facts together in the same entry. Preserve valid
JSON, source citations, and date precision. Consult `data/names.md` and
`data/places.json` before normalizing names or places, and do not merge similar
people or places without clear correspondence. Validate edited JSON and review
the diff manually.
