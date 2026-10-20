# Two outward-facing swan heads or necks as shield charges: image-catalog audit

## Result

Within the current `data/images/images.json` catalog, I find one securely legible example beyond the image the user supplied from BSB Cod.icon. 309, fol. 51r: **BSB Cod.icon. 307, fol. 573**, in the lower-center shield on the page. The two long-necked bird figures bend outward, with the heads/beaks pointing away from each other. Their silhouettes are consistent with swan necks, but the monochrome sketch is not detailed enough to make species identification certain. The manuscript page itself gives no color evidence for this shield.

I found **no further confirmed outward-facing paired swan-neck shield charge in the other armorial page images currently represented in the catalog**. Several pages show paired swan necks as helmet crests, and are not matches to a charge on the shield. This conclusion is bounded by the project catalog: it does not amount to a folio-by-folio survey of every manuscript named there.

## Search and review method

I parsed all 153 records in `data/images/images.json`, inspecting labels, titles, dates, folios, source/image URLs, region names, and other stored fields. This catches records by image content metadata (including region names), not by label alone. The query finds two `goses` regions:

- Entry 28 (zero-based): Cod.icon. 309, fol. 51r.
- Entry 49 (zero-based): Cod.icon. 307, fol. 573.

I then built an image inventory using the `armorial` label wherever it occurred, including array-valued labels. This yielded 63 armorial records (58 scalar `armorial` labels plus five `armorial` labels in arrays). I opened the available image URLs for visual screening, checking whether any paired bird forms were on the shield/device itself and whether their heads faced outward. I also considered non-armorial records by title, label, and description for heraldic subject matter; these are principally monument, effigy, architecture, and object images. The cataloged monuments reviewed elsewhere in this project depict the Rosenberg swan pair as a crest above the striped shield, not as the shield charge at issue here.

## Inventory of matches and close candidates

| Catalog record | Manuscript / folio | Image | Assessment |
|---|---|---|---|
| Entry 28 (zero-based) | *Wappen besonders von deutschen Geschlechtern*, BSB Cod.icon. 309, fol. 51r | [Direct image](https://drive.google.com/thumbnail?id=1G5LgjkYsA9ghId4uyPJsP8F_KfyZgeCx&sz=w1600) · [Drive record](https://drive.google.com/file/d/1G5LgjkYsA9ghId4uyPJsP8F_KfyZgeCx/view) | **Confirmed visual motif.** Blue shield with two outward-facing swan necks/heads, as seen in the supplied image. The catalog region is named `goses`; that region name is not itself a heraldic identification. Bearer/name not established by this image-catalog audit. |
| Entry 49 (zero-based) | *Sammlung von Wappen aus verschiedenen, besonders deutschen Ländern*, BSB Cod.icon. 307, fol. 573 | [Direct image](https://drive.google.com/thumbnail?id=1YweIhi9Jr2Qfr2BQ8ZdL3E8zu4IEEO6v&sz=w1600) · [Drive record](https://drive.google.com/file/d/1YweIhi9Jr2Qfr2BQ8ZdL3E8zu4IEEO6v/view) | **Probable visual match; species uncertain.** The lower-center shield contains two outward-facing, long-necked bird-like heads. They may be swans, but the monochrome line drawing and simplified heads also leave room for another animal form. Do not count this as a securely identified swan coat without corroborating caption or another depiction. The caption below appears to begin “Stach…” in the supplied close-up context, but the name is not resolved here. |

## Similar but excluded forms

- The catalog includes a number of Rosenberg/Uissigheim armorial depictions with swan-neck pairs **in the crest**, above the familiar striped shield. These corroborate the crest tradition but do not meet the charge-on-shield criterion. For example, the page in entry 2 (Arlberg brotherhood material) shows pairs of swan heads in the crests over striped shields; the shield is not charged with two swan necks.
- Other pages show paired horns, plumes, animal heads, or abstract curved forms in crests. They were excluded unless the image showed two recognizable bird necks on the shield itself.
- Cod.icon. 307, fol. 573 is not treated as a secure second family example: it is a plausible image-level parallel, but both the bird species and the bearer's identity require verification.

## Scope and limits

This is a review of the **current project image records**, not all digitized armorials, and not every folio in any cited codex. Most armorial records are selected pages or cropped/page images, so an unlisted page elsewhere in the same manuscript could contain another example. Some image URLs are Google Drive thumbnails; image detail and color fidelity depend on the stored scan. The two examples above therefore establish one direct blue-field instance and one monochrome candidate in the catalog, while leaving the wider distribution unresolved.
