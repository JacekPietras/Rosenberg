# Data JSON formats

Read this file when creating or editing JSON under `data/`. Edit the JSON
directly, preserve its existing structure, and validate it afterwards.

## Facts and guesses

Facts and guesses are typed objects in an entry's `facts` and optional
`guesses` arrays; the containing entry is their source. Guesses use exactly the
same formats; the `guesses` array marks them as uncertain.

| `type` | Required | Optional | Meaning |
| --- | --- | --- | --- |
| `generic` | `person` or `subject` (exactly one), `content` | `personTitle`, `personDeceased`, `date` | One atomic claim about a person or a non-person subject |
| `parent` | `person`, `of` | `personTitle`, `ofTitle`, `personDeceased`, `ofDeceased`, `date` | `person` is a parent of `of` |
| `sibling` | `person`, `of` | as `parent` | `person` is a sibling of `of` |
| `spouse` | `person`, `of` | as `parent` | `person` is a spouse of `of`, including widowhood |
| `kin` | `person`, `of`, `term` | as `parent` | Other kinship; `term` is the source's word (`Vetter`) |
| `title` | `person`, `personTitle` | `personDeceased`, `date` | A designation of `person` |
| `death` | `person`, `diedOn` or `diedBefore` (exactly one) | `personTitle`, `date`, `circumstances` | A death and its date or exclusive upper bound |

Other types (`father`, `child`, `widow` …) and fields (`text`, `id`,
`evidence`, `assessment`) are rejected. A child is recorded as `parent` with the
parent in `person`; relationships are stored once, without reverse copies.

### Fields

- `person`, `of`: a non-empty string, either an exact `people.json` ID
  (case-sensitive) or a normalized full name. No brackets, nested objects, or
  separate ID fields.
- `personTitle`, `ofTitle`: a non-empty array of unique strings, one
  designation per item: `["der Jüngere", "Ritter", "zu Boxberg"]`; `Vogt zu
  Lauda` is one item. Omit the field when there is no title. Never put a
  deceased status in it.
- `personDeceased`, `ofDeceased`: `true` when the participant was dead by the
  fact's date; otherwise omitted (never `false`). An unmarked participant was
  alive then. `ofDeceased` only on facts with `of`.
- `subject` (generic only): a literal description of a family, place,
  institution, object, or unidentified figure; never a person ID or invented
  name, and never combined with `personTitle` or `personDeceased`.
