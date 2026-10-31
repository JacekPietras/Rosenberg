# Data JSON formats

Read this file when creating or editing JSON under `data/`. Preserve each document's source text,
English translation, extracted facts, citations, and existing structure. Edit JSON directly; do not
use a separate facts database.

## Facts JSON

Keep every fact in its existing source entry's `facts` array, alongside the original text,
translation, and citations. Arrays may contain typed objects, legacy strings, and legacy
`{date, text}` objects during migration. Use typed objects for supported relationships, title
attestations, and deaths; other relevant facts may remain prose. A typed object has no duplicate
`text`, `id`,
`evidence`, or `assessment` field. Its source is the containing entry.

The supported typed facts are:

| `type`    | Required fields, in addition to `type`            | Optional fields                                                  | Meaning                                                       |
|-----------|---------------------------------------------------|------------------------------------------------------------------|---------------------------------------------------------------|
| `parent`  | `person`, `of`                                    | `personTitle`, `ofTitle`, `personDeceased`, `ofDeceased`, `date` | `person` is a parent of `of`.                                 |
| `sibling` | `person`, `of`                                    | `personTitle`, `ofTitle`, `personDeceased`, `ofDeceased`, `date` | `person` is a sibling of `of`.                                |
| `spouse`  | `person`, `of`                                    | `personTitle`, `ofTitle`, `personDeceased`, `ofDeceased`, `date` | `person` is a spouse of `of`, including widowhood.            |
| `kin`     | `person`, `of`, `term`                            | `personTitle`, `ofTitle`, `personDeceased`, `ofDeceased`, `date` | Source-stated kinship without a more specific supported type. |
| `title`   | `person`, `personTitle`                           | `personDeceased`, `date`                                         | Source-stated designation of `person`.                        |
| `death`   | `person`, exactly one of `diedOn` or `diedBefore` | `personTitle`, `date`, `circumstances`                           | A person's death and its date or exclusive upper bound.       |

Reject other types and fields. In particular, do not add `father`, `mother`,
`child`, `son`, `daughter`, `brother`, `sister`, `wife`, or `widow` types. Convert “A is B's child”
to `parent` with B in `person` and A in `of`. Do not add a reverse fact. `kin.term` is a non-empty
string preserving the source kinship term, such as `Vetter`, without guessing its precise modern
meaning.

An entry may also contain an optional `guesses` array alongside `facts` for assumptions, inferences,
and author interpretations. Use the same object formats and historical dates as for facts:
`{date, text}` for prose, and typed objects for inferred family relationships and death dates. The
containing
`guesses` array identifies these as uncertain; retain reasoning and attribution in an accompanying
dated prose guess when needed. Include a citation when the containing entry does not identify the
basis. Never invent a date: preserve legacy undated strings when the historical date cannot be
established, and flag them for review. Book entries require an explicit historical date on every
fact and guess; `validate_facts.py` reports an undated book item as an error. Do not invent a date
to satisfy validation. Keep guesses separate from source-supported facts.

`person` and `of` are non-empty strings: either a known `people.json` ID or a normalized full name.
Resolve an exact, case-sensitive ID match first; otherwise treat the value as a name, without
selecting a namesake's record. Write IDs directly in these fields, without square brackets or
separate
`personId`/`ofId` fields. Do not use nested person objects. IDs must be unique and must not collide
with full names. Preserve existing IDs; do not require or invent one when identity is unresolved.

`personTitle` and `ofTitle`, when present, are non-empty arrays of unique, non-empty strings. Put
each designation in its own item, for example
`["der Jüngere", "Ritter", "zu Boxberg"]`; keep `Vogt zu Lauda` as one complete item. Omit an absent
title field instead of writing `null`, an empty array, or a scalar string. Only record designations
stated by this source. A `title`
fact requires `personTitle` and has no `of` or `ofTitle` fields.

`personDeceased` and `ofDeceased` are optional boolean fields identifying the corresponding
participant as deceased at the fact's historical date. Set a field to `true` only when the source
states that participant was deceased, including when it identifies the other spouse as a widow or
widower. Omit it otherwise. Do not use `false` or
`null`. Use `ofDeceased` only on facts with an `of` participant. Do not put
`verstorben` or equivalent deceased status in a title array.

