# Agent Instructions

Read [README.md](README.md) before making structural changes.

## Data rules

- Work with the JSON files under `data/`; do not refer to deleted scripts, reports, Markdown letters, or `data/facts.json`.
- Keep each document’s source text, English translation, and `facts` array together.
- Preserve ISO date precision (`YYYY`, `YYYY-MM`, or `YYYY-MM-DD`) and never invent missing date components.
- Preserve valid JSON and the existing structure. Make the smallest targeted edit.
- Every fact must be explicit, concise, atomic, and supported by the associated source text.
- Use full names, titles, and epithets when needed for disambiguation. Consult `data/variations.md` before normalizing names.
- Never infer a relationship or merge similarly named people. Münch von Rosenberg is distinct from the primary von Rosenberg family.

## Historical scope

Focus on the von Rosenberg family and clearly related people, places, offices, holdings, transactions, and relationships, including documented connections to von Uissigheim and von Erligheim. Skip unrelated detail and financial measurements unless they are essential to identifying an event.

## Editing and verification

When processing a document, read the complete JSON and its source text, update the relevant entry in place, and review the diff. Verify:

1. JSON parses successfully.
2. `date`, `entries`, and each entry’s `source`, `german`, `english`, and `facts` fields remain structurally intact.
3. Every fact is supported by the German source or is a faithful translation of it.
4. No duplicate, inferred, or unrelated facts were added.

There is no automated merge, sorting, queue, or report workflow. Do not create temporary fact files or a separate fact database.
