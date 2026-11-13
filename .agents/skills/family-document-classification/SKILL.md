---
name: family-document-classification
description: Classify a Rosenberg project document by the family it concerns, using its filename or source citation, and add a proposed family label to its JSON record.
---

# Family document classification

Use when asked which Rosenberg family a document concerns, including requests naming a document file or a record's `source` citation. The task includes updating that document's `label` with `Proposed: XXX`.

## Locate and assess the document

1. Resolve the supplied filename under `data/documents/`, or find the document entry whose `source` exactly matches the supplied reference. If there are multiple matches, identify the relevant record from its text and citation; if the target remains ambiguous, report the candidates without editing.
2. Read the complete record: date, place, every entry's source, German or Latin text, English text, summary, and relevant image/seal annotations. Prefer the original German/Latin evidence over summaries and translations.
3. Read `data/books/ai_2026.json` for the project's descriptions, estates, and notable members of the competing Rosenberg families. Read `data/distinctFamilies.md` for the permitted distinct-family labels. `Franken` is the label for the Bauland/Odenwald von Rosenberg family.
4. Search other documents for the named people, places, titles, offices, and distinctive transactions. Use those records to follow recurring associations and disambiguate same-name families. Search books and notes too when useful. Do not treat another record's label as evidence for its classification.
5. Search the web for notable people or places when external historical context could distinguish candidates. Prefer reliable archival, scholarly, or official sources; cite links in the report. Web evidence is corroboration and must not override the document's own explicit evidence without explanation.

## Choose a family

Compare the document's people, chronology, places, roles, and relationships with the descriptions and evidence above. A shared surname or a place called Rosenberg alone is not enough. Account for direct interactions: a record can concern a family even when its principal parties are not members, if its contents directly document that family's estate, rights, or affairs. Keep evidence from separate same-named families distinct.

Choose one label:

- `Franken` for the Bauland/Odenwald von Rosenberg family.
- For another family, use its family label from `data/distinctFamilies.md` (preserving the established readable capitalization, such as `Schenk` or `Mönch`). Use the corresponding family description in `ai_2026.json` to map records to that label.

If the evidence does not support a family from the permitted set, do not invent a label. Explain the ambiguity or mismatch and leave the record unchanged.

## Apply and report

- Add exactly `Proposed: XXX`, replacing `XXX` with the chosen label. Ignore all existing labels when making the decision; preserve them and append the proposal to the existing string or array. Do not replace or correct other labels.
- Do not change any other document field or content. Avoid adding a duplicate identical proposal if it is already present.
- Preserve JSON structure and formatting as much as possible. Validate the edited JSON and review the diff to confirm the only change is the proposal label.
- Report the selected file and citation, proposed family, concise evidence from the document and cross-document or web research, and the edit made. Distinguish direct evidence from inference and cite external web sources when used.