Facts are analyzed independently. A participant marked deceased may have died before the fact's
attestation; a mention at that date does not imply that participant was alive. An unmarked
participant is treated as alive at the fact's historical date, so a missing marker can separate a
dead person from later records. A separate `death` fact can record a
usable death date or bound, but must not be required to interpret the status on a relationship or
title fact. For example, a spouse fact can stand alone:

```json
{
  "type": "spouse",
  "person": "Anne von Bebenburg",
  "of": "Eberhard von Rosenberg",
  "ofDeceased": true
}
```

### Death facts

Each `death` object has exactly one of `diedOn` or `diedBefore`. Its value is a string containing a
valid calendar date in `YYYY`, `YYYY-MM`, or
`YYYY-MM-DD` form. `diedOn` identifies the stated day, month, or year, without inventing finer
precision. `diedBefore` is an exclusive upper bound at the start of that day, month, or year: `1394`
means before 1 January 1394. Convert “deceased by 1393” to `diedBefore` `1394` so the whole of 1393
remains possible. Similarly, for an inclusive day or month, use the start of the next day or month
as the exclusive bound. Optional `circumstances` is a non-empty string recording relevant
circumstances of the death, such as its cause, manner, or place. Omit it when unknown or not
relevant; do not use it to duplicate the death date or bound.

For “shortly after” a dated point, use `diedBefore` two calendar months after that point as a
standardized estimate, not a source-stated limit. When the target month lacks the original day, use
its last day. Preserve the original source wording in the source text; put the estimated typed bound
in `guesses`. Do not add a prose fact or guess explaining the calculation. Do not treat the
estimated bound as a source-supported fact. Other approximations that cannot be expressed by these
types remain prose. Do not create a typed death fact without a usable date or bound.

The top-level `date` is the historical date of the claim or attestation, subject to the ordinary
inheritance and book/note rules below. It is distinct from `diedOn` and `diedBefore` and never
supplies either implicitly. A death date itself may be the historical date of a death event, but an
attestation date must not be mistaken for an exact death date. If an entry says someone was already
deceased, use the exclusive bound immediately after the attestation's date or period when known. For
an inherited interval, use the exclusive bound immediately after its latest endpoint only when the
attestation is known to fall within that interval. Do not use an interval as `diedOn` or
`diedBefore`.

Examples corresponding to death in a year and deceased by a year:

```json
[
  {
    "type": "death",
    "person": "Eberhard von Rosenberg",
    "date": "1314",
    "diedOn": "1314"
  },
  {
    "type": "death",
    "person": "vogt_zu_Lauda",
    "date": "1393",
    "diedBefore": "1394"
  }
]
```

For “Ulrich von Rosenberg died shortly after 22 February 1424”, a document with an enclosing
historical date can contain this guess:

```json
{
  "type": "death",
  "person": "Ulrich von Rosenberg",
  "diedBefore": "1424-04-22"
}
```

The same format applies in `guesses`; the array identifies the claim as an inference. The
standardized two-month estimate requires no explanatory prose guess. Retain legacy prose during
migration. Store a stated cause, manner, or place of death as a separate prose fact or guess when
relevant.

Illustrative facts, not historical additions:

```json
[
  {
    "type": "parent",
    "person": "Example parent",
    "personTitle": [
      "Ritter"
    ],
    "of": "Example child",
    "date": "1399"
  },
  {
    "type": "title",
    "person": "Example child",
    "personTitle": [
      "der Jüngere",
      "zu Boxberg"
    ],
    "date": "1399-02-01"
  }
]
```

### Fact dates

Fact-level dates are valid calendar dates using only the source's precision:
`YYYY`, `YYYY-MM`, or `YYYY-MM-DD`. Never invent missing components. Use an valid date when a date
field is required. Null values are not accepted; omit unnecessary optional fields instead of filling
them with `null`.

In documents, an explicit fact date overrides the entry/document date. Without it, inherit the
nearest enclosing historical date, normally the entry's date or the document-level date. Preserve
existing inherited document intervals (`YYYY-YYYY`, ISO endpoints separated by `/` or `--`) as
intervals; do not reduce them to a single day. A typed fact with neither a historical date to
inherit nor its own date must supply a valid historical date. Omit a fact-level `date` when it
repeats the enclosing document or entry date; the fact inherits that date. Keep an explicit date
only when it records a different historical date, such as a death date stated in the document.

In books and notes, typed facts require their own `date` field, even if an entry has a date. Never
inherit a publication year. Book prose facts and all book guesses use `{date, text}`; bare strings
and objects without a date are validation errors. Strict migration validation applies the same
requirement to notes. Dates record the historical event or attestation, not when extraction
occurred. A relationship attestation date is not its start date.

