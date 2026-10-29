# Data JSON formats

Read this file when creating or editing JSON under `data/`. Preserve each
document's source text, English translation, extracted facts, citations, and
existing structure. Edit JSON directly; do not use a separate facts database.

## Facts JSON

Keep every fact in its existing source entry's `facts` array, alongside the
original text, translation, and citations. Arrays may contain typed objects,
legacy strings, and legacy `{date, text}` objects during migration. Use typed
objects for supported relationships, title attestations, and deaths; other relevant
facts may remain prose. A typed object has no duplicate `text`, `id`,
`evidence`, or `assessment` field. Its source is the containing entry.

The supported typed facts are:

| `type` | Required fields, in addition to `type` | Optional fields | Meaning |
| --- | --- | --- | --- |
| `parent` | `person`, `of` | `personTitle`, `ofTitle`, `personDeceased`, `ofDeceased`, `date` | `person` is a parent of `of`. |
| `sibling` | `person`, `of` | `personTitle`, `ofTitle`, `personDeceased`, `ofDeceased`, `date` | `person` is a sibling of `of`. |
| `spouse` | `person`, `of` | `personTitle`, `ofTitle`, `personDeceased`, `ofDeceased`, `date` | `person` is a spouse of `of`, including widowhood. |
| `kin` | `person`, `of`, `term` | `personTitle`, `ofTitle`, `personDeceased`, `ofDeceased`, `date` | Source-stated kinship without a more specific supported type. |
| `title` | `person`, `personTitle` | `personDeceased`, `date` | Source-stated designation of `person`. |
| `death` | `person`, exactly one of `diedOn` or `diedBefore` | `personTitle`, `date` | A person's death and its date or exclusive upper bound. |

Reject other types and fields. In particular, do not add `father`, `mother`,
`child`, `son`, `daughter`, `brother`, `sister`, `wife`, or `widow` types. Convert
“A is B's child” to `parent` with B in `person` and A in `of`. Do not add a
reverse fact. `kin.term` is a non-empty string preserving the source kinship
term, such as `Vetter`, without guessing its precise modern meaning.

An entry may also contain an optional `guesses` array alongside `facts` for
assumptions, inferences, and author interpretations. Use the same object
formats and historical dates as for facts: `{date, text}` for prose, and typed
objects for inferred family relationships and death dates. The containing
`guesses` array identifies these as uncertain; retain reasoning and attribution
in an accompanying dated prose guess when needed. Include a citation when the
containing entry does not identify the basis. Never invent a date: preserve
legacy undated strings when the historical date cannot be established, and
flag them for review. Book entries require an explicit historical date on
every fact and guess; `validate_facts.py` reports an undated book item as an
error. Do not invent a date to satisfy validation. Keep guesses separate from
source-supported facts.

`person` and `of` are non-empty strings: either a known `people.json` ID or a
normalized full name. Resolve an exact, case-sensitive ID match first;
otherwise treat the value as a name, without selecting a namesake's record.
Write IDs directly in these fields, without square brackets or separate
`personId`/`ofId` fields. Do not use nested person objects. IDs must be unique
and must not collide with full names. Preserve existing IDs; do not require
or invent one when identity is unresolved.

`personTitle` and `ofTitle`, when present, are non-empty arrays of unique,
non-empty strings. Put each designation in its own item, for example
`["der Jüngere", "Ritter", "zu Boxberg"]`; keep `Vogt zu Lauda` as one complete
item. Omit an absent title field instead of writing `null`, an empty array,
or a scalar string. Only record designations stated by this source. A `title`
fact requires `personTitle` and has no `of` or `ofTitle` fields.

`personDeceased` and `ofDeceased` are optional boolean fields identifying the
corresponding participant as deceased at the fact's historical date. Set a
field to `true` only when the source states that participant was deceased,
including when it identifies the other spouse as a widow or widower. Omit it
otherwise; absence does not mean the person was alive. Do not use `false` or
`null`. Use `ofDeceased` only on facts with an `of` participant. Do not put
`verstorben` or equivalent deceased status in a title array.

Facts are analyzed independently. A participant marked deceased may have
died before the fact's attestation; a mention at that date does not imply
that participant was alive. An unmarked mention alone also does not establish
that the participant was alive. A separate `death` fact can record a usable
death date or bound, but must not be required to interpret the status on a
relationship or title fact. For example, a spouse fact can stand alone:

