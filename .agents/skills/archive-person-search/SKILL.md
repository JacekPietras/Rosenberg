---
name: archive-person-search
description: Search archive catalogs for a named person, optionally including historical name variants, and import matching catalog records.
---

## Choose a search method

Apply these steps to each requested or relevant archive:

1. If the archive is listed below, use its script:
   - Arcinsys Hessen: `scripts/archive_search/search_arcinsys_hessen.py`
   - Bavarian State Archives (GDA Bayern): `scripts/archive_search/search_gda_bayern.py`
   - Landesarchiv Baden-Württemberg: `scripts/archive_search/search_landesarchiv_bw.py`
   - Landesarchiv Nordrhein-Westfalen: `scripts/archive_search/search_landesarchiv_nrw.py`
   - Monasterium: `scripts/archive_search/search_monasterium.py`
   - Regesta Imperii: `scripts/archive_search/search_regesta_imperii.py`
2. Otherwise, look for the archive in `data/notes/archives.md`. If found, propose making a search script for it.
3. If it is not in the notes, search the web for it. If found, propose making a search script for it. If not found, report that.

## Run searches

Run the selected script from the repository root, passing the full name as one argument:

```text
python3 scripts/archive_search/SCRIPT.py 'Eberhard von Rosenberg'
```

Always search a full person name: a given name together with a surname or territorial name, such as `Eberhard von Rosenberg`. If the full name cannot be determined, ask for the missing information. Search the supplied name first.

If the user requests variations, look up given-name variants in `data/names.md`. For a surname derived from a place, run `python3 scripts/list_place_variations.py 'PLACE'` to find its variants. Combine relevant given-name and surname variants into full-person queries, retaining appropriate connecting words such as `von`. Avoid duplicate or unnecessary queries, and report the variants actually searched.

When a name contains a nobiliary or territorial prefix, consider variants such as `von`, `v`, `v.`, `von.`, and `de`. Search variants as part of the full person name and report which forms were searched.

Scripts import catalog records to `data/documents/`. Review the results and imported changes: a catalog may match words separately, and a name match does not establish identity. Follow `rules/json-formats.md` for document JSON work and `rules/facts.md` before changing or reviewing facts. Report the archives and queries searched, relevant results and imports, and any unsupported records or incomplete searches.

Avoid rate limits and blocks. Respect script delays and session handling, reuse caches, and do not run concurrent searches against the same site. Stop on rate limits, access blocks, or repeated errors and report the obstacle; do not retry aggressively.

## Create a search script

Propose a reusable script when the archive is unsupported; do not claim it was searched if it was not. If implementation is requested or otherwise authorized, inspect the site's search and the existing scripts. Add a client under `scripts/archive_search/` that uses respectful request delays and defaults to importing records into `data/documents/`. Integrate `scripts/archive_anubis.py` if the site uses Anubis and the helper is appropriate. Verify the implementation with focused tests and the actual site when accessible, update the mapping above, and report any access or import limitations.
