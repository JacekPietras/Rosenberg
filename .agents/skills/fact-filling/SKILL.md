---
name: fact-filling
description: Extract, review, and update source-supported facts and guesses in the project's data JSON entries.
---

# Fill facts

Use this skill when asked to add or review `facts` or `guesses` for an entry in `data/`.

## Before editing

- Read `../../../specs/facts.md`, `../../../specs/json-formats.md`, and `../../../specs/person-names.md`.
- Read the complete source entry and its context before extracting or reviewing assertions. `german` or `latin` is the source; a summary is only a finding aid. Never use `english` alone as the source for facts or guesses. If the source text is missing, report that support cannot be verified rather than treating the translation as authoritative.
- Preserve the entry's existing structure and unrelated data. Keep facts source-supported and relevant under `facts.md`; put interpretations and assumptions only in `guesses`.

## Extract and normalize

- Make each assertion atomic and use only the fact types and fields defined in `json-formats.md`. Store relationships once, without reverse copies. Do not infer kinship from proximity, transactions, witness status, shared names, or other association.
- Use exact source wording for kinship terms, and preserve meaningful historical names, titles, places, and distinctions. Apply the date precision, deceased-participant, title, death-bound, relevance, and name-normalization rules in `facts.md`.
- For a person's name in `person`, `of`, or fact prose, follow `person-names.md`. Use a `people.json` ID only when the source identifies that particular registered person; shared names are not sufficient.
- For every place name in an assertion, including a place used as a person's name after a particle such as `von` (for example, Rosenberg in `Eberhard von Rosenberg`), check whether the place is represented in `data/places.json`. Use `python3 scripts/list_place_variations.py` to search existing canonical names and variants; do not read the large `places.json` file directly. Do not confuse alternate designations introduced by a name connector (such as `genannt von Rosenberg`) with a surname-place without independent evidence.
- If a referenced place is absent, add a place record to `data/places.json` when it can be identified and the required place data can be supported. Follow the place schema and settlement rules in `json-formats.md`: use a stable ID, canonical name first in `variations`, supported coordinates and category where applicable, and a sourced `description` when needed. Establish whether a settlement was a city or village in 1387 from suitable evidence before assigning that category. Do not invent a settlement, category, parent, coordinates, or historical identification from a name alone. If evidence or required data is missing or ambiguous, leave `places.json` unchanged and report the place for follow-up rather than guessing.

## Verify and finish

- For every fact or guess, locate its exact supporting source passage and verify names, dates, titles, places, relationships, and similarly named people. When reviewing existing assertions, report unsupported or contradicted items and correct clear errors; if the source is unavailable or ambiguous, leave the assertion and report the issue.
- Report each reviewed or added assertion with its entry, exact supporting quote (or `NOT FOUND`), status, reasoning, and recommendation, as specified in `facts.md`.
- After editing, run `python3 scripts/lint.py` and review the diff. Confirm valid JSON, source support, atomicity, relevance, no duplicates, preserved date precision and source fields, and only intended fact/guess changes plus any justified missing place records.