```json
{
  "type": "spouse",
  "person": "Anne von Bebenburg",
  "of": "Eberhard von Rosenberg",
  "ofDeceased": true
}
```

### Death facts

Each `death` object has exactly one of `diedOn` or `diedBefore`. Its value is
a string containing a valid calendar date in `YYYY`, `YYYY-MM`, or
`YYYY-MM-DD` form. `diedOn` identifies the stated day, month, or year, without
inventing finer precision. `diedBefore` is an
exclusive upper bound at the start of that day, month, or year: `1394` means
before 1 January 1394. Convert “deceased by 1393” to `diedBefore` `1394` so
the whole of 1393 remains possible. Similarly, for an inclusive day or month,
use the start of the next day or month as the exclusive bound.

For “shortly after” a dated point, use `diedBefore` two calendar months after
that point as a standardized estimate, not a source-stated limit. When the
target month lacks the original day, use its last day. Preserve the original
source wording in the source text; put the estimated typed bound in `guesses`.
Do not add a prose fact or guess explaining the calculation. Do not treat the
estimated bound as a source-supported fact. Other approximations that cannot be expressed by
these types remain prose. Do not create a typed death fact without a usable
date or bound.

The top-level `date` is the historical date of the claim or attestation,
subject to the ordinary inheritance and book/note rules below. It is distinct
from `diedOn` and `diedBefore` and never supplies either implicitly. A death date itself
may be the historical date of a death event, but an attestation date must not
be mistaken for an exact death date. If an entry says someone was already
deceased, use the exclusive bound immediately after the attestation's date
or period when known. For an inherited interval, use the exclusive bound
immediately after its latest endpoint only when the attestation is known to
fall within that interval. Do not use an interval as `diedOn` or `diedBefore`.

Examples corresponding to death in a year and deceased by a year:

```json
[
  {"type": "death", "person": "Eberhard von Rosenberg", "date": "1314", "diedOn": "1314"},
  {"type": "death", "person": "vogt_zu_Lauda", "date": "1393", "diedBefore": "1394"}
]
```

For “Ulrich von Rosenberg died shortly after 22 February 1424”, a document
with an enclosing historical date can contain this guess:

```json
{"type": "death", "person": "Ulrich von Rosenberg", "diedBefore": "1424-04-22"}
```

The same format applies in `guesses`; the array identifies the claim as an
inference. The standardized two-month estimate requires no explanatory prose
guess. Retain legacy prose during migration. Store a stated cause, manner, or
place of death as a separate prose fact or guess when relevant.

Illustrative facts, not historical additions:

```json
[
  {
    "type": "parent",
    "person": "Example parent",
    "personTitle": ["Ritter"],
    "of": "Example child",
    "date": "1399"
  },
  {
    "type": "title",
    "person": "Example child",
    "personTitle": ["der Jüngere", "zu Boxberg"],
    "date": "1399-02-01"
  }
]
```

### Fact dates

Fact-level dates are valid calendar dates using only the source's precision:
`YYYY`, `YYYY-MM`, or `YYYY-MM-DD`. Never invent missing components. Use an
valid date when a date field is required. Null values are not accepted;
omit unnecessary optional fields instead of filling them with `null`.

In documents, an explicit fact date overrides the entry/document date.
Without it, inherit the nearest enclosing historical date, normally the
entry's date or the document-level date. Preserve existing inherited document intervals
(`YYYY-YYYY`, ISO endpoints separated by `/` or `--`) as intervals; do not
reduce them to a single day. A typed fact with neither a historical date to
inherit nor its own date must supply a valid historical date.

In books and notes, typed facts require their own `date` field, even if an
entry has a date. Never inherit a publication year. Book prose facts and all
book guesses use `{date, text}`; bare strings and objects without a date are
validation errors. Strict migration validation applies the same requirement
to notes. Dates record the historical event or attestation, not when
extraction occurred. A relationship attestation date is not its start date.

Validate facts from the repository root:

```text
python3 scripts/validate_facts.py
python3 scripts/validate_facts.py --strict-migration data/books data/notes
```

The existing validator may not yet recognize the death types; update it
before relying on it to validate newly added death objects. The validator
checks syntax, fields, dates, and registry references and reports
source locations. It does not verify historical support or identity, build
the graph, or detect ancestry cycles. An unmatched ID-like string is a review
warning, not a resolved person. Review source evidence and data diffs as well.

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