Validate facts from the repository root:

```text
python3 scripts/validate_facts.py
python3 scripts/validate_facts.py --strict-migration data/books data/notes
```

The existing validator may not yet recognize the death types; update it before relying on it to
validate newly added death objects. The validator checks syntax, fields, dates, and registry
references and reports source locations. It does not verify historical support or identity, build
the graph, or detect ancestry cycles. An unmatched ID-like string is a review warning, not a
resolved person. Review source evidence and data diffs as well.

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
`{date, text}`; supported relationship, title, and death facts use typed objects with an explicit
historical `date`. Existing string facts remain supported during migration.

## Document JSON

```json
{
  "date": "1399-02-01",
  "label": [
    "Schenk",
    "important"
  ],
  "place": "Boxberg",
  "entries": [
    {
      "source": "43 Nr. 5290",
      "url": "http://...",
      "german": "Original text",
      "english": "English translation",
      "facts": [
        "An explicit, atomic historical fact"
      ],
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
        {
          "src": "https://.../second-page.jpg",
          "seals": []
        }
      ]
    }
  ]
}
```

Documents have a document-level `date` and an `entries` array. Each entry retains `source`,`german`,
`english`, and `facts`. Its `facts` array follows the shared Facts JSON rules above: typed facts and
legacy prose may coexist, and facts normally inherit the document date unless overridden.

The optional document-level `label` may be a string or an array of strings. Each label is displayed
as a red badge. The special label `"important"` gives the document a reddish background; `"Hessen"`,
`"Schenk"`, and `"Mönch"` give it a dimmed background.

Each `img` item has a `src` URL and an optional `seals` array. Removed images remain in the JSON
with `"deleted": "true"`; the viewer hides them and image import treats their `src` as already
known. `position` is the comma-separated normalized center (`x,y`, both from 0 to 1), and `size` is
the seal diameter as a fraction of the image height. Optional `width` is a normalized widening
modifier from `0` to `1`, `wideningRotation` sets its direction, and optional
`rotation` applies the seal's second, final rotation. The crop window remains circular and
unchanged. Use an empty `seals` array when an image has no recorded annotations, or omit the field
until annotations are available. Optional image-level `tags` is an array of strings. Optional
`regions` is an array of named rectangles with a `name` and normalized `x`, `y`, `width`, and
`height` values from 0 to 1. The viewer displays regions as labeled outlines. When no separate
preview `focus` exists, the first region supplies the preview focus coordinates.

Each seal may have one `type`: `contrepalle`, `swans`, `helm`, or `full`. The Seals tab's `unknown`
filter shows seals whose type is not filled;
`unknown` is not an editable type.

## Images JSON

`data/images/images.json` is an object with a `title` and an `entries`
array. An entry's optional `label` is a string or an array of strings, such as
`"effigy"` or `["effigy", "new"]`. Each label is displayed separately and can be used to filter the
Images view. Preserve the `armorial` or `effigy` label when adding review labels such as `new`.
Armorial entries may include a `title`, `date`, `folio`, `source`, and `url`. The `title` contains
the armorial name and additional details only. Store dates as `YYYY` or
`YYYY-YYYY`, and store the optional folio separately without a `fol.` prefix. The viewer displays
the date in brackets after the title; it does not add the folio to the displayed title. `url` is the
image URL or local filename. The displayed title supplies the image's accessible name. Optional
`tags` is an array of strings used to filter the Images view.
`source` holds only references: URLs, or book citations with pages, figures, or plates. Optional
`description` holds all other information: identification, transcriptions, translations, dating
notes, photographer credits, licences, and caveats. Optional `regions` is an array of named
rectangular image areas. Each region has a `name` and normalized `x`, `y`, `width`, and `height`
values from 0 to 1. Regions are displayed as labeled outlines and can be added or renamed in the
local image viewer. The first region supplies the preview framing. If an image is stored locally,
place it directly in `data/images/` and reference its filename in `img`. The viewer also accepts
Google Drive thumbnail URLs in `img` for images that remain hosted in Drive.

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

