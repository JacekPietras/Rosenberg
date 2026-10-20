---
name: armorial-family-research
description: Find new armorial pages depicting supplied family
---

# Armorial family research

Find additional, image-verifiable armorial pages for the requested family. Unless the user specifies otherwise, prioritize c. 1300–1450.

1. Read `../../../AGENTS.md`, `../../../README.md`, and `../../../rules/json-formats.md`. Do not read the full `images.json`; use this inline command from the project root to print the unique titles of entries labeled `armorial`:

   ```sh
   !python3 -c 'import json; from pathlib import Path; entries=json.loads(Path("data/images/images.json").read_text(encoding="utf-8"))["entries"]; print("\n".join(sorted({e["title"] for e in entries if "armorial" in ([e["label"]] if isinstance(e.get("label"), str) else e.get("label", [])) and e.get("title")})))'
   ```

   Check relevant spellings in `../../../data/names.md`. Use the concise title list to identify armorials already represented. For a possible match, inspect only relevant armorial records and compare shelfmark, folio/page, image ID, and family regions: a new page in a known armorial can still be a new find.
2. Search family-name variants and historic forms in digitized manuscript catalogs and library/archive collections. Treat indexes and transcriptions as leads; follow them to the scan, viewer, or IIIF manifest. Prefer primary catalog records and preserve uncertain dates and readings.
3. Inspect the actual page image. A candidate counts only when the image is viewable and the family can be identified from its label or clearly supported heraldic evidence. Confirm folio labels from the viewer or manifest; never infer them from neighboring image numbers. Record the evidence and link both the catalog record and visual page.
4. Report title, repository/shelfmark, date, folio, family form, working image/viewer link, evidence, and whether the page is new or already represented. State access and coverage limits; do not count text-only or inaccessible-image results as verified finds.

Do not edit the JSON unless asked. If asked, make a minimal valid change following `../../../rules/json-formats.md`. Use a local filename only for an image stored in `../../../data/images`. Use a Google Drive thumbnail URL only when the individual file ID is known; a folder link is insufficient. 