Book facts follow the shared Facts JSON rules above. Prose facts use
`{date, text}`; supported relationship, title, and death facts use typed objects with
an explicit historical `date`. Existing string facts remain supported during
migration.

## Document JSON

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

Documents have a document-level `date` and an `entries` array. Each entry
retains `source`, `german`, `english`, and `facts`. Its `facts` array follows
the shared Facts JSON rules above: typed facts and legacy prose may coexist,
and facts normally inherit the document date unless overridden.

The optional document-level `label` may be a string or an array of strings. Each
label is displayed as a red badge. The special label `"important"` gives the
document a reddish background; `"Hessen"`, `"Schenk"`, and `"Mönch"` give it a
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
`source` holds only references: URLs, or book citations with pages, figures,
or plates. Optional `description` holds all other information: identification,
transcriptions, translations, dating notes, photographer credits, licences, and
caveats.
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
`coverImage` selects a folder image for the collection card. Add `date`,
`label`, `source`, and `placeId` when they describe the
collection. Effigy collections may also include `sketchfabUrl`. Effigy
Sketchfab records use `title`, `id`, `url`, and optional `date` and `preview`
image URL. An optional `placeId` refers to the matching place ID in
`data/places.json`.

## People JSON

`data/people.json` is a JSON array. A person may have an `id`; when present, it
must be unique. Relationship fields may refer to another person by ID when
available, or by name when that person has no ID. IDs are optional and should
not be added solely to satisfy the format. Unknown dates and relationships are
`null` or empty arrays. Dates use ISO precision (`YYYY`, `YYYY-MM`, or
`YYYY-MM-DD`).

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
optional medieval place `category` may be `castle`, `church`, `city`, or
`village`; omit it when uncertain. Settlement categories describe status in
1387, not present-day municipal status.
Optional `showOnMap: false` excludes a place from all map views. Places are
shown by default.

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

### Settlement parents

A church or castle's optional `parent` contains the ID of its city or village
record. Reuse the correct settlement record. The referenced record must
exist, have category `city` or `village`, and have no parent of its own.
Establish the relationship from evidence or an explicit user identification,
not from similar names, shared coordinates, or a substring match. For example,
`burg-oberlauda` has `parent: "lauda"` while retaining the name `Burg Oberlauda`.

If the settlement is missing, research whether it was a city or village in
1387 before creating its record. Prefer municipal histories, official regional
gazetteers, and charter evidence. Distinguish town rights from market rights;
market rights alone do not establish city status. Record the supporting
evidence and source references with the settlement, and use settlement
coordinates rather than copying the building's coordinates without evidence.
If its identity or status cannot be established, leave it unresolved rather
than inventing a settlement or category.
For the current city/village schema, represent a documented market settlement
without town rights as `village` and explain its market status in the sourced
description. Do not invent a medieval village when the evidence describes
only a castle and its associated buildings. Bartenstein is such a case:
its settlement category is unset and its settlement marker is hidden, while
the castle has no settlement parent. Preserve both existing IDs:
`bartenstein` remains an unclassified, hidden record for existing ID URLs,
and `schloss-bartenstein` is the visible castle with variations
`["Bartenstein", "Schloss Bartenstein"]`. Bare historical mentions must
still match the castle in links and person maps. Check structured ID usages
before merging, removing, or reassigning any place record.

Once the settlement exists, reference it from the relevant buildings and
remove bare settlement names from those buildings' variations. For example,
create `niederstetten` as a `city` based on its privileges before 1387, then
use it as the parent of `niederstetten-friedhofskapelle` and
`niederstetten-st-jakobus`. The churches store their local building names;
the bare name `Niederstetten` belongs to the settlement. A settlement shared
by a church and castle must have one shared parent record: for example,
`waldmannshofen` is the village parent of both its church and castle. Move
bare historical settlement spellings to that parent as well.

### Names, combinations, and links

Use only `variations` to store recognized names, including local, full,
older, and punctuated forms. Do not add separate `aliases`, `nameFormat`, or
`mapLabel` fields. When a parent exists, omit redundant settlement names:
`uissigheim-st-laurentius` stores just `["St. Laurentius"]` with
`parent: "uissigheim"`. Do not store generated combinations or duplicate
building names for the parent's historical spellings. Existing explicit full
names such as `St. Kilian, Röttingen` remain supported by the loader, but
simplify redundant stored forms to `St. Kilian`. Similarly, store `Schloss`
with `parent: "waldmannshofen"`; its display name must be exactly
`Schloss Waldmannshofen`, never `Schloss Waldmannshofen Waldmannshofen`.

