---
name: place-history
description: Research and write sourced history for a place in data/places.json.
---

# Place history

Research and write a short historical description for a city, village, church, castle, or other place represented in `../../../data/places.json`. Use this skill when asked to add or revise a place's `history` field.

## Research

- Read `../../../rules/json-formats.md`, and the relevant place record in `../../../data/places.json` before editing. Search the canonical name and useful historical spelling variants, plus the place type and specific features.
- Browse the web for place-specific evidence. Prefer local history or heritage organizations, municipal and regional historical resources, monument inventories, and scholarly publications. Use Wikipedia as an orientation and cross-checking source; do not rely on it alone when better evidence is available. Consult scientific papers or books when a disputed, specialized, or poorly documented point requires them.
- Follow sources to the page or publication that supports each claim. Use that evidence to verify the prose, but do not include citations, source lists, or research notes in the `history` value. Do not include claims that are not supported by sources.
- Distinguish the history of the settlement from that of its church, castle, lordship, or institution. Do not transfer dates or events between them without evidence. Treat legends and uncertain foundation dates as such, or omit them.

## Write the description

Write a concise English paragraph, usually about 60–100 words. The `history` field should contain only the historical description: no source list, inline links, footnotes, or research notes. Keep the chronology focused on the place itself:

1. Briefly mention developments before 1350 only when they provide useful context; otherwise start with the later medieval period.
2. Give the main attention to 1350–1450: explain the important local changes, owners or institutions, conflicts, construction, rights, or economic role that sources establish. Select only the few events needed to explain the place's medieval character.
3. Summarize 1450–1650 very briefly, including only significant transitions or damage.
4. Describe the present condition and state how much of the medieval built fabric or footprint survives, using concrete evidence (for example, surviving walls, a church core, foundations, a changed plan, or later rebuilding). Mention events after 1650 only when they materially explain that condition.

Avoid a list of dates, generic regional background, unsupported precision, and lengthy accounts of later history. If evidence for a period or the surviving medieval extent is unavailable, omit the claim rather than guess. Make clear when a structure's visible fabric is later than its medieval origin.

## Edit `places.json`

- Add or revise one optional string property named `history` on the matching place object. Store only the concise prose in that string; do not create a separate source array or alter the place schema otherwise.
- Preserve all existing fields and records. Do not change `description`, coordinates, category, variations, or IDs as part of a history edit.
- Ensure JSON escaping is valid (including quotes and line breaks), then parse the JSON and review the diff to confirm that only the intended `history` value changed.

Example shape (replace the placeholder with researched prose):

```json
{
  "id": "example-place",
  "history": "A concise account of the place’s history and surviving medieval fabric."
}
```
