# Person names in text

Read this file when writing a person's name in `english` or in the text of
`facts` and `guesses` (`content`, `subject`, `term`). `german`, `latin`, and
`summary` are copied from the source and never changed.

The shared recognition logic is
[`docs/app/data/person-name-recognition.js`](../docs/app/data/person-name-recognition.js);
its lists are `data/names.md`, `data/nobiliary_particles.md`,
`data/titles-age.md`, `data/titles-office.md`, and place variations. Look places up with
`python3 scripts/list_place_variations.py` (`--include-churches` when relevant);
`scripts/place_names.py` resolves building names against their settlements.
Do not read `data/places.json` directly; it is very large.

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
| Given names | One or more canonical forms from `data/names.md` (`Conradus` → `Konrad`) |
| Ordinal | Optional roman number after the given names: `II`, `(II)`, `[II]`, `II.` |
| Particle | `von`, `de`, `v.`, `van` … from `data/nobiliary_particles.md`, as the source has it; `v.` and `von.` become `von` |
| Place | A canonical place variation from `list_place_variations.py` (`Ussinkeim` → `Uissigheim`) |
| `zu <place>` | Optional second place, part of the name when the source attaches it to the person |
| Simple titles | Single title words and epithets from `data/titles-age.md` (`der Jüngere`, `der Ältere`) and `data/titles-office.md` (`Ritter`, `Vogt`, `der Rote`); the first form of a group is canonical |
| Full titles | A simple title with an optional `zu <place>` or `an <place>`: `Vogt zu Lauda`, `Vizedom zu Amberg` (source `Vitzthum zu Amberg`); the place is canonical as in the Place row |

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
- A place after the particle is a place in the name, not a residence;
  generic building names need their parent (see
  [`json-formats.md`](json-formats.md#parents-and-names)).
- Different people may share a name; a name alone never identifies a person.
