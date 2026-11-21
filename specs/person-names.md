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

The module builds one dictionary per set of data files, finds candidate spans
with a regex, scans each span into given names, ordinal, by-name, particle,
place, titles, designations, and birth name, and resolves them into a route name
plus canonical titles.

Name connectors such as `genannt`, `called`, and `known as` are comma-separated
equivalents in `data/name-connectors.md`. The recognizer accepts them before a
given name or between the given name and its particle.

## Structure

Canonical form:

```text
<given name(s)> <particle> <place> [zu <place>] [age title] [, title ...]
```

Recognized (non-canonical) forms may also carry titles before the given names
or between the given names and the particle:

```text
[titles] <given name(s)> [titles] <particle> <place> ...
```

| Part | Rule |
| --- | --- |
| Given names | One or more canonical forms from `data/names.md` under `# Men` or `# Women` (`Conradus` → `Konrad`) |
| By-names | Forms in `data/by-names.md` are never given names. When a listed form directly precedes a Rosenberg particle-place name, it joins that name into the family name: `Hans Schenk von Rosenberg` has given name `Hans` and family name `Schenk von Rosenberg`. A following `zu <place>` is ordinarily a title/place designation, not part of that family name. A by-name that is also a title word (`Voit`, `Voyt`) is a by-name there, never the title `Vogt`: `Friedrich Voit von Rosenberg` is not `Friedrich von Rosenberg, Vogt`. |
| Ordinal | A Roman numeral after a given name may appear in source text and is consumed during recognition, but omitted from the recognized route name. |
| Particle | `von`, `de`, `v.`, `van` … from `data/nobiliary_particles.md`, as the source has it; `v.` and `von.` become `von` |
| Place | A place variation from `list_place_variations.py`, written in its canonical form: the first variation of its record (`Ussinkeim` → `Uissigheim`, `Nuremberg` → `Nürnberg`). The same form is used in routes, title places, and designations. |
| `zu <place>` | Optional second place, part of the name when the source attaches it to the person; contracted `zum <place>` has the same meaning and normalizes to `zu <place>` |
| Name connector | `genannt`, `called`, `known as` and listed forms introduce a designation. In constructions such as `Eberhard genannt von Rosenberg`, the following `von Rosenberg` is the designation, not a surname component. |
| Simple titles | Single title words and epithets from `data/titles-age.md` (`der Jüngere`, `der Ältere`) and `data/titles-office.md` (`Ritter`, `Vogt`, `der Rote`); the first form of a group is canonical |
| Full titles | A simple title with an optional `zu`/`zum <place>` or `an <place>`: `Vogt zu Lauda`, `Vizedom zu Amberg` (source `Vitzthum zu Amberg`); listed places use the canonical form from the Place row, `of <place>` becomes `zu <place>`. The recognizer may retain a one-word unlisted place in a recognized title, but it is not normalized; report it for the place list. An unlisted place must be a capitalized word that is not an article, pronoun, or similar function word (`the`, `der`, `his` …) and never includes trailing punctuation (`Amtmann zu Hanau.` → `Amtmann zu Hanau`). |

For a listed by-name followed by the Rosenberg place, `von Rosenberg` and
`zu Rosenberg` forms identify the same family name: `Schenk von Rosenberg`
and `Schenk zu Rosenberg` are equal family-name forms. This equivalence is
specific to the listed by-name construction and to the Rosenberg place; do not
equate `von` and `zu` particle-place names otherwise. A by-name followed by
`zu` and any other place keeps the place as a designation: `Hans Truchseß zu
Aue` is `Hans Truchsess` with the designation `zu Aue`; `Hans Stieber zu
Aisch` is `Hans Stieber`, `zu Aisch`. With `von` the place stays in the family
name (`Hans Marschalk von Pappenheim`).

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
in `Elisabeth von Rosenberg, née Marschalk von Pappenheim`, `von Rosenberg` is
not her birth family name: `Marschalk von Pappenheim` is the name introduced
by `née`, while `von Rosenberg` is the later title/designation and must be
preserved as such. The route is `Elisabeth Marschalk von Pappenheim`; the
recognizer returns `von Rosenberg` as a title. Do not merge it into her birth
name or treat it as a by-name construction. Titles written between the married
and the birth name are kept too: `Dorothea von Wertheim, Gräfin, née von
Rieneck` has route `Dorothea von Rieneck` and titles `von Wertheim`, `Graf`.

Canonical examples: `Konrad von Rosenberg`, `Konrad von Rosenberg der Ältere`,
`Arnold von Uissigheim, Ritter`, `Eberhard von Rosenberg, Vogt zu Lauda`.

