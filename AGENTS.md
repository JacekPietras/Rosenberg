# Agent Instructions

Read [README.md](README.md) before making structural changes.

## Data rules

- Work with the JSON files under `data/`. Do not refer to deleted scripts, reports, Markdown letters, or `data/facts.json`.
- Keep each document’s source text, English translation, and extracted `facts` together in the same JSON entry.
- Preserve valid JSON, the existing structure, source citations, and the smallest targeted edit.
- Preserve ISO date precision: `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`. Never invent missing date components.
- Facts must be concise, atomic, explicit, and supported by the associated source text. Write facts in English, but preserve historically meaningful German or Latin names, titles, and place names.

## Fact extraction

Read the complete document and its source text before adding facts. Extract only information explicitly stated or unambiguously expressed in the source; never infer, interpret, or extrapolate. The German source is authoritative when it differs from the English translation.

### Relationships and identities

Extract all explicitly stated family relationships as separate atomic facts:

- `X is son/daughter of Y`
- `X is spouse/widow(er) of Y`
- `X is brother/sister of Y`

Never write grouped forms such as “Sons: A and B”; create one fact for each relationship. Do not assume relationship symmetry: a statement that X is Y’s brother does not automatically establish every reverse relationship. Use full names and include epithets such as `der Ältere` or `der Jüngere`, and territorial designations such as `zu Boxberg` or `zu Wölchingen`, whenever they distinguish individuals.

### Titles and offices

Preserve German and Latin terminology exactly when it carries meaning. Useful forms include `Ritter`, `Edelknecht`, `Vogt`, `Hofmeister`, `Burggraf`, `Domherr`, `Vizedom`, `Vitztum`, `Komtur`, `miles`, and `armiger`. Include the territorial or institutional scope, for example `erzbischöflicher Vogt zu Walldürn` or `Vogt zu Dürn`.

### Property and transactions

Extract relevant holdings and actions in terms of the people, property, place, and parties involved:

- `X holds [asset] at [place]`
- `X sold [asset] at [place] to Y`
- `X donated [asset] to Y`
- `X exchanged [asset] for [asset]`
- `X held [asset] as a [type] fief from Y`
- `X inherited or received [asset] from Y`

Also extract relevant witnesses, arbitrators, sureties, and official duties. Omit prices, financial amounts, measurements, and unrelated administrative detail unless they are essential to identifying the event.

Make one assertion per fact string. Facts should be concise and written in English, except for historically meaningful names, places, titles, and epithets.

## Relevance and identity

### Keep criteria

Keep a fact if any of these are true:

- It mentions a member of **von Rosenberg**, any branch or generation.
- It mentions **von Uissigheim** or **von Erligheim** as ancestors, relatives, or connected families.
- It documents direct interaction with those families:
  - spouse, parent, child, or sibling;
  - witness, surety, or arbitrator;
  - transaction partner or other direct participant.
- It references places central to these families:
  - **Boxberg**;
  - **Wölchingen**;
  - **Uissigheim**;
  - **Erligheim**;
  - **Rosenberg** or **Bartenstein**.

### Remove criteria

Remove a fact if it is only about unrelated nobility or clergy, unrelated administrative activity, financial amounts or measurements, or a third-party transaction where none of the target families is a direct participant. Do not remove a relevant property or transaction fact merely because it is not genealogical.

**Münch von Rosenberg** is a distinct family. Never conflate it with the primary von Rosenberg family or use its genealogy as evidence about von Rosenberg. A Münch fact may remain when it explicitly documents a direct interaction with the primary von Rosenberg family.

## Names and normalization

Consult `data/names.md` for personal names and `data/places.json` for place names before normalizing them. Use the first form in a variation entry as the standard only when the correspondence is clear. Match spelling variants case-insensitively but preserve the standard form’s case.

Normalize clear variants such as `Conradus` to `Konrad`, `Arnolt` to `Arnold`, `Engelhart` to `Engelhard`, `Ussinkeim` to `Uissigheim`, and `Erlikeim` to `Erligheim`. Preserve the meaning of Latin or German context such as `dictus`, `von`, `miles`, and `armiger`. `Kunz`/`Cunz` are shortened forms of Konrad but must remain `Kunz` when used; do not expand them automatically.

Never merge people or places solely because their names are similar. If identity is ambiguous, preserve the source form and flag it for review. Do not normalize away `der Ältere`, `der Jüngere`, `zu [place]`, titles, or other identifiers. Record legitimate new variants for later addition to the appropriate names or places file rather than silently inventing a standard form.

## Source verification

For every generated fact, locate the exact supporting passage in the German source. The German source is authoritative when it differs from the English translation. Check names, dates, titles, places, relationships, and the identity of similarly named people.

When reporting verification, include the fact, source entry, exact supporting quote (or `NOT FOUND`), status, reasoning, and recommendation. If a source is bilingual, verify against both columns but treat the original German as authoritative.

Treat a fact as:

- **supported** only when the source explicitly supports it;
- **partially supported** when the core claim is present but details need correction;
- **unsupported** when the claim cannot be located or requires inference;
- **contradicted** when it conflicts with the source.

Correct clear errors and remove unsupported or contradicted facts. Never infer kinship from proximity, shared location, witness status, or a business relationship. Do not assume relationship symmetry: “X is brother of Y” must be supported as stated. If the source is missing, corrupted, or ambiguous, leave the fact unresolved and report the issue.

## Verification checklist

After editing, verify:

1. JSON parses successfully.
2. The document-level `date` and `entries` structure remain intact.
3. Each relevant entry retains `source`, `german`, `english`, and `facts` fields; `facts` is an array of strings.
4. Every fact has source support, is atomic, and is not duplicated or unrelated.
5. Source text, translation, citations, names, and date precision were not changed unintentionally.

There is no automated merge, sorting, queue, report, or temporary-file workflow. Add facts directly to the relevant JSON entry and review the diff.
