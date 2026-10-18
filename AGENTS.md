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

## Research skills

- For archival catalog searches by person or family name, read and follow [`archive-name-research`](.agents/skills/archive-name-research/SKILL.md).
- For uploading, reading, or making Drive URLs for images in the local objects folder, read and follow [`google-drive-objects`](skills/google-drive-objects/SKILL.md).

## Images

Majority of images with references to Google Drive are available under https://drive.google.com/drive/folders/1IsXSTRMEPEmAAgwtbOq_hUa6P3ge-vbU?usp=drive_link
You are free to scan it and make direct references.

To add a new image to Google Drive, run:

```text
python3 scripts/add_to_google_drive.py PATH_TO_IMAGE
```

The script moves the image into `/Users/jpietras/GoogleDrivePrivate/[Rycerskie]/Boxberg/objects`.