Non-canonical, to be recognized and rewritten: `Ritter Arnold von Uissigheim`,
`Arnold Ritter von Uissigheim`, `Konrad der Ältere von Rosenberg`.

## Territorial, family, and realm titles

`data/titles-office.md` classifies some titles by its `//` sections; the
recognizer treats the place after them differently from other offices.

- `// territorial titles` (Bischof, Erzbischof, Abt, Äbtissin, Herzog,
  Kurfürst, Pfalzgraf, Landgraf, Marggraf, Burggraf): the place belongs to the
  office, never to the family name. `Bishop Konrad of Würzburg`, `Konrad zu
  Würzburg, Bischof`, and `Konrad, Bischof zu Würzburg` all give the name
  `Konrad` with the title `Bischof zu Würzburg`; `Johann II zu Würzburg,
  Bischof` gives `Hans`. English `of <place>` becomes `zu`; a source `von`
  or `zu` is kept (`Johann, Abt von Fulda` → `Abt von Fulda`). Several titles
  are all returned (`Bischof zu Würzburg`, `Herzog zu Franken`). After a
  leading title, `zu`/`of <place>` is always the office place and `von <place>`
  only when the place is a see or territory in `data/title-seats.md`
  (`Bishop Konrad von Würzburg` → `Konrad`, `Bischof von Würzburg`); otherwise
  it is the family name (`Bishop Konrad von Thüngen`). After a trailing title
  only `zu`/`of` is the office place: `Gerhard von Schwarzburg, Bischof` has
  the family name `von Schwarzburg` and the bare title `Bischof`. A territorial
  title and a given name without a place is not by itself recognized as a
  mention. `vom` in a title place is written `von`, as `zum` is written `zu`.
- `// family titles` (Graf, Gräfin, Count, Countess): the place is the family
  name and also part of the title. `Thomas, Graf von Rieneck`, `Count Thomas of
  Rieneck`, and `Graf Thomas von Rieneck` give `Thomas von Rieneck` with the
  title `Graf von Rieneck` (`of` becomes `von`; a source `zu` stays: `Johann,
  Graf zu Hardegg` → `Johann zu Hardegg`, `Graf zu Hardegg`). A title after a
  complete name stays bare (`Thomas von Rieneck, Graf` → `Graf`).
- `// route titles` (König, Kaiser): the realm is never a family name. The
  title belongs to the route (`König Wenzel`) and carries the realm (`König von
  Böhmen`, from `King Wenzel IV of Bohemia`). The numeral is omitted from the
  route. The realm must be listed
  under `// realms` in `data/title-seats.md`, written after `of` or `von`
  (not `zu`) and without a possessive; otherwise the title is bare (`of
  Bohemian`) or, after `von <unlisted place>`, dropped because the place is the
  person's family name (`Roman King Hans von Neitperg` → `Hans von Neitperg`).
- `data/title-seats.md` lists seats (`// sees`), territories (`//
  territories`), and realms (`// realms`), one place per line with equivalent
  forms after commas; the first form is canonical. The file is appended to the
  name-connectors text passed to the recognizer, and only those sections are
  read from it. Forms there need not be in `places.json`.
- An age title never takes a place; `der Jüngere of Boxberg` gives `der
  Jüngere` and `zu Boxberg`.

## Language

- Particles and titles are always in their German form: the particle as in the source (`von`, `zu`, `an` …), never `of`;
  `der Jüngere`, never `the Younger`; `Ritter`, never `knight`; `Eberhard von Rosenberg, Vogt zu Lauda`, never `Eberhard von
  Rosenberg, bailiff of Lauda`.
- English forms are not canonical and must be corrected. `of` between a name and
  a place is never a particle: it flattened several German particles (`von`,
  `zu`, `an`, …) into one word, so it is never replaced by guessing: the
  recognizer keeps `Hans of Wertheim` as written (the title rules above are the
  exception, because the title fixes the meaning). Restore the
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
- A mention is one sentence-internal phrase. It never crosses a sentence end:
  trailing `.`, `,`, `;` are not part of it, a leading title must directly
  precede the given name, and a bare place surname needs a single space after
  the name (`Friedrich IV.   Heidelberg` is not one name). A saint reference
  (`St. Burkard in Würzburg`) is not a person.
- A title that directly precedes a given name belongs to that person, not to
  the preceding coordinated list (`Eglolf and Egilolf von Rosenberg, Abbot
  Hiltpold`). In `Elector Ludwig and Philipp zu Speyer, Bischof` the title
  and place after the list belong to the last person (`Bischof zu Speyer`) and
  the leading title to the first (`Kurfürst`).
- A single word that matches a title directly after one given name is a
  surname, not a title (`Georg Keller`); after a comma it is a title.

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
