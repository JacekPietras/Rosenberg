# Agent Instructions

Read README.md before making structural changes.

## Data and fact rules

- Work with JSON files under `data/`.
- Preserve the smallest targeted edit, valid JSON, existing structure, source citations, source text, translations, and ISO date precision.
- Read `specs/json-formats.md` when working with data schemas or JSON structure.
- Read `specs/facts.md` before adding, changing, reviewing, or removing facts.

The linked rules are part of these instructions and should be followed when
the relevant task requires them.

There is no automated merge, sorting, queue, report, or temporary-file workflow. 
Add facts directly to the relevant JSON entry and review the diff.

## Family reconstruction

- Before changing `scripts/family_graph/` or `data/matching.json`, read `specs/family_graph_algorithm/`.
- Keep `specs/family_graph_algorithm/` in step with the code.

## Images

For downloading a selected image from an archive viewer, follow `archive-image-download` skill

Majority of images with references to Google Drive are available under https://drive.google.com/drive/folders/1IsXSTRMEPEmAAgwtbOq_hUa6P3ge-vbU?usp=drive_link
You are free to scan it and make direct references.

To add, read, or get a URL for an image in Google Drive, follow the `google-drive-objects` skill.
