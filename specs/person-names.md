# Person names in text

Read this file when writing a person's name in `english` or in the text of
`facts` and `guesses` (`content`, `subject`, `term`). `german`, `latin`, and
`summary` are copied from the source and never changed.

The browser recognition logic is
[`docs/app/data/person-name-recognition.js`](../docs/app/data/person-name-recognition.js).
It uses `data/names.md`, `data/by-names.md`, `data/nobiliary_particles.md`,
`data/name-connectors.md`, `data/titles-age.md`, `data/titles-office.md`, and
place variations. Family-graph prose recognition is implemented separately
in `scripts/family_graph/person_names.py`; it uses given names, particles,
titles, connectors, by-names, and place variations. Keep their behavior aligned
where both recognize the same forms. Look places up with
`python3 scripts/list_place_variations.py` (`--include-churches` when relevant);
`scripts/place_names.py` resolves building names against their settlements.
Do not read `data/places.json` directly; it is very large.

Name connectors such as `genannt`, `called`, and `known as` are comma-separated
equivalents in `data/name-connectors.md`. The recognizer accepts them before a
given name or between the given name and its particle.

## Structure

Canonical form:

```text
<given name(s)> [ordinal] <particle> <place> [zu <place>] [age title] [, title ...]
```

Recognized (non-canonical) forms may also carry titles before the given names
or between the given names and the particle:

```text
[titles] <given name(s)> [ordinal] [titles] <particle> <place> ...
```

| Part | Rule |
| --- | --- |
| Given names | One or more canonical forms from `data/names.md` under `# Men` or `# Women` (`Conradus` → `Konrad`) |
| By-names | Forms in `data/by-names.md` are never given names. When a listed form directly precedes a Rosenberg particle-place name, it joins that name into the family name: `Hans Schenk von Rosenberg` has given name `Hans` and family name `Schenk von Rosenberg`. A following `zu <place>` is ordinarily a title/place designation, not part of that family name. A by-name that is also a title word (`Voit`, `Voyt`) is a by-name there, never the title `Vogt`: `Friedrich Voit von Rosenberg` is not `Friedrich von Rosenberg, Vogt`. |
| Ordinal | Optional roman number after the given names: `II`, `(II)`, `[II]`, `II.` |
| Particle | `von`, `de`, `v.`, `van` … from `data/nobiliary_particles.md`, as the source has it; `v.` and `von.` become `von` |
| Place | A canonical place variation from `list_place_variations.py` (`Ussinkeim` → `Uissigheim`) |
| `zu <place>` | Optional second place, part of the name when the source attaches it to the person; contracted `zum <place>` has the same meaning and normalizes to `zu <place>` |
| Name connector | `genannt`, `called`, `known as` and listed forms introduce a designation. In constructions such as `Eberhard genannt von Rosenberg`, the following `von Rosenberg` is the designation, not a surname component. |
| Simple titles | Single title words and epithets from `data/titles-age.md` (`der Jüngere`, `der Ältere`) and `data/titles-office.md` (`Ritter`, `Vogt`, `der Rote`); the first form of a group is canonical |
| Full titles | A simple title with an optional `zu`/`zum <place>` or `an <place>`: `Vogt zu Lauda`, `Vizedom zu Amberg` (source `Vitzthum zu Amberg`); listed places use the canonical form from the Place row. The recognizer may retain a one-word unlisted place in a recognized title, but it is not normalized; report it for the place list. |

For a listed by-name followed by the Rosenberg place, `von Rosenberg` and
`zu Rosenberg` forms identify the same family name: `Schenk von Rosenberg`
and `Schenk zu Rosenberg` are equal family-name forms. This equivalence is
specific to the listed by-name construction; do not generally equate `von`
and `zu` particle-place names.

By-names are maintained separately from given names because they cannot fill
the given-name position. A listed by-name used as a person's surname is part
of the family name even when no Rosenberg place-name follows: `Hans Schenk`
has given name `Hans` and family name `Schenk`. A listed by-name directly
before `von Rosenberg` likewise joins that name into the family name: `Hans
Schenk von Rosenberg` means `Hans` + `Schenk von Rosenberg`. Here `Schenk` is
a by-name, not a title, and `von Rosenberg` is part of the same family name.
The source may omit the place-name, or attach `zu <place>` separately as a
title/place designation. Without a preceding by-name, `zu <place>` remains a
separate title/place designation when the source attaches it that way, as in
`Hans von Rosenberg zu Lauda`. Apply these readings only where the listed
by-name functions as the person's surname in context.

