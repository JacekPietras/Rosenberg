---
name: fact-extraction-review
description: When directly asked to extract fact entries from document json
---

# Fact extraction and review

Use this skill when extracting facts, adding them to a source entry, or auditing and correcting existing facts.

## Before editing

1. Read `../../../rules/facts.md` and `../../../rules/json-formats.md`. They are authoritative for fact criteria and JSON structure; follow them rather than repeating their details here.
2. Read the complete relevant JSON entry and source text. Treat the source field as authoritative (`german` or `latin`; `english` only when it is the only text field), as described in `../../../rules/facts.md`. Consult `../../../data/names.md` when normalizing personal names. For place-name variants, run `python3 scripts/list_place_variations.py` from the project root; add `--include-churches` when churches are relevant. Read the matching place record before adding or changing its variations.

## Work

- Extract only explicit, relevant claims. Find the supporting German passage for each fact and check it against the claim.
- When auditing, classify each fact as supported, partially supported, unsupported, or contradicted. Correct clear errors and remove unsupported or contradicted facts when asked to edit; flag unresolved ambiguity rather than guessing.
- Make the smallest targeted edit in the existing JSON entry. Preserve source text, translation, citations, date precision, and structure; avoid duplicates.

## Report and review

For an audit, report each fact with its entry or citation, exact German quote (or `NOT FOUND`), status, reasoning, and recommendation. When reporting new facts, include their supporting quotes.

Review the diff and confirm the JSON parses and each retained or added fact is supported. Mention unresolved items or verification limits.
