# Fact extraction and verification

Read this file when adding, changing, reviewing, or removing `facts` in the
JSON documents under `data/`.

## Extraction

Read the complete document and its source text before adding facts. Extract
only information explicitly stated or unambiguously expressed in the source;
never infer, interpret, or extrapolate. The German source is authoritative when
it differs from the English translation. Facts must be concise, atomic,
explicit, and written in English, except for historically meaningful German or
Latin names, titles, places, and epithets. Make one assertion per fact string.

Extract all explicitly stated family relationships as separate atomic facts:

- `X is son/daughter of Y`
- `X is spouse/widow(er) of Y`
- `X is brother/sister of Y`

Never use grouped forms such as “Sons: A and B”. Do not assume relationship
symmetry: a statement that X is Y's brother does not automatically establish
the reverse relationship. Use full names and include epithets such as `der
Ältere` or `der Jüngere`, and territorial designations such as `zu Boxberg` or
`zu Wölchingen`, whenever they distinguish individuals.

Preserve German and Latin terminology exactly when it carries meaning. Useful
forms include `Ritter`, `Edelknecht`, `Vogt`, `Hofmeister`, `Burggraf`,
`Domherr`, `Vizedom`, `Vitztum`, `Komtur`, `miles`, and `armiger`. Include the
territorial or institutional scope, such as `erzbischöflicher Vogt zu Walldürn`
or `Vogt zu Dürn`.

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

Consult `data/names.md` for personal names and `data/places.json` for place
names. Use the first form in a variation entry as the standard only when the
correspondence is clear. Match spelling variants case-insensitively while
preserving the standard form's case.

Normalize clear variants such as `Conradus` to `Konrad`, `Arnolt` to `Arnold`,
`Engelhart` to `Engelhard`, `Ussinkeim` to `Uissigheim`, and `Erlikeim` to
`Erligheim`. Preserve context such as `dictus`, `von`, `miles`, and `armiger`.
`Kunz`/`Cunz` are shortened forms of Konrad but must remain `Kunz` when used;
do not expand them automatically.

Never merge people or places solely because their names are similar. If
identity is ambiguous, preserve the source form and flag it for review. Do not
normalize away `der Ältere`, `der Jüngere`, `zu [place]`, titles, or other
identifiers. Record legitimate new variants for later addition to the relevant
names or places file rather than silently inventing a standard form.

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
schema: letter facts are strings, while book facts are objects with `date` and
`text`. Confirm every fact is supported, atomic, relevant, and not duplicated;
also confirm source text, translation, citations, names, and date precision were
not changed unintentionally.