The loader matches the linked parent's listed spellings within each full
variation, case-insensitively at letter/digit boundaries, trying longer
spellings first. It removes that matched spelling, trims surrounding commas
and whitespace, and combines the remaining building name with only the first
parent variation (the settlement's canonical name) in both orders, separated
by a space. Other parent spellings may identify a settlement already present
in a stored building name, but must not generate additional combinations.
Preserve explicitly stored full building names, including historical forms,
and deduplicate the expanded names. If the first stored variation already
contains a parent spelling, it remains the canonical display name. Otherwise,
append the first parent variation to form the canonical name. For example,
`St. Laurentius` becomes `St. Laurentius Uissigheim`. Distinctive local names
remain recognized too. Generic building names (`Abbey`, `Monastery`, `Burg`,
`Schloss`, `Wasserschloss`, `Old Burg`, `Kirche`, `Evangelische Kirche`,
`Johanniskirche`, and `Friedhofskapelle`) are combined
with the parent but must not match on their own, which would incorrectly
link unrelated buildings or include them in fact and map searches.
Two building variations produce four unpunctuated combinations, regardless
of how many settlement variations exist. The settlement's other variations remain available for settlement
links and searches.

Also recognize a comma between the building and settlement, in either order,
without adding those combinations to the stored JSON. For example,
`Friedhofskapelle Niederstetten`, `Friedhofskapelle, Niederstetten`, and
`Niederstetten, Friedhofskapelle` must link to the same chapel as one phrase.
Allow variable whitespace around the comma and preserve the source text.
These punctuated forms must also work in old place URLs and mention searches.

If a variation contains no parent spelling at those boundaries, treat it as
a local building name and combine it with the canonical parent in both
orders, also retaining the local name. Do not strip a substring from a word:
`Lauda` does not match inside `Oberlauda`. Standalone names such as
`Reichelsburg` remain valid too.
`burg-oberlauda` intentionally resolves to `Burg Oberlauda Lauda`: Oberlauda
is part of the building's local name and Lauda is its confirmed parent.

Historical settlement spellings belong on the settlement. For example,
`Haldemarstetten`, `Zaltenbergstetten`, `Haltermannstetten`, and
`Haltenbergsketten` belong to `niederstetten`, not to the castle's local
variations. Keep the distinct proper building name `Schloss Haltenbergstetten`.

Use the same expanded variations for book/document hyperlinks, place-page
mentions, fact and person-map matching, and the Python place-listing and
fact-search tools. Match longer full names before shorter settlement names.
Place links use IDs when present so distinct places can share a display name.
Bare settlement names must resolve to the settlement rather than its church
or castle. Prefer a unique matching city/village. If the other matches have
no category, prefer the sole classified record, as for the Bartenstein castle
and retained unclassified record. Otherwise leave an ambiguous name unlinked
instead of selecting the first record. This matters for the two
different Essingen sites. Explicit ID URLs still select the requested record.
Place pages must also accept canonical names and all recognized variations
to preserve existing full-name URLs.

Map labels use the canonical name. For a building without a parent, put the
short settlement name first in `variations`, such as `Essingen`, and retain
the full building names as later variations. Apply this rule to both the
person-screen map and the main map, including all map modes. Resolve labels
from the stored canonical name; do not guess settlement names by splitting
building names at runtime. When a missing settlement is established, migrate
to the explicit parent relationship above.

During a migration, preserve existing place IDs, building coordinates,
categories, descriptions, source references, source text, and translations.
Retain distinctive building spellings in `variations`, simplifying redundant
settlement text; move bare settlement names to the parent where appropriate.
Verify that composed names contain the settlement only once, generic building
words do not create standalone matches, and shared settlements have one
parent for all their buildings. Verify valid JSON, unique
IDs, valid parent references, old name/ID URLs, both name orders using only the
first parent variation, and both map views. Keep browser and Python expansion behavior
consistent, and review the diff for unrelated changes.

## Editing requirements

Keep source, translation, and facts together in the same entry. Preserve valid
JSON, source citations, and date precision. Consult `data/names.md` before
normalizing personal names. For place-name variants, run
`python3 scripts/list_place_variations.py` from the project root (add
`--include-churches` when relevant). Read the matching `data/places.json`
record before adding or changing its variations. Do not merge similar people or
places without clear correspondence. Validate edited JSON and review the diff
manually.
