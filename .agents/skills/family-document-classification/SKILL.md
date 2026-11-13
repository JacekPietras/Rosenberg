---
name: family-document-classification
description: Classify a Rosenberg project document by the family it concerns, using its filename or source citation, and add a proposed family label to its JSON record.
---

# Family document classification

Use when asked which Rosenberg family a document concerns, including requests naming a document file or a record's `source` citation. The task includes updating that document's `label` with `Proposed: XXX`.

## Locate and assess the document

1. Resolve the supplied filename under `data/documents/`, or find document entries whose `source` contains the supplied exact citation. `source` may be a string or an array; compare against each citation string. If multiple documents match, identify the target from its text and citation; if it remains ambiguous, report the candidates without editing.
2. Read the complete record: date, place, every entry's source, German or Latin text, English text, summary, and relevant image/seal annotations. Prefer original German/Latin text over summaries and translations. Some records contain only an archival abstract/regest; use it as the available evidence, but say that the classification rests on the abstract rather than a full transcription.
3. Read `data/books/ai_2026.json` for the project's descriptions, estates, and notable members of the competing Rosenberg families. Read `data/distinctFamilies.md` for the permitted distinct-family labels. `Franken` is the label for the Bauland/Odenwald von Rosenberg family.
4. Search other documents for the named people, places, titles, offices, and distinctive transactions. Use those records to follow recurring associations and disambiguate same-name people and places; compare chronology and relationships rather than matching names alone. Search books and notes too when useful. Do not treat another record's label as evidence for its classification.
5. Search the web for notable people or places when external historical context could distinguish candidates. Prefer reliable archival, scholarly, or official sources; cite links in the report. Web evidence is corroboration and must not override the document's own explicit evidence without explanation.

## Choose a family

Compare the document's people, chronology, places, roles, and relationships with the descriptions and evidence above. A shared surname or a place called Rosenberg alone is not enough. Account for direct interactions: a record can concern a family even when its principal parties are not members, if its contents directly document that family's estate, rights, or affairs. Keep evidence from separate same-named families distinct.

### Shared regions and overlapping place evidence

Several distinct families appear in the same broad regions, so regional presence narrows the candidates but does not identify a family by itself. The Bauland/Odenwald von Rosenbergs (`Franken`) and the Mönch von Rosenbergs both have Bauland/Odenwald associations. The Schenk von Rosenbergs belong to the wider Franconian/Würzburg area, but their Roßberg/Schenkenschloss and office or service evidence distinguish them. The Lengenfelder, Raydenbach, Voit, and Wirt groups are all associated with Rosenberg near Sulzbach; Odenwald/Franken Rosenbergs can also appear in Sulzbach records, so do not assign `Sulzbach` based on the place alone. Use the specific people, chronology, titles, offices, and transaction to distinguish them.

The Brandenburg entries also cover distinct groups: early lords of Rosenburg, Querfurt, Barby, and Bredow-associated regional Rosenberg bearers. A Brandenburg place or Rosenburg reference does not establish continuity among them. The South Bohemian Rožmberks (`Czechia`) held lands in the Austrian Mühlviertel, while the Orsini-Rosenberg and Kamptal families are separate Austrian houses; an Austria/Czechia setting alone does not decide among these. Use the entry-specific people and historical context in `ai_2026.json`.

Choose one label:

- `Franken` for the Bauland/Odenwald von Rosenberg family.
- For another family, use its family label from `data/distinctFamilies.md` (preserving readable capitalization, such as `Schenk`, `Mönch`, `Czechia`, or `Sulzbach`). Use `ai_2026.json` to map the identified family to the permitted label. Some labels intentionally cover multiple families: for example, `Sulzbach` covers the Lengenfelders, Raydenbach, Voit, and Wirt groups. Identify the specific group when the evidence allows, but use the shared permitted label in the proposal.

Classify the family whose affairs the document most directly records, not automatically every family or person mentioned. If two permitted families are equally central and the document does not support choosing one, report the ambiguity and leave the record unchanged. A place name or castle name alone does not establish which family is involved; use evidence linking it to the family.

If the evidence does not support a family from the permitted set, do not invent a label. Explain the ambiguity or mismatch and leave the record unchanged.

## Apply and report

- Add exactly `Proposed: XXX`, replacing `XXX` with the chosen label. Ignore all existing labels when making the decision; preserve them and append the proposal to the existing string or array. Do not replace or correct other labels.
- Do not change any other document field or content. Avoid adding a duplicate identical proposal if it is already present.
- Preserve JSON structure and formatting as much as possible. Validate the edited JSON and review the diff to confirm the only change is the proposal label.
- Report the selected file and citation, proposed family, concise evidence from the document and cross-document or web research, and the edit made. Distinguish direct evidence from inference and cite external web sources when used.
