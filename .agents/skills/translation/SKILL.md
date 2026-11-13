---
name: translation
description: Create or review the English translation of a historical document JSON entry from its German or Latin source text.
---

# Document translation

Use this skill when asked to translate or review the `english` field of a JSON document under `data/`. The user may identify the document by filename (for example, `1257-01-10_2.json`) or by a source citation (for example, `[RI VII] H. 3 n. 3`). When given a citation, search the document entries' `source` fields to locate the matching entry; do not require a filename in the request.

## Before editing

- Read `../../../specs/json-formats.md` and `../../../specs/person-names.md`.
- Open the requested document and inspect its full structure. Documents may contain multiple `entries`; translate or review the relevant entry or entries, keeping each translation aligned with its source text.
- Translate from the available transcribed source field, `german` or `latin` (only one is present). Do not translate an archival abstract in place of a transcription. When the source text is ambiguous, retain the ambiguity rather than silently resolving it.

## Place and surname variants

When creating or reviewing a transcription, normalize a clearly identified place name to its canonical form from `data/places.json`, including a place used in a surname such as `von Neuburg`. Preserve the source spelling only when it is itself the canonical form; do not retain a parenthetical historical spelling in the transcription. Do not normalize a surname merely because it resembles a place name, or resolve an uncertain identification by guesswork.

For each noncanonical spelling encountered, check `data/places.json` with `python3 scripts/list_place_variations.py '<spelling>'` (add `--include-churches` when relevant). If the spelling is supported by the source and identifies the same place, ensure it is listed in that place record's `variations`, retaining the canonical name first. Follow `specs/json-formats.md` and `specs/facts.md` for evidence and place-data requirements; use the place-history skill or suitable sources to establish missing information. Do not create a place or add a variation from resemblance alone. If identity or evidence is uncertain, leave the spelling unchanged and report it for follow-up.

Keep this place registry maintenance separate from translation: do not rewrite existing `german`/`latin` source text during translation review. When a transcription is being prepared, use the canonical name in the transcription and preserve verified historical spellings in `places.json`.

## Translation

- Write clear, faithful English that preserves the source's claims, qualifications, relationships, names, dates, titles, and meaningful distinctions. Medieval German and Latin may use historical senses or constructions; interpret them in context and do not modernize away their meaning.
- If `english` is missing, add it to the corresponding entry. If present, review it against the source and correct omissions, mistranslations, or unnecessary literal phrasing. Preserve paragraphing, lists, and other meaningful structure.
- Keep `german`, `latin`, `summary`, citations, URLs, facts, labels, and all unrelated fields unchanged. Do not add facts or infer historical details that the text does not support.
- Follow the text-formatting rules in `json-formats.md`, including backticks around source passages intended to display in Fraktur. Before finalizing, compare every parenthetical in the translation with the source: omit spelling variants and editorial spelling notes that the source already records, while retaining parentheses only when they carry substantive meaning needed in English. For example, source `Hermann von Lißberg (Lys-)` becomes `Hermann von Lißberg`; do not copy `(Lys-)` into the translation. Also omit unexplained editorial reference markers such as superscript footnote numbers when the corresponding notes are not included in the entry. Do not carry over parenthetical clause numbers used only to enumerate an archival abstract or regest; express the content as clean connected prose while preserving substantive numbers, dates, and quantities.
- Follow `person-names.md`: retain particles and name-attached titles in German, normalize only clear listed name variants, and place titles in their canonical position. Translate an office or occupation when it is used descriptively in the sentence rather than attached as part of a person's name.
- When the source clearly refers to two distinct people with exactly the same name and their relationship establishes an older/younger distinction (for example, father and son), distinguish the relevant mentions as `der Ältere` and `der Jüngere`. Apply the distinction consistently wherever needed to make the English translation clear. Do not add either designation based only on a shared name or an uncertain relationship; preserve the ambiguity if the source does not establish which person is older.

## Review

After editing, parse the JSON and review the diff. Confirm that the translation matches the corresponding source text, the JSON remains valid, and only the intended `english` field or fields changed.
