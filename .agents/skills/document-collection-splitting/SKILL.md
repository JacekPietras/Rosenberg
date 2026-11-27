---
name: document-collection-splitting
description: Split a Rosenberg project document that describes a collection of separately dated historical documents into relevant individual JSON records.
---

# Split document collections

Use when asked to split a collection identified by a document filename or archival citation. Read `../../../README.md`, `../../../specs/json-formats.md`, and `../../../specs/facts.md` before editing.

## Identify and assess

- Locate the record under `data/documents/`; search `source` strings and arrays for a supplied citation. If a citation matches multiple records, resolve the target from context; report ambiguity if it cannot be resolved.
- Read the complete record and identify the boundaries of the individual historical documents, including continuations, folio references, and shared collection context. A collection's date range, a date mentioned within an item, and a document's own date are different things. Multiple dates alone do not necessarily mean multiple documents.
- Assess every item against the relevance rules in `specs/facts.md`: target families include von Rosenberg, von Uissigheim, von Erligheim, their evidenced kin, direct participants in relevant events, and relevant places. Distinguish unrelated Rosenberg families and namesakes. Use source context and project evidence, not surname or place similarity alone; an archival abstract is evidence of its own contents, not a full transcription.
- Before creating files, classify each item separately as relevant, unrelated, or unresolved, and record the specific evidence or uncertainty behind the decision. A shared volume, archive citation, locality, institution, or general subject does not by itself make an item relevant to a target family or event. Evaluate each item's own participants, transaction, place, and relationship to the relevant event under `specs/facts.md`.
- Retain relevant items and genuinely unresolved items; explain what specific connection remains uncertain. Skip items whose described subject and participants are unrelated to the relevant families, events, and places. Do not label every item unresolved merely because an abstract might omit a connection, or treat missing evidence alone as proof that an uncertain connection is impossible. An item concerning the same institution or benefice may warrant review, but does not establish a family connection.

## Split and preserve

- Create one document JSON per retained historical document, even when several share a date. Set its historical `date` to the best supported precision permitted by the schema and use that date in its filename, following existing naming and suffix conventions. For an undated item use the schema's undated convention; never invent a date or overwrite a collision. A date range or uncertain dating must follow the schema and preserve its uncertainty.
- Preserve each retained item's original text and matching translation as faithful excerpts, including its item number and folio, together with the citation, URL, and any shared context necessary to interpret it. Keep the distinction between transcription and archival abstract. Do not rewrite source text or silently repair mismatches; flag incomplete or misaligned translations. Preserve relevant images, seals, labels, research, and other metadata only where applicable, without attributing collection-wide details to an individual item as established fact.
- Allocate existing facts, guesses, and other annotations to the item or items that support them. Preserve explicit dates and account for any changed inherited document date; do not copy a collection-level assertion indiscriminately. If an assertion, context, or annotation cannot be assigned safely, retain the relevant original material and report the ambiguity rather than losing or inventing evidence. Regenerate or omit stale generated `mention` lists according to the schema; do not copy collection-wide mentions to every output.
- Check references to the original path and update those that clearly refer to a specific split document. Do not guess at ambiguous references. Replace or remove the original collection only once all relevant or uncertain material and applicable metadata are preserved, and follow the repository's soft-deletion convention where appropriate. Avoid leaving an active duplicate collection that would double-count its split documents.

## Verify and report

Validate the JSON, run `python3 scripts/lint.py`, and review the diff, including original text, translations, citations, dates, and allocation of assertions. Account for every collection item as retained, skipped as unrelated, or unresolved. Report output filenames and dates, reasons for skipped items, unresolved dates or relevance, and any references or material requiring follow-up. Do not alter unrelated records or pre-existing user changes.
