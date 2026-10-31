# Fact extraction and verification

Read this file when adding, changing, reviewing, or removing `facts` in the
JSON documents under `data/`.

## Extraction

Read the complete document and its source text before adding facts. Extract
only information explicitly stated or unambiguously expressed in the source;
never infer, interpret, or extrapolate. The German source is authoritative when
it differs from the English translation. Facts must be concise, atomic,
explicit, and written in English, except for historically meaningful German or
Latin names, titles, places, and epithets. Make one assertion per fact. Keep
facts in the source entry; use the typed formats in `rules/json-formats.md`
for every fact and guess. Use `generic` with `person` and a simple, atomic
`content` continuation for claims outside the supported relationship, title, and death
types. Do not repeat the subject's name or titles in `content`; begin with the predicate
so the name, titles, and content read as one sentence. Optional `personTitle` and `personDeceased` describe the subject; dates
follow the shared rules. Untyped facts and guesses are not supported.

For claims about a family, place, institution, object, or an unidentified figure, use a
`generic` object with a non-person `subject` instead of `person`, as specified in
`rules/json-formats.md`. Preserve supported collective claims without inventing personal
identities. Do not use personal title or deceased-status fields on these objects.

Extract each explicitly stated family relationship as a separate typed fact:

- `parent`: `person` is a parent of `of`. Reverse the participants when the
  source says that someone is a child, son, or daughter of someone else.
- `sibling`: `person` is a sibling of `of`.
- `spouse`: `person` is a spouse of `of`, including a widow or widower.
- `kin`: explicit kinship not represented more precisely above; preserve the
  source's kinship term in `term` without guessing its degree.

Record each source-stated death, including a designation as deceased or late,
as a separate typed death fact when a usable date can be established, using the rules in
`rules/json-formats.md`. Distinguish the death date or bound from the date of
the attestation. When a source identifies someone as deceased at a known
date, record the corresponding `diedBefore` bound unless it supplies a more
precise claim. Never
infer an exact death date from widowhood or other context. Record a stated
cause or manner of death separately as a generic fact; do not lose it when
converting an existing death statement.

On each typed relationship, title, or generic fact, independently mark a participant
whom the source identifies as deceased using `personDeceased` or
`ofDeceased`, as applicable. A widow or widower designation establishes that
the other spouse is deceased, as do terms such as “late”, “selig”, or
“quondam”. Omit the field only when the source does not identify the
participant as dead: identity matching treats an unmarked participant as alive
at the fact's historical date. Do not
store `verstorben` or equivalent status in a title array. The separate death
fact and participant status serve different purposes: each fact must be
interpretable independently.

Never use grouped forms such as “Sons: A and B”. Do not infer relationships
from proximity, transactions, or shared names. Store a relationship once;
reverse navigation of parentage and symmetric navigation of spouse/sibling
edges are graph operations, not additional extracted source statements. Do
not infer parents from siblings, a second parent from a spouse, full
siblinghood from one shared parent, or sibling transitivity. Widowhood does
not supply an exact death or marriage date.

Use `person` and `of` as flat strings containing a known person ID or a
normalized full name. Use optional `personTitle` and `ofTitle` arrays for
source-stated designations, including age epithets and territorial scope.
Omit absent titles; do not fill them from `people.json` or another source.
A `title` fact uses `person` and a non-empty `personTitle` array, without `of`.
A designation already recorded on a relationship or generic fact need not be duplicated
as a separate title fact at the same date.

Preserve the source's distinction among `der Alte`, `der Ältere`, `der Junge`,
and `der Jüngere`; do not translate them as “the old/older/elder/young/younger.”
Expand abbreviations such as `d. Ä.` and `d. J.` in facts and English
translations; leave the source text as written. In typed facts, keep each
expanded epithet or territorial designation in the corresponding title array.
In generic facts, use `personTitle`; in translations, put it after the full name, as in
`Konrad von Rosenberg der Ältere` or `Arnold von Rosenberg zu Boxberg`.

Titles are dated attestations, not permanent identity properties. `der
Jüngere` can later become `der Ältere`, and `Edelknecht` can precede `Ritter`.
A first `Ritter` attestation does not date a knighting, and omission of a title
does not prove its absence. Do not infer uninterrupted title use or identity
from matching designations. Record a fact-level historical date when it
differs from the enclosing document date; typed book/note facts always need
an explicit valid date. Do not use `null`; omit unnecessary optional fields.
Never substitute a book's publication date for historical time.

Preserve German and Latin terminology when it carries historical meaning.
Examples include `Ritter`, `Edelmann`, `Edel`, `Edelknecht`, `Knecht`, `Vogt`,
`Hofmeister`, `Burggraf`, `Domherr`, `Vizedom`, `Vitztum`, `Komtur`, `miles`,
and `armiger`.

Keep these forms in typed title arrays when they function as personal titles
or designations. In generic facts, use `personTitle`. In English translations, place them after
the full name even if the German source puts them first: `Arnold von
Uissigheim, Ritter`; `Eberhard von Rosenberg, Vogt zu Dürn`. Retain the territorial or institutional scope. In a
list, attach the title to each person, for example, `Eberhard von Rosenberg,
Ritter; Johann von Randecke, Ritter`.