A trailing `zu` or `zum` place after a complete particle-place surname can be
a title/designation rather than part of the name. For example,
`Konrad von Rosenberg zu Bartenstein` is recognized as the mention `Konrad von
Rosenberg` with the title/designation `zu Bartenstein`; its person-name route
uses `Konrad von Rosenberg`. The same applies to `Konrad von Rosenberg zum
Bartenstein`. A listed by-name followed directly by `zu Rosenberg` remains the
special family-name construction described above.

Keep a birth name distinct from a later title or designation. For example,
in `Elisabeth von Rosenberg, née Marschalk zu Pappenheim`, `von Rosenberg` is
not her birth family name: `Marschalk zu Pappenheim` is the name introduced
by `née`, while `von Rosenberg` is the later title/designation and must be
preserved as such. Do not merge it into her birth name or treat it as a
by-name construction.

Canonical examples: `Konrad von Rosenberg`, `Konrad von Rosenberg der Ältere`,
`Arnold von Uissigheim, Ritter`, `Eberhard von Rosenberg, Vogt zu Lauda`.

Non-canonical, to be recognized and rewritten: `Ritter Arnold von Uissigheim`,
`Arnold Ritter von Uissigheim`, `Konrad der Ältere von Rosenberg`.

## Language

- Particles and titles are always in their German form: the particle as in the source (`von`, `zu`, `an` …), never `of`;
  `der Jüngere`, never `the Younger`; `Ritter`, never `knight`; `Eberhard von Rosenberg, Vogt zu Lauda`, never `Eberhard von
  Rosenberg, bailiff of Lauda`.
- English forms are not canonical and must be corrected. `of` between a name and
  a place is never a particle: it flattened several German particles (`von`,
  `zu`, `an`, …) into one word, so it is never replaced by guessing. Restore the
  particle the `german`/`latin` source has: `Hartmut the Younger of Kronenberg`
  becomes `Hartmut von Kronenberg der Jüngere` only if the source says `von`.
  `the Younger` becomes `der Jüngere` and moves after the surname. Recognizers
  should still accept the English form so it can be found and corrected.
- If the source particle is not in `data/nobiliary_particles.md` (for example
  `an`), keep it as in the source and report it for the list.
- Latin or variant forms (`miles`, `armiger`, `v.`) in a name are likewise
  corrected to the German form: titles to the first form of their group in
  `data/titles-office.md` or `data/titles-age.md`; `v.` and `von.` to `von`; other particles stay as in the
  source.

## Titles and position

- Canonical: every title follows the surname. An age title comes directly after
  it; other titles come after a comma, separated by `,` or `;` as in the source
  (see [`facts.md`](facts.md#titles)).
- A title before the given name or between the given names and the particle is
  not canonical. Matchers and recognizers must still accept it as part of the
  name, with any title from the two title files, and must not treat it as a
  different person or a part of the given name.
- When writing or normalizing `english` and fact text, move such titles to the
  canonical position; never drop them.

## Rules

- A name is written once per mention in this form; family names stay intact
  (`von Uissigheim`, never "of Uissigheim").
- In facts, titles belong in `personTitle`/`ofTitle`, not in `person`/`of`;
  `person` and `of` hold only the normalized full name or an ID
  ([`json-formats.md`](json-formats.md#fields)). In `content`, never repeat the
  name or titles.
- `english` places titles after the full name, attached to each person
  separately: `Eberhard von Rosenberg, Ritter; Johann von Randecke, Ritter`.
- A title attached to a name stays German (`Vogt zu Lauda`). Only an office or
  occupation described in the sentence, not attached to a name, is translated
  (`Eberhard served as bailiff of Dürn`), as in [`facts.md`](facts.md#titles);
  never mix the two (`bailiff zu Dürn`).
- Expand `d. Ä.` and `d. J.` to `der Ältere` and `der Jüngere`.
- Normalize only clear variants from the lists. If a name, title, or place is
  ambiguous or not listed, keep the source form and report it; do not invent
  a standard form, and never unify names only because they look similar.
- A name connector introduces an alternate designation, not a surname. For
  example, in `Ritters Eberhard genannt von Rosenberg`, recognize the person
  mention, but do not treat `von Rosenberg` as Eberhard's surname or rewrite it
  as `Eberhard von Rosenberg` without independent source evidence. An English
  rendering such as `a knight called Eberhard von Rosenberg` does not change
  that distinction.
- A place after the particle is a place in the name, not a residence;
  generic building names need their parent (see
  [`json-formats.md`](json-formats.md#parents-and-names)).
- Different people may share a name; a name alone never identifies a person.
