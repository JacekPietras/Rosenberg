---
name: armorial-family-research
description: Find new armorial pages depicting a supplied family and verify them against viewable manuscript images. Use for heraldic image research, not text-only name searches.
---

# Armorial family research

Find additional, image-verifiable armorial pages for the requested family. Unless the user specifies otherwise, prioritize c. 1300–1450.

1. Read `AGENTS.md`, `README.md`, `rules/json-formats.md`, and `data/images/armorials.json`. Check relevant spellings in `data/names.md`. Compare armorial, shelfmark, folio/page, image ID, and family regions: a new page in a known armorial can still be a new find.
2. Search family-name variants and historic forms in digitized manuscript catalogs and library/archive collections. Treat indexes and transcriptions as leads; follow them to the scan, viewer, or IIIF manifest. Prefer primary catalog records and preserve uncertain dates and readings.
3. Inspect the actual page image. A candidate counts only when the image is viewable and the family can be identified from its label or clearly supported heraldic evidence. Confirm folio labels from the viewer or manifest; never infer them from neighboring image numbers. Record the evidence and link both the catalog record and visual page.
4. Report title, repository/shelfmark, date, folio, family form, working image/viewer link, evidence, and whether the page is new or already represented. State access and coverage limits; do not count text-only or inaccessible-image results as verified finds.

Do not edit the JSON unless asked. If asked, make a minimal valid change following `rules/json-formats.md`; add a named normalized region only when its bounds are reliable. Use a local filename only for an image stored in `data/images/`. Use a Google Drive thumbnail URL only when the individual file ID is known; a folder link is insufficient. For name-focused archive catalog searches, also follow [archive-name-research](../../.agents/skills/archive-name-research/SKILL.md).
