# Agent Instructions

Read [README.md](README.md) before making structural changes.

## Data and fact rules

- Work with JSON files under `data/`; do not refer to deleted scripts, reports, Markdown letters, or `data/facts.json`.
- Preserve the smallest targeted edit, valid JSON, existing structure, source citations, source text, translations, and ISO date precision.
- Read [`rules/json-formats.md`](rules/json-formats.md) when working with data schemas or JSON structure.
- Read [`rules/facts.md`](rules/facts.md) before adding, changing, reviewing, or removing facts.

The linked rules are part of these instructions and should be followed when
the relevant task requires them.

There is no automated merge, sorting, queue, report, or temporary-file workflow. Add facts directly to the relevant JSON entry and review the diff.
