# Fact extraction and verification

Read this file when adding, changing, reviewing, or removing facts and guesses
in the JSON under `data/`. Document facts and guesses are stored once at the
document level and may be supported by any of its entries. Other sources store
assertions on the relevant entry. The object formats are in
[`json-formats.md`](json-formats.md).

## Source fields

- `german`, `latin`: the original text (or a book's German text). This is the
  source.
- `summary`, `abstract`: an archival summary (regest) of the original, usually
  in modern German (`summary`) or English (`abstract`). It helps to read the
  original but is not the source.
- `english`: normally the project's translation, not a source. When it is the
  entry's only text field, the source itself is English and `english` is
  authoritative.

When fields disagree, `german`/`latin` wins over a summary, and both win over
a translated `english`. A claim found only in a summary or a translation is not
a fact; correct the translation or report the difference.

An entry may be a continuation: its original text can refer back to a person,
bond, or event in an adjacent passage. Read the connected original passages to
resolve such references, and report the passages and evidence for continuity.
The event itself must be supported by the document or source entry containing
its fact; context can identify its participants, but does not add events or details to it.
Do not equate people merely because their names or circumstances resemble one
another. If continuity or identity is uncertain, preserve the source's own
designation and report the uncertainty instead of asserting an identification.

## Extraction

Read the complete entry first. Extract what the source states explicitly or
expresses unambiguously, including relationships directly conveyed by its
wording; do not speculate, interpret, or extrapolate. Each fact is one concise,
atomic assertion in English, keeping historically meaningful German or Latin
names, titles, places, and epithets.

| Source states | Fact |
| --- | --- |
| A is the parent, or B is the child, son or daughter of A | `parent` with A in `person`, B in `of` |
| Siblings | `sibling` |
| Spouses, a widow or widower | `spouse` |
| Other kinship (`Vetter`, `Oheim` …) | `kin` with the source's `term`, without guessing its degree |
| A designation at a date | `title` |
| A death, or that someone was dead by a date | `death`; cause, manner or place in `circumstances` |
| Anything else about a person | `generic` with `person` |
| A family, place, institution, object, or unidentified figure | `generic` with `subject` |

- Store a relationship once; never add its reverse or a symmetric copy.
- Record every relationship the document explicitly or unambiguously conveys
  among relevant family members and their kin, including each spouse and each
  sibling pair. Do not stop after recording only parent-child relationships.
  For example, if Konrad Rosenberg's brother had sons Hans and Eberhard, record
  Konrad and his brother as siblings, the brother as parent of each son, Hans
  and Eberhard as siblings, and Konrad's relationship to each nephew. If the
  source does not supply a kinship term for a relationship, express it in a
  `generic` fact rather than inventing a source term for `kin`. Preserve any
  uncertainty in the wording.
- Never use grouped forms such as "Sons: A and B".
- Do not infer relationships from proximity, transactions, witness status, or
  shared names, parents from siblings, a second parent from a spouse, full
  siblinghood from one shared parent, or sibling transitivity.
- Record a death fact only with a usable date or bound. "Deceased at a known
  date" becomes a `diedBefore` bound. Widowhood gives no death or marriage date.
- `generic` `content` begins with the predicate and does not repeat the
  subject's name or titles.

For property and transactions, state the people, property, place, and parties:
`X holds [asset] at [place]`, `X sold [asset] at [place] to Y`, `X donated
[asset] to Y`, `X exchanged [asset] for [asset]`, `X held [asset] as a [type]
fief from Y`, `X inherited or received [asset] from Y`. Also extract witnesses,
arbitrators, sureties, and official duties. Omit prices, amounts, measurements,
and administrative detail unless needed to identify the event.

### Deceased participants

Mark a participant the source identifies as dead with `personDeceased` or
`ofDeceased` on every fact where he appears; an unmarked participant counts as
alive at the fact's date. "Late", "selig", "quondam", and a widow or widower
designation (for the other spouse) all mark death. Never put `verstorben` or
similar in a title array.

### Titles

- Record only titles this source states, in `personTitle`/`ofTitle`; never copy
  them from `people.json` or another source. A title already on a relationship
  or generic fact needs no separate `title` fact at the same date.
- Keep German and Latin terms that carry historical meaning: `Ritter`, `Edel`,
  `Edelmann`, `Edelknecht`, `Knecht`, `Vogt`, `Hofmeister`, `Burggraf`,
  `Domherr`, `Vizedom`, `Vitztum`, `Komtur`, `miles`, `armiger`. Keep the
  territorial or institutional scope (`Vogt zu Dürn`).
- Keep `der Alte`, `der Ältere`, `der Junge`, and `der Jüngere` distinct and
  untranslated; expand `d. Ä.` and `d. J.` in facts and translations, not in
  the source text.
- Translate the term when it describes an office, action, or occupation rather
  than a title: `Eberhard served as bailiff of Dürn`, `Rudolf, a canon of
  Würzburg`. Avoid hybrids such as `bailiff zu Dürn`. Distinguish titles from
  place descriptions such as `pastor of Uissigheim`.
- Titles are dated attestations: `der Jüngere` can later be `der Ältere`, and
  `Edelknecht` can precede `Ritter`. A first `Ritter` does not date a
  knighting, and a missing title does not prove its absence. Do not infer that
  two people are one from matching titles.
- Complete a participant's titles from the entry text only when the name
  identifies one person there. Treat same-name participants as different
  people when they differ in age title (`der Ältere`/`der Jüngere`), deceased
  status, or registry ID, or when one fact names them as both `person` and
  `of`. Then add nothing to a participant lacking such a distinction, and take
  titles only from mentions that share a title with it. `scripts/linters/enrich_fact_titles.mjs`
  reports these completions; `--apply` writes them.

In `english` translations, keep family names intact (`von Uissigheim`, not "of
Uissigheim") and put titles after the full name, attached to each person in a
list: `Arnold von Uissigheim, Ritter`; `Konrad von Rosenberg der Ältere`;
`Eberhard von Rosenberg, Ritter; Johann von Randecke, Ritter`.

### Dates

Give a fact its own `date` when it differs from the enclosing date; book and
note facts always need one. Never use a publication date as historical time.

## Guesses

Put assumptions, inferences, and interpretations (including a book's or note's
own interpretation) in `guesses`, never in `facts`. State the uncertainty and
its basis, citing it when the entry does not. Guesses use the same types, are
about the same people and subjects as relevant facts, and never comment on
authors, sources, or research. Do not present a guess as settling who someone
is or how people are related.

"May have been the mother of X" says nothing about the parent being alive at
the date of the discussion: keep the recorded date and deceased status, and keep
it a `generic` guess, never a `parent` fact.

## Relevance

Focus extraction on von Rosenberg, von Uissigheim, von Erligheim, and their
kin. Capture all source-supported relationships involving these families and
their kin, including distant relatives and relatives with another family name.
Here, unrelated people are people who are not members or kin of these families,
even distantly. Facts solely about unrelated people are less important and
should be kept only when they meet the relevance rules below. Establish kinship
from evidence rather than assuming it.

Keep a fact when it mentions a member of von Rosenberg, von Uissigheim, or von
Erligheim; documents a direct interaction with them (relative, witness, surety,
arbitrator, transaction partner, other participant); or references Boxberg,
Wölchingen, Uissigheim, Erligheim, Rosenberg, or Bartenstein. A person the
source explicitly identifies as a relative of a target-family member remains
relevant even when they bear another name or no family name. Also keep an
explicit kinship fact about a named relative of a non-family participant when
that participant has a direct role in a relevant target-family event and the
source gives the relationship in that event. Do not infer family membership
from the relationship or extend relevance through further unmentioned
relatives. Keep relevant property and transaction facts even when they are not genealogical.

A person documented as born into a target family remains relevant when later
sources use a married name or another designation. Establish the identification
from evidence, not a shared name alone. When the possible connection is
unresolved, do not discard an existing source-supported assertion merely
because the later designation does not name the target family; flag it for
identity review.

Remove facts only about unrelated nobility or clergy, unrelated administration,
amounts or measurements, or third-party transactions without a target-family
participant.

`Schenk von Rosenberg` and `Mönch` (`Münch`) `von Rosenberg` are separate
families, distinct from each other and from the primary von Rosenberg family.
Do not target them because of the name, and never use their genealogy as
evidence about the primary family; a direct interaction with a target family is
still relevant.

## Names

- Write `person` and `of` as a normalized full name (`Konrad von Rosenberg`) or
  an exact `people.json` ID. Use an ID only when the source identifies that
  person; never give one ID to people because they share a name, title, or
  place.
- Normalize clear variants with `data/names.md` (`Conradus` → `Konrad`,
  `Arnolt` → `Arnold`), keeping the canonical form's case. `Kunz`/`Cunz` stays
  `Kunz`.
- For places, run `python3 scripts/list_place_variations.py`
  (`--include-churches` when relevant) and read the `data/places.json` record
  before changing its variations (`Ussinkeim` → `Uissigheim`).
- Never normalize away `der Ältere`, `zu [place]`, `dictus`, or other
  identifiers, and never unify two names only because they look similar. If a
  correspondence is ambiguous, keep the source form and flag it. Report new
  variants for the names or places file instead of inventing a standard form.

## Verification

For every fact, find the exact supporting passage in the source field and check
names, dates, titles, places, relationships, and similarly named people. Report
per fact: the fact, entry, exact quote (or `NOT FOUND`), status, reasoning, and
recommendation. Status is **supported** (explicit), **partially supported**
(core claim present, details wrong), **unsupported** (not found or needs
inference), or **contradicted**. Correct clear errors; remove unsupported and
contradicted facts. If the source is missing, corrupted, or ambiguous, leave the
fact and report the issue.

Review the event, participant identification, and each title or other detail
separately. If the event is supported but a detail is wrong, correct that detail
without deleting the supported event. If a participant's identity is ambiguous,
retain the source-supported event under the source's designation where possible
and report the uncertainty; do not turn an uncertain identity into a fact.

After editing, run `python3 scripts/lint.py`
(it checks syntax and references, not support), and review the diff: source
text, translation, citations, names, and date precision unchanged; facts
supported, atomic, relevant, and not duplicated. Verification belongs in the
review response, never in stored facts.