For all image records, including effigies and Drive collections, keep dates out of `title` and store
them separately in `date` as `YYYY` or `YYYY-YYYY`. The viewer appends the date in brackets during
display. Legacy `year` fields are accepted as a display fallback. A Drive collection is one image
entry with
`type: "link"`, `title`, and `url` set to the Drive folder URL. The folder contents are the
collection; keep its member image files in that Drive folder and do not add a separate image entry
or `img` array for each member. Optional
`coverImage` selects a folder image for the collection card. Add `date`,
`label`, `source`, and `placeId` when they describe the collection. Effigy collections may also
include `sketchfabUrl`. Effigy Sketchfab records use `title`, `id`, `url`, and optional `date` and
`preview`
image URL. An optional `placeId` refers to the matching place ID in
`data/places.json`.

## People JSON

`data/people.json` is the manually curated registry of confirmed, separate
people. It is a non-empty array containing **only** `id` and `name` on each
record. Both are non-empty strings; IDs are unique and case-sensitive and must
not collide with any full name. Different people can have the same full name.
Preserve confirmed IDs and names. Inclusion in this registry is a reviewed
identity decision; reconstruction must never add provisional people to it.

```json
[
  {"id": "example_person", "name": "Example person"},
  {"id": "another_person", "name": "Another person"}
]
```

Do not store relationships, titles, biographies, matching results, provenance,
input fingerprints, build metadata, or configuration here. Source assertions
remain in their source JSON. All computed results belong in `data/tree.json`.
Rebuilding the tree must leave the registry byte-for-byte unchanged.

## Tree JSON

`data/tree.json` is the generated family graph, separate from the confirmed
registry. Generate it with `python3 scripts/rebuild_family_tree.py --apply`;
The normal CLI computes a facts-only audit and an independently built weighted
facts-and-guesses view; guesses are always included in the normal viewer.
`--facts-only` is an explicit audit command.
Without `--apply` the CLI is read-only. The local viewer also rebuilds stale or
missing trees and offers a retry action only when rebuilding fails. The tree is output, never input
identity evidence, and must not be included in its own input fingerprints.

The top-level object has:

- `schema: 4`, `engine: "5"`, `policy: "4"`.
- `configuration.searchLimit`: the positive integer bound for the retained registry diagnostics.
- `configuration.probability`: the effective model settings from `data/matching.json`,
  including model/calibration status, source and guess weights, prior, merge
  threshold, ambiguity margin, feature weights, temporal decay, and iteration limits.
- `views`: exactly `["facts"]` or `["facts", "with-guesses"]`, including empty
  or identical views.
- `inputs`: repository-relative input path to SHA-256 fingerprint, covering
  recursively discovered source JSON in books/documents/notes/images,
  `data/names.md`, `data/titles.md`, `data/places.json`, `data/matching.json`, the confirmed ID/name registry, and
  engine/shared Python utilities.
- `fingerprint`: the fingerprint of the complete `inputs` object.
- `evidence`: a graph keyed by each available evidence view.
- `matchingBackground`: per-view factual full-name counts and their weighted
  total, used for capped relative-name specificity. Source factors apply and
  guesses are excluded. Totals and values are validated.
- `coverage`: counts per view for `reconstructedPeople`,
  `reconstructedRelationships`, `contextualLinks`, `registryRelationships`,
  `unresolvedMentions` from registry diagnostics, `candidateComparisons`,
  `contextCoverage`, and `conflicts`. Context coverage counts attached,
  unattached, undated, explicit-ID, context-only, and family-linked occurrences.

### Source people and relationships

Each evidence view contains `sources`, `nodes`, `relationships`, and
`comparisons`. Schema 4 readers continue to accept earlier viewer artifacts for
migration, but new exports use schema 4. The
`sources` array stores each path/pointer/fingerprint reference once. Persisted
`mentions[].source`, `identitySources[]`, and derivation `sources[]` contain
zero-based integer indexes into that table; comparison `sources[]` use the same
indexes. Readers expand them for inspection.
Complete reference objects are also accepted in an uncompressed view.

A source reference has exactly `path`, `pointer`, and `fingerprint`. `path` is a
source JSON path, `pointer` is a zero-based RFC 6901 JSON Pointer ending in
`/facts/N` or `/guesses/N`, and `fingerprint` identifies that original assertion.
References remain attached to their original source entry; do not relocate a
stale pointer by searching for another identical assertion.

A node contains `key`, `name`, `titles`, `dates`, `status`, `mentions`, and
`identitySources`, and `identityProbability`. A registry-backed node also contains `registry`, equal to its
confirmed ID and node key. Other nodes use an opaque `@evidence/` handle derived
from their source occurrences. These are generated view handles, not permanent
person IDs, and can change when new evidence changes a grouping.

