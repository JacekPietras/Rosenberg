---
name: place-history
description: Research and write sourced history for a place in data/places.json.
---

# Place history

Research and write a short historical description for a city, village, church, castle, or other place represented in `../../../data/places.json`. Use this skill when asked to add or revise a place's `history` field.

## Research

- Read `../../../rules/json-formats.md`, and the relevant place record in `../../../data/places.json` before editing. Search the canonical name and useful historical spelling variants, plus the place type and specific features.
- Before drafting a place history, you MUST spawn at least 10 subagents to research it. Do not substitute your own searches for these assignments or begin drafting before all 10 have returned findings. Assign each spawned agent a different website, publisher, or source portal—not merely a different section or topic on the same website—and use at least 10 distinct sites or portals across multiple independent domains. Do not count Wikipedia as one of the main research sources. If the platform limits concurrent agents, spawn and run them in batches until 10 distinct agents have completed their assignments. Suitable source types to seek, matched to the place and region, include:
  1. The municipality or local government's history pages and publications.
  2. A regional heritage organization, historical society, or museum.
  3. The official state or national monument inventory and heritage authority.
  4. A regional historical database or place-history portal.
  5. A state, municipal, or ecclesiastical archive catalog or digitized primary-source collection.
  6. A scholarly journal or academic project focused on the region or period.
  7. A university repository, library, or digitized scholarly book collection.
  8. A church, diocese, monastery, or other relevant institution's own history or archive.
  9. An archaeological service, excavation archive, or specialist architectural survey.
  10. A distinct specialist portal, such as one for historic maps, fortifications, trade, or local material culture.
- These are source-finding lanes, not mandatory categories: choose real, relevant sites for the place, and replace unavailable or inapplicable types with other independent sources. Wikipedia may help discover names and leads, but assign no more than one agent to it and verify its claims through other sources. Different agents may investigate overlapping historical questions, but each must search its own assigned site or portal so the research does not collapse into reading separate Wikipedia sections. Do not begin drafting until all 10 assignments have returned; if a site yields no usable evidence, record that result and give the agent a different relevant site to investigate.
- Give each subagent the place variants, place type, 1350–1450 priority, and its assigned website or portal. Ask for concise findings with the exact claim, date or date range, direct supporting quotation or passage, source title and link or publication details, and any uncertainty. Have agents distinguish the settlement's history from that of associated structures or institutions. Synthesize the findings, compare independent accounts, and verify claims against the cited sources yourself; parallel suggestions are leads, not evidence by themselves.
- Browse the web for place-specific evidence. Prefer local history or heritage organizations, municipal and regional historical resources, monument inventories, and scholarly publications. Use Wikipedia as an orientation and cross-checking source; do not rely on it alone when better evidence is available. Consult scientific papers or books when a disputed, specialized, or poorly documented point requires them.
- Follow sources to the page or publication that supports each claim. Use that evidence to verify the prose, but do not include citations, source lists, or research notes in the `history` value. Do not include claims that are not supported by sources.
- Distinguish the history of the settlement from that of its church, castle, lordship, or institution. Do not transfer dates or events between them without evidence. Treat legends and uncertain foundation dates as such, or omit them.

## Write the description

Write a sourced, readable English pointed list. Let the evidence determine its length; do not impose a fixed word limit. The `history` field should contain only the historical description: no source list, inline links, footnotes, or research notes. Use one bullet for each dated event or tightly bounded period; begin each historical bullet with the date or date range that actually applies to its contents. Every event with a stated date must appear under a bullet whose opening date includes that event's date. Do not use an early first-mention date as a heading for later events, and do not combine events from different dates into one bullet just because they concern the same place. Give each separately dated event its own bullet. Order the bullets chronologically and keep the account focused on the place itself:

1. Briefly mention developments before 1350 only when they provide useful context; otherwise start with the later medieval period. When a bullet includes multiple events, its date or range must span all of them and must not imply that later developments occurred at the date of the earliest event.
2. Give the main attention to 1350–1450. This period must not be reduced to a brief summary: include all significant developments about the place that reliable sources establish, such as changes in lordship or institutional control, conflicts, construction, rights, and economic or political roles. Explain how these developments relate to one another when the evidence allows. Stay focused on the place and omit only minor or unsupported detail.
3. Summarize 1450–1650 very briefly, including only significant transitions or damage.
4. End with a separate bullet beginning `Present:` that describes the place's current state and how much of the medieval built fabric or footprint survives, using concrete evidence (for example, surviving walls, a church core, foundations, a changed plan, or later rebuilding). Mention events after 1650 in earlier bullets only when they materially explain that condition.

Avoid bare date lists, generic regional background, unsupported precision, and lengthy accounts of later history. The list may need several bullets and may exceed a short paragraph when the 1350–1450 evidence is substantial; prioritize completeness for significant events in that period while keeping the other periods proportionate. Check that every date in a bullet agrees with its opening date or range; split the bullet if it does not. If evidence for a period or the surviving medieval extent is unavailable, omit the claim rather than guess. Make clear when a structure's visible fabric is later than its medieval origin.

## Edit `places.json`

- Add or revise one optional string property named `history` on the matching place object. Store only the historical prose in that string; do not create a separate source array or alter the place schema otherwise.
- Preserve all existing fields and records. Do not change `description`, coordinates, category, variations, or IDs as part of a history edit.
- Ensure JSON escaping is valid (including quotes and line breaks), then parse the JSON and review the diff to confirm that only the intended `history` value changed.

Example shape (replace the placeholder with researched prose):

```json
{
  "id": "example-place",
  "history": "- 1135: The place is first recorded.\n- 1344: A separately dated grant or event.\n- 1350–1360: A significant sourced development in the place’s history.\n- 1420: Another significant event.\n- Present: Description of the current place and the surviving medieval fabric."
}
```
