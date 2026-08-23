# Rosenberg Research Data

This repository contains digitized historical sources about the von Rosenberg family and related Franconian/Odenwald families. Source text, English translation, and extracted facts are kept together in JSON files.

## Layout

```text
data/
├── books/       # Structured source books
├── letters/     # One JSON file per dated letter or document
└── variations.md # Historical name and place-name variants
.claude/         # Agent instructions and optional prompts
```

## Letter JSON

Each letter file normally has this shape:

```json
{
  "date": "1399-02-01",
  "entries": [
    {
      "source": "43 Nr. 5290",
      "german": "Original text",
      "english": "English translation",
      "facts": ["An explicit, atomic historical fact"]
    }
  ]
}
```

Dates use ISO 8601 precision available in the source (`YYYY`, `YYYY-MM`, or `YYYY-MM-DD`). Keep the existing precision; do not invent a day or month. `facts` belongs to the entry because it is supported by that entry’s source text and translation.

## Working with the data

There are no project scripts or automated import pipeline. To update a document, edit its JSON directly and preserve valid JSON, the existing source text, and the translation. Extract facts only from the document itself. Keep facts concise, atomic, explicit, and in English, while preserving historically meaningful German titles, names, and place names.

Use `data/variations.md` when a spelling needs to be recognized or normalized. Do not merge people merely because their names are similar. In particular, do not conflate Münch von Rosenberg with the primary von Rosenberg family.

Before committing, validate the edited JSON with any available JSON-aware editor or validator and review the diff manually.

## Data model and workflow

Rosenberg is a static research dataset. Source documents and translations are stored together, with extracted facts beside the supporting text. There is no separate facts database, report directory, synchronization service, or processing script.

Letter JSON documents have a document-level `date` and an `entries` array. Each entry contains an archival or bibliographic `source`, the original `german` text, its `english` translation, and explicit, atomic `facts` supported by that entry.

The editing workflow is deliberately direct: read the relevant JSON and source text, update the translation or facts in place, preserve source citations and date precision, then inspect the diff. A fact must be directly stated or unambiguously expressed in the source; do not infer relationships, identities, or dates.

Prioritize the von Rosenberg family and its documented network, including von Uissigheim and von Erligheim, their direct relatives, transaction partners, witnesses, offices, and relevant properties. Preserve German and Latin titles where they carry historical meaning, and use full names and epithets when needed to distinguish individuals. Exclude unrelated administrative detail and do not conflate Münch von Rosenberg with von Rosenberg.