`status` is `anchored`, `contextual`, or `source`. Contextual nodes are inferred
identity clusters; source nodes can still correspond to another node elsewhere.
Counts describe source identities, not a proven count of distinct people.
Each mention contains `source`, `field`, and its resolved historical `date`.
Typed occurrences use `field: "person"` or `"of"`. Textual context occurrences
use `field: "text"` and a `reference` containing a literal name from the fact
or a confirmed ID explicitly present as `[id]`. The reference must be supported
by the original fact text. A context ID cannot override a different fixed
anchor. Occurrence uniqueness includes the text reference; several named actors
in one fact are distinct occurrences, not duplicate assignments. An occurrence belongs to only one node per view. Source
references supporting grouping remain in `identitySources`. Titles and dates
summarize attestations.

Relationships contain `type`, `person`, `of`, `derivations`, and `term` for kin.
Types are directed `parent`, and symmetric `spouse`, `sibling`, and `kin`.
Endpoints are node keys. Kin terms preserve the source's wording, such as
`Vetter`, without inventing a precise modern relationship. Marriage does not
supply another parent; siblings do not supply parents or transitive siblings.
No self-relationships or directed ancestry cycles are accepted. Repeated
ancestry through different branches is allowed. Attestation dates are not
relationship start dates.

Each derivation contains `identity`, `usesGuesses`, and `sources`; its containing
view supplies the evidence mode. Identity is `anchored`, `reviewed`, `inferred`,
or `source` (correspondence to other occurrences remains open). `usesGuesses`
covers assertion content and all identity dependencies, including negative
constraints and earlier contextual links. Guesses references require this flag,
and it is always false in the facts view. Every relationship must have a source
assertion whose participant assignments match its endpoints. Equivalent edges
retain alternative complete derivations; each view is validated separately.

### Reconstruction and verification

Repeated participant references in one dated source passage are grouped into
the fewest people that source distinctions and graph constraints jointly allow;
occurrences are merged only when every such grouping puts them together.
Siblings share a generation and a parent is one generation above a child, so a
person cannot be both parent and sibling of the same person. Cross-source matching
uses a weighted log-odds model for all source people, including those without
registry IDs. For compatible-name candidates:

```text
logOdds = log(prior / (1 - prior)) + sum(feature contributions)
probability = 1 / (1 + exp(-logOdds))
```

All title categories decay with the distance between their actual attestation
intervals. Elder → younger age titles and Ritter → Edelknecht are penalized; the
reverse progressions are neutral. Different age titles of one name in one
passage are different people. Titles are compared by meaning, using the
equivalents in `data/titles.md` and place variants in `places.json`: an office is
its office word and place, regardless of prefix or connector (`Vogt zu Lauda` =
`Vogt in Lauda` = `erzbischöflicher Voigt zu Lauda`); `genannt X`, `called von X`,
`dictus de X`, `von X`, and `zu X` are one designation of X. Different offices with
the same place, or an office and a bare place designation, supply the weaker
territory weight once. Cross-role place support uses
`crossRolePlaceFactor`. Scoped offices have stronger weights than ranks. Property associations
use names/variations from `places.json`. Same-fact associates are deterministic
`XXX von YYY` name co-occurrences; an entire entry is never one associate group.
Dated prose binds exact bracketed IDs directly. Ordinary names select a unique
local participant using overlapping date intervals. Informative prose-only
occurrences can form provisional context profiles and bridge typed family
identities, but never create family edges or standalone disconnected family
cards. Repeated normalized names in a fact remain ambiguous. Context occurrences
retain source text references rather than being rewritten as typed facts.

Family evidence uses exact anchors, already linked relatives, full relative
names, and co-parent context without creating extra edges, scaled by relation
type (parent/child and spouse above sibling above other kin). Same-named
siblings, parents, or children of the same identified person receive the
stronger `sharedRelativeWeight`. A merge that leaves a person with two
same-named parents who cannot be one person (distinct confirmed IDs or a
chronology block) is blocked. Features are capped
by category/relative/place; repeated extraction does not manufacture support.
Document/image source factors are always 1.0; book/note factors are 0.5.
Guesses receive an additional 0.45 factor by default. Pairwise evidence uses the
weaker of the two observations' effective factors.