- `content` (generic only): an English continuation starting with the
  predicate, without the subject's name or titles, so that `<name> <titles>
  <content>` reads as one sentence: `Arnold von Rosenberg, Ritter, zu Boxberg
  witnessed the agreement at Boxberg.` Generic objects have no `of`, `ofTitle`,
  or `ofDeceased`.
- `null` is never used; omit absent optional fields.

Each fact is self-contained: a spouse fact with `ofDeceased` needs no separate
death fact.

```json
{"type": "spouse", "person": "Anne von Bebenburg", "of": "Eberhard von Rosenberg", "ofDeceased": true}
```

### Dates

A date is `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`, at the source's precision. It is
the date of the event or attestation, never a publication date, and not the
start of a relationship.

- **Documents**: facts inherit the entry or document date, including intervals
  (`YYYY-YYYY`, ISO endpoints joined by `/` or `--`), which stay intervals.
  Facts of any type have their own `date` when it differs from the inherited
  date. A fact without an enclosing date needs its own.
- **Books and notes**: every fact and guess has its own `date`.

### Deaths

- `diedOn`: the stated day, month, or year.
- `diedBefore`: an exclusive bound at the start of that day, month, or year:
  "dead by 1393" is `diedBefore: "1394"`; "dead by 3 May 1393" is
  `"1393-05-04"`. Never an interval.
- The fact's `date` is the attestation, distinct from `diedOn`/`diedBefore`
  and never supplying them. "Already dead" at an attestation gives the bound
  just after that date or period; for an inherited interval only when the
  attestation lies within it.
- "Shortly after" a date is the guess `diedBefore` two calendar months later
  (the month's last day if that day does not exist), without an explanatory
  guess. Other approximations are `generic` guesses.
- `circumstances`: cause, manner, or place of death; omitted when unknown.
- A death fact needs a usable date or bound.

```json
[
  {"type": "death", "person": "Eberhard von Rosenberg", "date": "1314", "diedOn": "1314"},
  {"type": "death", "person": "vogt_zu_Lauda", "date": "1393", "diedBefore": "1394"}
]
```

### Validation

```text
python3 scripts/lint.py
```

It checks syntax, fields, dates, and registry references, not historical
support. An ID-like string that matches no ID is a warning.

## Entry text fields

| Field | Content |
| --- | --- |
| `german`, `latin` | Original document text when available; otherwise the German archival abstract when no full transcription is available |
| `english` | Normalized English translation of the original text, or English translation of the German abstract when the original is not transcribed; when a transcribed entry has `summary`, that summary may inform and enrich the English rendering with relevant context |
| `subheading` | Optional lower-level heading displayed within the current entry or book section |
| `summary` | The abstract provided by the archive webpage, retained only when the document is transcribed (`transcribed: true`) |

The `abstract` field must never be used. Do not put an archive-provided
abstract in `german` or `latin` when a full transcription is available; keep it
in `summary` instead. When no full transcription is available, put the German
abstract in `german` or `latin` and its normalized English translation in
`english`; omit `summary` unless the document is marked transcribed.

In `english`, translate and normalize the text for clear, readable English. For
transcribed documents, base the translation on the original `german` or `latin`
text. The archive-provided `summary` may also be used as contextual evidence to
clarify implicit references or include relevant information omitted from the
transcription, making the English account more informative. Keep a clear
distinction between the document's wording and context supplied by the summary;
do not imply that summary-only details were stated in the document, and do not
add claims unsupported by the source text and summary together. The `summary`
field itself remains unchanged. When no full transcription is available,
`english` remains a normalized translation of the German abstract in `german`
or `latin`.
Do not repeat source-language spelling variants or editorial parentheses that
are already preserved in `german` or `latin` (for example, translate
`Handschuhsheim (Hentschus-)` as `Handschuhsheim`). Preserve meaningful names,
titles, and distinctions in the translation; this rule removes redundant
spelling notes, not historical content.

In book and document text, wrap a passage in single backticks to display its
Latin letters as Unicode Fraktur, for example `` `Ebirhardus` `` renders as
“𝔈𝔟𝔦𝔯𝔥𝔞𝔯𝔡𝔲𝔰”. The stored text keeps the backticks as the marker; digits,
punctuation, and spaces inside the passage remain unchanged.

For structured family lists, indent nested lines and start each item with `+`
to display it as a connected tree. Use `*` or `-` for ordinary nested bullet
lists.

## Book and notes JSON

```json
{
  "book": "Bauer [1872]",
  "entries": [
    {
      "title": "Section or source title",
      "subheading": "Optional heading within the section",
      "german": "Original German text",
      "english": "English translation",
      "facts": [{"date": "1399-02-01", "type": "generic", "person": "Example person", "content": "witnessed the agreement at Boxberg."}],
      "diagram": "Optional diagram data"
    }
  ]
}
```

## Document JSON

```json
{
  "label": ["Schenk", "important"],
  "date": "1399-02-01",
  "place": "Boxberg",
  "transcribed": true,
  "entries": [
    {
      "source": ["43 Nr. 5290", "Regest Nr. 123"],
      "url": ["http://...", "https://example.org/document"],
      "german": "Original text",
      "english": "English translation",
      "facts": [{"type": "generic", "person": "Example person", "content": "witnessed the agreement at Boxberg."}],
      "img": [{"src": "https://.../page.jpg", "seals": [{"person": "Eberhard", "position": "0.3,0.8", "size": 0.05, "type": "full"}]}]
    }
  ]
}
```

- `date` (required): the document's historical date. `place`: place of issue.
- `transcribed`: `true` when transcribed; absent or `false` otherwise.
- `deleted`: `true` hides the whole document from the Documents screen while retaining its JSON.
- `label`: a string or array of strings, shown as badges. `important` gives a
  reddish background.
- Entries keep `source` (the citation) and `url` as either a string or an array
  of strings, when there is one reference/link or several; they also keep their
  text fields and `facts`.
- `img[]`: `src`; `deleted: true` for a removed image (kept so it is not
  imported again); optional `tags`, and `regions` (named rectangles with
  normalized `x`, `y`, `width`, `height` from 0 to 1; the first gives the
  preview focus when there is no `focus`).
- `seals[]` (empty or omitted when not annotated): `position` is the normalized
  center `x,y`, `size` the diameter as a fraction of the image height; optional
  `width` (widening, 0–1), `wideningRotation`, `rotation`, and `type`
  (`contrepalle`, `swans`, `helm`, `full`).

## Images JSON

`data/images/images.json` is `{"title": …, "entries": […]}`.

```json
{"title": "Family arms", "date": "1370-1414", "folio": "332v", "label": "armorial", "source": "Source citation", "url": "family-arms.png"}
```

- `title`: the image or armorial name, without date or folio.
- `date`: `YYYY` or `YYYY-YYYY` (legacy `year` is still read). `folio` without
  a `fol.` prefix; `page` is a string giving a page number or a labeled viewer
  page identifier (such as `Internet Archive leaf n885`).
- `label`: a string or array (`armorial`, `effigy`, review labels such as
  `new`); keep `armorial`/`effigy` when adding review labels. `tags`: filters.
- `url`: an image URL, a Google Drive thumbnail URL, or the filename of an image
  stored directly in `data/images/`.
- `source`: only references (URLs, citations with pages, figures, plates).
  `description`: everything else (identification, transcription, credits,
  licences, caveats).
- `regions`: as for documents; the first gives the preview framing.
- `placeId`: an ID from `data/places.json`.
- A Drive collection is one entry with `type: "link"`, `title`, and `url` set
  to the folder; its images stay in the folder, without separate entries.
  Optional `coverImage`, `date`, `label`, `source`, `placeId`, and, for
  effigies, `sketchfabUrl`.
- An effigy Sketchfab record has `title`, `id`, `url`, and optional `date` and
  `preview`.

## People JSON

`data/people.json` is the curated registry of confirmed, separate people: a
non-empty array of objects with **only** `id` and `name`. IDs are unique,
case-sensitive, and never equal to a full name; different people may share a
name. Only reviewed people are added, and generated files never change it.

```json
[{"id": "example_person", "name": "Example person"}]
```

## Tree JSON

`data/tree.json` is generated by `python3 scripts/rebuild_family_tree.py
--apply` and never edited by hand. `--apply` validates the whole tree and
writes it once, as compact JSON; input changes during the build prevent the write.
It keeps only `merged` and `ambiguous` comparisons. The complete tree, with every
comparison, goes to the gitignored `.cache/tree-debug.json` for
`print_graph_connections.py`; that file is optional and ignored when its
`fingerprint` differs.

| Key | Content |
| --- | --- |
| `configuration` | `searchLimit`, the bound for registry diagnostics |
| `inputs` | Path → fingerprint for every source JSON in books/documents/notes/images, `data/names.md`, `nobiliary_particles.md`, `name-connectors.md`, `titles-age.md`, `titles-office.md`, `kinship.md`, `places.json`, `matching.json`, `distinctFamilies.md`, and the registry (IDs and names only). Scripts and the tree itself are not inputs. |
| `fingerprint` | Fingerprint of `inputs` |
| `evidence` | Graph per view (`with-guesses`) |
| `matchingBackground` | Per view, factual full-name counts and their weighted total |
| `coverage` | Per view: `reconstructedPeople`, `reconstructedRelationships`, `contextualLinks`, `registryRelationships`, `unresolvedMentions`, `candidateComparisons` (all comparisons, including those only in the debug cache), `contextCoverage`, `conflicts` |

A graph has `sources`, `nodes`, `relationships`, and `comparisons` (only `merged` and `ambiguous` in `data/tree.json`).

**Sources.** `sources` lists each reference once; elsewhere references are
integer indexes into it (full objects are also accepted). A reference has
exactly `path`, `pointer` (RFC 6901, ending in `/facts/N`, `/guesses/N`, or a
document entry's `/english` field), and `fingerprint` of the referenced
assertion or text value. A stale pointer is never relocated to another
identical assertion. English-text references are contextual evidence and do
not support relationship assertions.

**Nodes.** `key`, `name`, `titles`, `dates`, `status`, `identityProbability`,
`mentions`, `identitySources`, optional `possiblySame`.

- `key`: the registry ID for a registry person (also in `registry`), otherwise
  a generated `@evidence/…` handle that can change between builds.
- `status`: `anchored` (registry person), `contextual` (several passages), or
  `source` (one passage).
- `mentions[]`: `source`, `field` (`person`, `of`, or `text`), and the resolved
  `date`. A `text` mention also has `reference`: a literal name recognized in
  its fact text or document English field, or an `[id]` present in the text.
  Each occurrence belongs to one node.
- `identityProbability`: 0–1, the lowest membership confidence of the
  mentions; 1 for a registry person or a grouping within one source.
- `possiblySame`: `[{key, probability}]`, tied or likely candidates not chosen.

**Relationships.** `type` (directed `parent`; symmetric `spouse`, `sibling`,
`kin`), `person`, `of` (node keys), `term` for `kin`, and `derivations`. No
self-relationships or ancestry cycles; repeated ancestry through different
branches is allowed. Each derivation has:

- `identity`: `anchored`, `reviewed`, `inferred`, or `source` (correspondence
  still open);
- `usesGuesses`: whether the assertion or any identity it depends on uses
  guesses;
- `assertionWeight`, `endpointProbability` (`null` while correspondence is
  open), and `sources`;
- `inference: "sibling"` for a father taken from a sibling; its sources are the
  parent assertion to sibling X and the sibling assertion between X and `of`.
  Any other derivation has a source assertion whose participants match its
  endpoints.

**Comparisons.** `person`, `candidate` (node keys), `mentions`, `stage` (3 or
4), `iteration`, `probability`, `logOdds`, `features` (named log-odds
contributions), `sources`, `usesGuesses`, `status`, `reason`, and, at stage 4,
`share`. `status` is `merged`, `below-threshold`, `ambiguous`, `incompatible`
(reason starting `blocked:` when blocked), or `superseded` (an earlier
comparison of occurrences joined later).

Probabilities and weights are uncalibrated estimates.

### Fingerprints

Fingerprints cover the complete parsed file (dates, citations, text,
assertions), plus a check of the source file set. Encoding, shared by Python and
JavaScript: objects become `["object", [[key, value], …]]` with sorted keys,
arrays `["array", [value, …]]`, numbers `["number", "<big-endian IEEE-754
binary64 hex>"]` (negative zero as zero); strings, booleans, and null stay as
they are. Serialize as compact ASCII JSON (lowercase `\u` escapes, UTF-16
surrogate pairs), hash the UTF-8 bytes with SHA-256, and prefix `sha256:`.

## Matching JSON

`data/matching.json` holds the reconstruction parameters, with exactly the keys
of the existing file: `model` (`weighted-log-odds-v6`), `calibrated` (`false`),
probabilities and margins, `guessWeight`, `sourceWeights`, age assumptions,
title, place, associate and family weights and half-lives, penalties,
`maxRounds`, `bestCandidate`, and `secondPass`.

Missing or unknown keys, non-positive or non-finite numbers, probabilities
outside 0–1, and non-integer counts are rejected. `sourceWeights` must be
documents/images 1.0 and books/notes 0.5; `guessWeight` lies strictly between 0
and 1.

## Places JSON

`data/places.json` is an array of places.

```json
[{"id": "uissigheim", "variations": ["Uissigheim", "Ussigheim", "Ußinkeim"], "lat": 49.679167, "lon": 9.5725, "category": "village"}]
```

| Field | Content |
| --- | --- |
| `id` | Unique, stable ID; check its uses before merging, removing, or reassigning a place |
| `variations` | Canonical English name first, then historical spellings; the only place for names (no `aliases`, `nameFormat`, `mapLabel`) |
| `lat`, `lon` | WGS84 decimal degrees |
| `category` | `castle`, `church`, `city`, or `village`, as in 1387; omitted when uncertain |
| `parent` | For a church or castle: the ID of its city or village |
| `description` | Sourced notes, including the evidence for a settlement's status |
| `showOnMap` | `false` hides the place on all maps |

### Parents and names

- A `parent` must exist, be a `city` or `village`, and have no parent itself.
  Set it from evidence or an explicit user identification, never from similar
  names, coordinates, or substrings. All buildings of one settlement share one
  parent record.
- A building with a parent stores only its local names (`["St. Laurentius"]`);
  the displayed name adds the parent's first variation (`St. Laurentius
  Uissigheim`). Settlement spellings belong to the settlement, not to its
  buildings.
- Generic building names (`Abbey`, `Monastery`, `Burg`, `Schloss`,
  `Wasserschloss`, `Old Burg`, `Kirche`, `Evangelische Kirche`,
  `Johanniskirche`, `Friedhofskapelle`) only match together with their parent.
- A building without a parent lists the short settlement name first
  (`Essingen`), then its full names.

### Creating a settlement

Before creating a missing settlement, establish whether it was a city or village
in 1387 from municipal histories, official gazetteers, or charters. Market
rights alone make a `village`; explain them in `description`. Use the
settlement's own coordinates. Do not invent a village where the evidence shows
only a castle: `bartenstein` stays an unclassified, hidden record, and
`schloss-bartenstein` is the visible castle with `["Bartenstein", "Schloss
Bartenstein"]` and no parent.

When moving buildings under a new parent, keep their IDs, coordinates,
categories, descriptions, and sources, and move bare settlement names to the
parent.

## Archive search existence checks

`data/archive_search/ARCHIVE.json` stores verified catalogue search results for
reuse and publication. `archive` is the archive search script identifier;
`queries` maps each exact query string to a Boolean indicating whether the
archive returned any results. A negative result describes the catalogue search
at the time it was checked; it is not a historical fact or proof that a person
is absent from the archive. The archive search scripts write entries immediately after a confirmed result.
