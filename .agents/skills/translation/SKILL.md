---
name: translation
description: Create or review the English translation of a historical document JSON entry from its German or Latin source text.
---

# Document translation

Use this skill when asked to translate or review the `english` field of a JSON document under `data/`, for example `1257-01-10_2.json`.

## Before editing

- Read `../../../specs/json-formats.md` and `../../../specs/person-names.md`.
- Open the requested document and inspect its full structure. Documents may contain multiple `entries`; translate or review the relevant entry or entries, keeping each translation aligned with its source text.
- Translate from the available transcribed source field, `german` or `latin` (only one is present). Do not translate an archival abstract in place of a transcription. When the source text is ambiguous, retain the ambiguity rather than silently resolving it.

## Translation

- Write clear, faithful English that preserves the source's claims, qualifications, relationships, names, dates, titles, and meaningful distinctions. Medieval German and Latin may use historical senses or constructions; interpret them in context and do not modernize away their meaning.
- If `english` is missing, add it to the corresponding entry. If present, review it against the source and correct omissions, mistranslations, or unnecessary literal phrasing. Preserve paragraphing, lists, and other meaningful structure.
- Keep `german`, `latin`, `summary`, citations, URLs, facts, labels, and all unrelated fields unchanged. Do not add facts or infer historical details that the text does not support.
- Follow the text-formatting rules in `json-formats.md`, including backticks around source passages intended to display in Fraktur. In the translation, omit redundant spelling variants and editorial spelling parentheses already preserved in the source.
- Follow `person-names.md`: retain particles and name-attached titles in German, normalize only clear listed name variants, and place titles in their canonical position. Translate an office or occupation when it is used descriptively in the sentence rather than attached as part of a person's name.
- When the source clearly refers to two distinct people with exactly the same name and their relationship establishes an older/younger distinction (for example, father and son), distinguish the relevant mentions as `der Ältere` and `der Jüngere`. Apply the distinction consistently wherever needed to make the English translation clear. Do not add either designation based only on a shared name or an uncertain relationship; preserve the ambiguity if the source does not establish which person is older.

## Review

After editing, parse the JSON and review the diff. Confirm that the translation matches the corresponding source text, the JSON remains valid, and only the intended `english` field or fields changed.