A typed mention without a deceased marker means the person was alive at the
fact's date. A death fact or deceased marker supplies a death bound. Each
identity has an estimated birth interval: a rank, office, `der Ältere`/`der
Alte`, parent, or spouse requires adulthood (`adultAgeYears`), and every
unmarked mention or exact death requires an age of at most `maxAgeYears`. Partial
dates are read permissively. A mention after death, incompatible death dates,
or an impossible age blocks a merge when both records are document/image facts;
otherwise it contributes `-deathConflictPenalty × pair reliability`. A merge
that raises the minimum implied age above `ageComfortYears` contributes
`-(minimum age - ageComfortYears) / ageScaleYears × pair reliability`; time
distance alone is neutral. Participants of one relationship fact, separate
confirmed IDs, self-relationships, and ancestry cycles block merges. Blocked
comparisons have status `incompatible` and a reason starting with `blocked:`.
A confirmed ID whose own document facts conflict is reported for review and is
not reassigned.

The configuration defines the compatible-name prior (initially 0.05), merge
threshold (0.85), reciprocal log-odds margin, age assumptions, cluster checks,
and maximum rounds. Capped full-relative-name frequency adjustments use the frozen
factual `matchingBackground`, add-one smoothing, and configurable rarity weight,
maximum, and reference frequency. This is source representation, not population
frequency. Matching runs against frozen profiles; whole candidate
components and connected source families are checked jointly. Inferred links
carry their dependencies and confidence into later rounds. Only accepted links
reduce cluster confidence; rejected internal pairs do not. Same-named repeated
parents are not co-parent evidence. Omitted surnames require family or identifying
title support, and co-parent support retains child-identity provenance. The algorithm's own
conclusions are not independent evidence. No seal-image matching is used. These probabilities are **uncalibrated estimates**.

Each comparison contains `person`, `candidate` (final node keys), original
`mentions` handles, `iteration`, `probability`, `logOdds`, `features` (named
log-odds contributions), `sources`, `usesGuesses`, `status`, and `reason`. Status
is `merged`, `below-threshold`, `ambiguous`, `incompatible`, or `superseded`.
The latter preserves an earlier comparison when later cluster evidence joined
its occurrences. Name/time-only candidates with no substantive additional
signal are not persisted. References and probability arithmetic are validated.

A node's `identityProbability` is the weakest accepted model link supporting its
cluster, or 1 for an exact/local occurrence grouping. It is not a probability
that the historical person existed or that the identity is permanently confirmed.
Derivations also retain `assertionWeight` and `endpointProbability`; the latter
is null when correspondence remains open. Assertion weights are evidence
factors, not calibrated probabilities of relationship truth.

Input fingerprints cover complete parsed source files, including enclosing dates,
citations, text, and newly added assertions; a separate source file-set check
catches added and removed files. The registry fingerprint covers only confirmed
IDs and names. Generated tree data is excluded, so applying an identical build
is deterministic and does not invalidate itself.

Fingerprint encoding is shared by Python and JavaScript. Recursively encode
objects as `["object", [[key, encodedValue], ...]]` with sorted keys, arrays as
`["array", [encodedValue, ...]]`, and numbers as `["number", "<big-endian
IEEE-754 binary64 hexadecimal>"]`. Strings, booleans, and null remain unchanged.
Normalize negative zero to zero. Serialize this tagged value as compact ASCII JSON (non-ASCII code points use
lowercase `\u` escapes, including UTF-16 surrogate pairs), then hash its UTF-8
bytes with SHA-256 and prefix `sha256:`. Object key order and insignificant JSON
whitespace do not affect a fingerprint; semantic input changes do.

Before displaying generated relationships, the viewer verifies the input set,
input fingerprints, source pointers and hashes, participant assignments, and
graph consistency. A stale or missing local tree triggers the Python rebuild
and a verified reload. The browser does not duplicate the matching algorithm.

`--apply` validates the complete tree in memory, rechecks source inputs, registry
bytes, and existing tree bytes, and writes `tree.json` once. It never modifies
`people.json` or source assertions. Intervening changes prevent a write. No
timestamps, reports, review queues, or separate facts database are introduced.

## Matching JSON