Translate the same term when it describes an office, action, or general
occupation rather than identifying a person's title: `Eberhard served as
bailiff of Dürn`; `Rudolf, a canon of Würzburg, renounced his inheritance`;
`Like every knight, Eberhard had armour`. Avoid hybrids such as `bailiff zu
Dürn` or `Canon zu Würzburg`. Keep family names intact (`von Uissigheim`, not
“of Uissigheim”) and distinguish titles from place descriptions such as
`pastor of Uissigheim`.

For property and transactions, state the people, property, place, and parties
involved. Relevant forms include:

- `X holds [asset] at [place]`
- `X sold [asset] at [place] to Y`
- `X donated [asset] to Y`
- `X exchanged [asset] for [asset]`
- `X held [asset] as a [type] fief from Y`
- `X inherited or received [asset] from Y`

Also extract relevant witnesses, arbitrators, sureties, and official duties.
Omit prices, financial amounts, measurements, and unrelated administrative
detail unless essential to identifying the event.

## Guesses and interpretations

An entry may also have a separate `guesses` array alongside `facts` for
assumptions, inferences, and interpretations, including interpretations read
in books or notes that are not claimed to come directly from a document. Keep
these out of `facts`. State uncertainty and the reasoning or attribution clearly,
and cite the book, note, or other basis when it is not already identified by
the containing entry. Do not present a guess as a document-supported fact or
use it to resolve an identity or relationship as certain.

Use the same typed object formats and historical date rules as facts for guesses,
including `generic` for other interpretations, and relationship and death objects
for inferred relationships and death dates. Keep `content` simple and atomic. Guesses must concern the same people and
subjects as relevant facts; do not use them for commentary on authors, sources,
or the research process. Retain citations needed to identify the basis of a guess.
Never invent a date or use the publication year as an event date. In books and
notes, every fact and guess must have an explicit historical date.

## Relevance and identity

Keep a fact when it mentions a member of von Rosenberg, von Uissigheim, or von
Erligheim; documents a direct relationship or interaction with those families;
or references Boxberg, Wölchingen, Uissigheim, Erligheim, Rosenberg, or
Bartenstein. Direct interactions include spouses, parents, children, siblings,
witnesses, sureties, arbitrators, transaction partners, and other direct
participants.

Remove facts only about unrelated nobility or clergy, unrelated administrative
activity, financial amounts or measurements, or third-party transactions with
no target-family participant. Keep relevant property and transaction facts even
when they are not genealogical.

`Münch von Rosenberg` is a distinct family. Never conflate it with the primary
von Rosenberg family or use its genealogy as evidence about von Rosenberg. A
Münch fact may remain when it explicitly documents a direct interaction with
the primary von Rosenberg family.

## Names and normalization

Consult `data/names.md` for personal names. For place-name variants, run
`python3 scripts/list_place_variations.py` from the project root; add
`--include-churches` when churches are relevant. Use the first form in a
variation entry as the standard only when the correspondence is clear. Read
the matching place record in `data/places.json` before adding or changing its
variations. Match spelling variants case-insensitively while
preserving the standard form's case.

Use normalized full names, with the given name followed by `von` and the
normalized family name (for example, `Konrad von Rosenberg`), rather than
source spelling variants when the correspondence is clear. In typed facts,
`person` and `of` accept either that name or an exact, case-sensitive existing
`people.json` ID. Write the ID directly in the field, without square brackets
or separate ID fields.

Only use an ID when the evidence identifies that person. An unresolved name
is not automatically linked to a registry record or the same name in another
entry. Preserve source distinctions in title arrays and flag remaining
ambiguity; do not require or invent IDs or titles merely to make a graph
complete. Do not merge people because they share a name, title, or location.

Normalize clear variants such as `Conradus` to `Konrad`, `Arnolt` to `Arnold`,
`Engelhart` to `Engelhard`, `Ussinkeim` to `Uissigheim`, and `Erlikeim` to
`Erligheim`. Preserve context such as `dictus`, `von`, `miles`, and `armiger`.
`Kunz`/`Cunz` are shortened forms of Konrad but must remain `Kunz` when used;
do not expand them automatically.

Never merge people or places solely because their names are similar. If
identity is ambiguous, preserve the source form and flag it for review. Do not
normalize away `der Ältere`, `der Jüngere`, `zu [place]`, titles, or other
identifiers. Keep age epithets in German, in title arrays for typed facts or
after the full name in translations (`<given name> von <surname> der
Alte/der Ältere/der Junge/der Jüngere`). Record legitimate
new variants for later addition to the relevant names or places file rather
than silently inventing a standard form.

## Source verification

For every generated fact, locate the exact supporting passage in the German
source. Check names, dates, titles, places, relationships, and similarly named
people. If the source is bilingual, verify both columns but treat the original
German as authoritative.

When reporting verification, include the fact, source entry, exact supporting
quote (or `NOT FOUND`), status, reasoning, and recommendation. A fact is:

- **supported** only when the source explicitly supports it;
- **partially supported** when the core claim is present but details need correction;
- **unsupported** when it cannot be located or requires inference;
- **contradicted** when it conflicts with the source.

Correct clear errors and remove unsupported or contradicted facts. Never infer
kinship from proximity, shared location, witness status, or business
relationships. If the source is missing, corrupted, or ambiguous, leave the
fact unresolved and report the issue.

After editing, verify that JSON parses, the document-level `date` and
`entries` structure remain intact, each relevant entry retains `source`,
`german`, `english`, and `facts`, and each `facts` array follows the applicable
schema in `rules/json-formats.md`, including the `generic` type for other atomic claims. Confirm every fact is supported, atomic, relevant, and not duplicated;
also confirm source text, translation, citations, names, and date precision
were not changed unintentionally. Run `python3 scripts/validate_facts.py`
on edited files. The
validator checks syntax and references, not source support, identity, or graph
consistency. Verification quotes and statuses belong in the review response;
do not add redundant evidence or assessment fields to stored typed facts.
