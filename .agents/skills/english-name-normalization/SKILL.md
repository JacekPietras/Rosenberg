---
name: english-name-normalization
description: Normalize personal and place names.
---

# English name normalization

Review English translations and facts text in JSON entries and normalize clear personal-name and place-name variants. Do not edit German source text, Latin source text or sentences, citations, dates, or other fields unless explicitly asked. Preserve Latin sentences verbatim even when they appear inside an English section; normalize names only in English prose, not within Latin text.

1. Read `../../../data/names.md`; 
2. do not read all of `places.json`. From the project root, run `!python3 scripts/list_place_variations.py` to list places that have variations, excluding churches while including castles.
2. In English entries, normalize a name or place to its listed standard form when the match is clear. Keep titles, distinguishing epithets, and meaningful territorial designations. Normalize particle variants such as `v.` to `von`; e.g. `Ebirhardus de Rossberg` → `Eberhard von Rosenberg`. Expand clear bracketed omissions such as `Ebe[r]hard` → `Eberhard`. When a known variant is explanatory in parentheses, remove the parenthetical variant: `Eberhard (Eberhardus)` → `Eberhard`.
3. Never infer identity from resemblance alone. Leave uncertain forms unchanged and note them for review. If an English entry establishes a legitimate variant not yet listed, add it to the matching person's line in `data/names.md` or the matching place's `variations` in `data/places.json`; preserve the canonical first item and JSON structure. Add only supported forms, and do not create a new canonical person or place from an uncertain match.
4. Make the smallest edits, preserve all other content, and review the diff. Ensure any changed JSON remains valid.