`data/matching.json` is the authoritative global configuration for the weighted
identity model. It contains `model: "weighted-log-odds-v3"`, `calibrated: false`,
`priorProbability`, `mergeProbability`, `ambiguityLogOddsMargin`,
`clusterMinimumProbability`, `guessWeight`, `sourceWeights`, age assumptions
(`adultAgeYears`, `maxAgeYears`, `ageComfortYears`, `ageScaleYears`), title
weights and half-lives, place weights and half-life, cross-role place factor,
relative-name rarity weight/cap/reference frequency, associate
weights/cap/half-life, family weights, relation factors, shared-relative weight,
cap and half-life,
elder-before-younger and Ritter-before-Edelknecht penalties, death conflict
penalty, and `maxRounds`.

Use the existing file's exact keys; unknown/missing keys, non-finite or
non-positive values, invalid probability ranges, and non-integer iteration
bounds are rejected. The agreed source factors are documents/images 1.0 and
books/notes 0.5; these values are enforced. Guesses must have a factor strictly
between 0 and 1. Other values are configurable model assumptions. Parameter
changes invalidate generated results and automatically rebuild the local tree.
The viewer shows every effective value from the generated configuration.


## Places JSON

`data/places.json` is an array of place objects. Each object's `variations`
array starts with the canonical English name, followed by recognized historical spelling variants.
`lat` and `lon` are decimal-degree WGS84 coordinates. An optional medieval place `category` may be
`castle`, `church`, `city`, or
`village`; omit it when uncertain. Settlement categories describe status in 1387, not present-day
municipal status. Optional `showOnMap: false` excludes a place from all map views. Places are shown
by default.

```json
[
  {
    "id": "uissigheim",
    "variations": [
      "Uissigheim",
      "Ussigheim",
      "Ußinkeim"
    ],
    "lat": 49.679167,
    "lon": 9.5725
  }
]
```

The viewer uses the first variation as the canonical name for display. All listed variations are
used when finding and linking related place content.

### Settlement parents

A church or castle's optional `parent` contains the ID of its city or village record. Reuse the
correct settlement record. The referenced record must exist, have category `city` or `village`, and
have no parent of its own. Establish the relationship from evidence or an explicit user
identification, not from similar names, shared coordinates, or a substring match. For example,
`burg-oberlauda` has `parent: "lauda"` while retaining the name `Burg Oberlauda`.

If the settlement is missing, research whether it was a city or village in 1387 before creating its
record. Prefer municipal histories, official regional gazetteers, and charter evidence. Distinguish
town rights from market rights; market rights alone do not establish city status. Record the
supporting evidence and source references with the settlement, and use settlement coordinates rather
than copying the building's coordinates without evidence. If its identity or status cannot be
established, leave it unresolved rather than inventing a settlement or category. For the current
city/village schema, represent a documented market settlement without town rights as `village` and
explain its market status in the sourced description. Do not invent a medieval village when the
evidence describes only a castle and its associated buildings. Bartenstein is such a case:
its settlement category is unset and its settlement marker is hidden, while the castle has no
settlement parent. Preserve both existing IDs:
`bartenstein` remains an unclassified, hidden record for existing ID URLs, and `schloss-bartenstein`
is the visible castle with variations
`["Bartenstein", "Schloss Bartenstein"]`. Bare historical mentions must still match the castle in
links and person maps. Check structured ID usages before merging, removing, or reassigning any place
record.

Once the settlement exists, reference it from the relevant buildings and remove bare settlement
names from those buildings' variations. For example, create `niederstetten` as a `city` based on its
privileges before 1387, then use it as the parent of `niederstetten-friedhofskapelle` and
`niederstetten-st-jakobus`. The churches store their local building names; the bare name
`Niederstetten` belongs to the settlement. A settlement shared by a church and castle must have one
shared parent record: for example,
`waldmannshofen` is the village parent of both its church and castle. Move bare historical
settlement spellings to that parent as well.

### Names, combinations, and links

Use only `variations` to store recognized names, including local, full, older, and punctuated forms.
Do not add separate `aliases`, `nameFormat`, or
`mapLabel` fields. When a parent exists, omit redundant settlement names:
`uissigheim-st-laurentius` stores just `["St. Laurentius"]` with
`parent: "uissigheim"`. Do not store generated combinations or duplicate building names for the
parent's historical spellings. Existing explicit full names such as `St. Kilian, Röttingen` remain
supported by the loader, but simplify redundant stored forms to `St. Kilian`. Similarly, store
`Schloss`
with `parent: "waldmannshofen"`; its display name must be exactly
`Schloss Waldmannshofen`, never `Schloss Waldmannshofen Waldmannshofen`.

