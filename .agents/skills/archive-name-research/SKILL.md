---
name: archive-name-research
description: Search an archival catalog for records connected to a supplied person's name. Use when given an archive search URL and a name.
---

# Archive name research

Search the supplied archive catalog thoroughly for records that may concern the supplied person or family. The inputs are an archive search URL and a target name, usually with a given name and surname. Do not assume a particular archive, language, catalog platform, or record type.

## Establish the search space

- Inspect the repository's `../../../AGENTS.md`, `../../../README.md`, and relevant data rules before editing local research data. Look for an existing name-variant list, people index, or prior source entries; use these to expand spellings and avoid duplicate additions.
- Record the archive's own forms for exact, partial, and advanced searches. Determine how it handles accents, case, token order, wildcards, quotation marks, connectors, and pagination. Use the archive's interface or documented endpoints where possible; do not assume a search result page shows every hit.
- Generate sensible combinations from supplied and locally documented variants: given-name forms, surname forms, particles/connectors (including omitted particles), and plausible historic spellings. Search exact phrases as well as component terms when the interface supports them. Keep a list of actual queries and their result counts.
- Follow every accessible result page for every useful query. Deduplicate by stable archive identifier or record URL, not by title or date alone. Track inaccessible pages, query limits, failed requests, and overlapping results so the final coverage statement is accurate.
- If the catalog exposes linked person pages, alternate descriptions, digitized images, or finding-aid context, inspect them when they clarify a candidate. Treat snippets and person-index metadata as leads, not as proof of a person's role in the document.

## Analyze each candidate

- When the active environment permits delegation, assign a separate reviewer to each distinct candidate document. Give each reviewer the archive URL, target name and variants, the candidate's stable identifier, and the local data needed to check for duplicates. Ask for a recommendation of add, already represented, or unrelated/insufficient, with evidence and a source citation. The orchestrating agent coordinates searches and deduplication; reviewers assess individual documents.
- Ask each reviewer to distinguish direct mentions, named participants, linked-person-index-only matches, incidental family references, spelling collisions, place-name hits, and likely namesakes. Do not collapse people or lineages solely because their names look alike.
- Prefer inclusion when a record is plausibly relevant but identity or role remains uncertain. Preserve the archive's wording and make uncertainty explicit; do not convert a search hit into a firm biographical claim. Exclude clear false matches and explain the decision in the research notes or final summary.
- Check for an existing local entry before adding. A matching date is not sufficient to establish a duplicate: compare the source, archive identifier, participants, and document content. Record multiple catalog descriptions of one physical or textual document together when appropriate, rather than duplicating the document.

## Add and document findings

- If the task and repository call for data entry, follow the repository's schema and fact/source rules. Preserve source text, translations, citations, identifier/URL, and the archive's date precision. Make the smallest targeted change and review the diff.
- Cite each added candidate with a stable direct record URL and archive reference. Where only an index or catalog abstract supports the name, say so in the entry and do not imply the source text was checked.
- Keep a compact audit of query variants, total results/pages reviewed, unique candidates, additions, duplicates, exclusions, and unresolved access limits. Do not claim completeness when the catalog's pagination, indexing, or access prevented it.
- At completion, report the coverage and its limits, summarize what was added and why uncertain cases were retained, and point to the local entries or other deliverable.

## Delegation

For a large result set, divide the deduplicated records into manageable batches. When delegation is available and allowed, assign each individual document to one reviewer with a clear per-record evidence request. The orchestrator maintains the master candidate list, prevents overlapping additions, reconciles duplicates, and verifies that every candidate received a disposition. If delegation is unavailable or disallowed, process the records directly and retain the same per-record review standard.
