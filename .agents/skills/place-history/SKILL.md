---
name: place-history
description: Research and write sourced history for a place in data/places.json.
---

# Place history

Research and write a historical description for a city, village, church, castle, or other place represented in `../../../data/places.json`. Use this skill when asked to add or revise a place's `history` field.

## Research

- Read `../../../rules/json-formats.md`, and the relevant place record in `../../../data/places.json` before editing. Search the canonical name and useful historical spelling variants, plus the place type and specific features.
- Browse the web for place-specific evidence. Prefer local history or heritage organizations, municipal and regional historical resources, monument inventories, and scholarly publications. Use Wikipedia as an orientation and cross-checking source; do not rely on it alone when better evidence is available. Consult scientific papers or books when a disputed, specialized, or poorly documented point requires them.
- Follow sources to the page or publication that supports each claim. Use that evidence to verify the prose, but do not include citations, source lists, or research notes in the `history` value. Do not include claims that are not supported by sources.
- Distinguish the history of the settlement from that of its church, castle, lordship, or institution. Do not transfer dates or events between them without evidence. Treat legends and uncertain foundation dates as such, or omit them.

### Required research delegation

The coordinating agent MUST spawn at least 10 research subagents before drafting a place history. Run them in batches when concurrency is limited, and wait for every assignment to return. Each agent must receive a concrete research question and an allocated body of sources. Sending the same general request to 10 agents does not satisfy this requirement. Research subagents carry out only their assigned research: they do not invoke this full workflow, spawn another set of agents, or edit `places.json`.

First perform brief source discovery to identify the relevant municipality, heritage authority, archives, regional scholarship, and promising publications. Then make an assignment table in the working context with an agent ID, question, primary website or collection, specific starting URLs or publication titles, and excluded sources already allocated to other agents. Choose the assignments for the actual place; the following are useful defaults:

| Agent | Specific research task | Sources to allocate |
| --- | --- | --- |
| 1 | Establish an outline, historical names, disputed dates, and bibliography leads. | The general Wikipedia article for the place and its references. Only this agent uses Wikipedia as its starting point; its summary claims require independent verification. |
| 2 | Find the local chronology and locally significant events, prioritizing 1350–1450. | Named municipal history pages, local museum publications, or a local historical society's website. |
| 3 | Find scholarly interpretations of the place's medieval history, including disputed events. | Specific academic articles or regional historical journals, located through scholarly indexes or repositories. Read the papers themselves. |
| 4 | Recover the fuller medieval narrative and details omitted from short web summaries. | Named scholarly monographs, critical local histories, or regional history books in digital libraries. Read relevant pages and record page numbers. |
| 5 | Reconstruct ownership and lordship: sales, pledges, inheritances, divided rights, and changes of territorial control. | Archival records, charter editions, regesta, or scholarly studies specifically covering the place's owners and transactions. |
| 6 | Date medieval monuments and distinguish their original fabric from later rebuilding. | The official monument inventory and architectural surveys for named churches, gates, walls, castles, or civic buildings. |
| 7 | Establish legal and administrative changes: town or market rights, jurisdiction, privileges, offices, and fortification permissions. | Allocated charter records, town-law editions, or administrative histories distinct from the ownership sources. |
| 8 | Explain the medieval settlement's economy and spatial development: markets, routes, trades, resources, expansion, and layout. | Specialist economic or settlement studies, historical atlases, or regional place-history entries. |
| 9 | Establish the role of local religious institutions, patronage, and institutional property. | Diocesan or monastic histories, ecclesiastical archives, and scholarly parish studies. Distinguish institutional events from events affecting the settlement. |
| 10 | Establish the current condition and what explains it: archaeological remains, surviving footprint, destruction, and rebuilding. | Archaeological reports, historical maps, conservation studies, or heritage surveys distinct from agent 6's building inventory. Keep later history limited to explaining survival or loss. |

Adapt these tasks to the place type and available evidence. For example, a castle may need separate studies of building phases, siege history, and lordship; a monastery may need foundation, endowments, and institutional reform. Replace inapplicable tasks with specific unanswered questions and distinct sources. The requirement is 10 substantive research assignments, not 10 positive findings or 10 compulsory topics.

Allocate sources to prevent convergence:

- Prefer different websites and publishers across assignments. Distinguish independent works as well as domains: two books hosted by one library can be separate sources, while mirrors or copied summaries of one article remain one source. Do not count different Wikipedia sections as separate assignments.
- Give each agent its allocated sources and the other agents' source exclusions. Agents should search within their assigned collection or source type using place variants and targeted questions. If an exact work is not yet identified, specify the collection, search terms, and the kind of evidence to locate.
- An agent may follow a citation to identify an underlying source. If that source belongs to another assignment, send the lead to the coordinator for routing rather than repeating the other agent's work. The coordinator updates source ownership as new works are found; source reuse for an explicit later cross-check is allowed.
- Require each report to identify sources actually read, with canonical URLs or bibliographic details and page numbers; provide each claim's date, supporting passage, and uncertainty. Also report inaccessible sources and searches with no useful results. A search snippet, bibliography entry, or Wikipedia citation alone does not establish a claim.
- Before synthesis, inspect the returned source lists for duplicate pages, mirrored texts, and shared underlying authorities. Route unfinished questions to the appropriate agent or assign unused sources when reports have converged. Never treat several agents repeating the same source as independent corroboration. Verify significant claims against the cited passages and resolve conflicting dates before drafting.

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