The loader matches the linked parent's listed spellings within each full variation,
case-insensitively at letter/digit boundaries, trying longer spellings first. It removes that
matched spelling, trims surrounding commas and whitespace, and combines the remaining building name
with only the first parent variation (the settlement's canonical name) in both orders, separated by
a space. Other parent spellings may identify a settlement already present in a stored building name,
but must not generate additional combinations. Preserve explicitly stored full building names,
including historical forms, and deduplicate the expanded names. If the first stored variation
already contains a parent spelling, it remains the canonical display name. Otherwise, append the
first parent variation to form the canonical name. For example,
`St. Laurentius` becomes `St. Laurentius Uissigheim`. Distinctive local names remain recognized too.
Generic building names (`Abbey`, `Monastery`, `Burg`,
`Schloss`, `Wasserschloss`, `Old Burg`, `Kirche`, `Evangelische Kirche`,
`Johanniskirche`, and `Friedhofskapelle`) are combined with the parent but must not match on their
own, which would incorrectly link unrelated buildings or include them in fact and map searches. Two
building variations produce four unpunctuated combinations, regardless of how many settlement
variations exist. The settlement's other variations remain available for settlement links and
searches.

Also recognize a comma between the building and settlement, in either order, without adding those
combinations to the stored JSON. For example,
`Friedhofskapelle Niederstetten`, `Friedhofskapelle, Niederstetten`, and
`Niederstetten, Friedhofskapelle` must link to the same chapel as one phrase. Allow variable
whitespace around the comma and preserve the source text. These punctuated forms must also work in
old place URLs and mention searches.

If a variation contains no parent spelling at those boundaries, treat it as a local building name
and combine it with the canonical parent in both orders, also retaining the local name. Do not strip
a substring from a word:
`Lauda` does not match inside `Oberlauda`. Standalone names such as
`Reichelsburg` remain valid too.
`burg-oberlauda` intentionally resolves to `Burg Oberlauda Lauda`: Oberlauda is part of the
building's local name and Lauda is its confirmed parent.

Historical settlement spellings belong on the settlement. For example,
`Haldemarstetten`, `Zaltenbergstetten`, `Haltermannstetten`, and
`Haltenbergsketten` belong to `niederstetten`, not to the castle's local variations. Keep the
distinct proper building name `Schloss Haltenbergstetten`.

Use the same expanded variations for book/document hyperlinks, place-page mentions, fact and
person-map matching, and the Python place-listing and fact-search tools. Match longer full names
before shorter settlement names. Place links use IDs when present so distinct places can share a
display name. Bare settlement names must resolve to the settlement rather than its church or castle.
Prefer a unique matching city/village. If the other matches have no category, prefer the sole
classified record, as for the Bartenstein castle and retained unclassified record. Otherwise leave
an ambiguous name unlinked instead of selecting the first record. This matters for the two different
Essingen sites. Explicit ID URLs still select the requested record. Place pages must also accept
canonical names and all recognized variations to preserve existing full-name URLs.

Map labels use the canonical name. For a building without a parent, put the short settlement name
first in `variations`, such as `Essingen`, and retain the full building names as later variations.
Apply this rule to both the person-screen map and the main map, including all map modes. Resolve
labels from the stored canonical name; do not guess settlement names by splitting building names at
runtime. When a missing settlement is established, migrate to the explicit parent relationship
above.

During a migration, preserve existing place IDs, building coordinates, categories, descriptions,
source references, source text, and translations. Retain distinctive building spellings in
`variations`, simplifying redundant settlement text; move bare settlement names to the parent where
appropriate. Verify that composed names contain the settlement only once, generic building words do
not create standalone matches, and shared settlements have one parent for all their buildings.
Verify valid JSON, unique IDs, valid parent references, old name/ID URLs, both name orders using
only the first parent variation, and both map views. Keep browser and Python expansion behavior
consistent, and review the diff for unrelated changes.

## Editing requirements

Keep source, translation, and facts together in the same entry. Preserve valid JSON, source
citations, and date precision. Consult `data/names.md` before normalizing personal names. For
place-name variants, run
`python3 scripts/list_place_variations.py` from the project root (add
`--include-churches` when relevant). Read the matching `data/places.json`
record before adding or changing its variations. Do not merge similar people or places without clear
correspondence. Validate edited JSON and review the diff manually.
