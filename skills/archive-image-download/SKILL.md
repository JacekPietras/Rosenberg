---
name: archive-image-download
description: Download a selected manuscript or armorial image from an archive viewer URL, including a requested folio, and extend the downloader when encountering a new viewer type.
---

# Archive image download

Run the project script from the repository root:

```text
python3 scripts/download_archive_image.py 'VIEWER_URL' --output /tmp/unique-image.jpg
python3 scripts/download_archive_image.py 'https://digi.vatlib.it/view/MSS_Vat.lat.10127' --folio '108 r' --output /tmp/vat_lat_10127_108r.jpg
```

Supports Internet Archive, DigiVatLib, BLB Karlsruhe, GNM, LOC RBC, and Findbuch.
`--resolve-only` prints image details without downloading. `--page` is a
one-based viewer sequence number; Internet Archive `nNNN` URLs use zero-based
scan leaves. Neither automatically identifies a manuscript folio. Vatican and
GNM folios are matched against catalog metadata. Select the requested page;
do not default to the manuscript cover.

Inspect the downloaded image with the image viewer before uploading. Check that
it is the requested leaf or spread. The script rejects non-image responses and
existing destination files; a successful download alone does not establish
historical identification, dating, or a license. LOC's fallback reports when it
used an image-service filename instead of the viewer API.

When the user requests Drive upload or catalog addition, follow
[google-drive-objects](../../.agents/skills/google-drive-objects/SKILL.md).
Check for an existing entry before uploading. Use the uploader's returned cloud
ID, then make the smallest direct edit to `data/images/images.json` under
`rules/json-formats.md`. Use `label: "armorial"` when requested. Preserve source
links and supported credits/usage terms; keep folios separate from titles. Do
not invent a folio or date from a scan index or filename. Validate JSON and
review the diff. The downloader itself neither uploads nor edits the catalog.

## Extend the downloader for a new viewer

When a supplied page type is unsupported, or an existing handler fails because
the viewer changed, **improve `scripts/download_archive_image.py` as part of the
task**. Do not leave the solution as a one-off shell download or instructions
that require repeating the investigation next time.

Inspect the page's HTML, viewer JavaScript, JSON endpoint, or IIIF manifest to
establish how its selected page maps to an image. Add a narrowly routed handler,
or fix the existing one, using actual source evidence. Prefer an observed or
documented full-size image endpoint. Preserve explicit page selection, timeouts,
image-response validation, and refusal to overwrite. Do not guess catalog IDs
or silently substitute the cover, thumbnail, or neighboring leaf.

Add focused regression coverage in `tests/test_download_archive_image.py` for
the new page mapping and relevant failure case, then run that test file and
exercise the real URL with a fresh temporary destination. Inspect the resulting
image before completing the requested upload/catalog work. Update this skill's
supported-viewer list when adding a handler. If access or page mapping cannot
be established, report the specific obstacle; do not claim a working handler or
fabricate a catalog entry.

Observed pitfalls are encoded in the handlers: Findbuch's `gtpc.php` uses the
selected path's array index, not the image filename number; GNM exposes image
URLs in its viewer JSON; BLB's social preview can point at a different leaf;
Vatican folios must come from its IIIF manifest. For Landesarchiv BW and
Bavarikon, inspect and reuse `scripts/download_landesarchiv.py` and
`scripts/parse_bavarikon.py` when extending support instead of duplicating their
specialized download logic.
