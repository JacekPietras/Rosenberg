#!/usr/bin/env python3
"""Normalize hidden places and validate visible places."""

import json
from pathlib import Path
from collections import defaultdict


ROOT = Path(__file__).resolve().parent.parent.parent


def normalize(path):
    original = path.read_text(encoding="utf-8")

    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    places = json.loads(original, object_pairs_hook=reject_duplicates)
    canonical = json.dumps(places, ensure_ascii=False, indent=2) + "\n"
    count = 0
    for place in places:
        if isinstance(place, dict) and place.get("showOnMap") is False:
            removed = False
            for field in ("lat", "lon", "category"):
                if field in place:
                    del place[field]
                    removed = True
            count += removed
    if count:
        if original != canonical:
            raise ValueError(f"{path}: nonstandard JSON formatting; refusing to reformat")
        path.write_text(json.dumps(places, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return count


def visible_place_errors(places):
    errors = []
    for index, place in enumerate(places):
        if isinstance(place, dict) and place.get("showOnMap", True) is True:
            for field in ("category", "lat", "lon"):
                if field not in place or place[field] is None:
                    errors.append(f"data/places.json#/{index}: missing {field} for a visible place")
    return errors


def variation_conflicts(places):
    """Return variations assigned to more than one distinct place."""
    owners = defaultdict(set)
    for index, place in enumerate(places):
        if not isinstance(place, dict):
            continue
        variations = place.get("variations", [])
        if not isinstance(variations, list):
            continue
        owner = place.get("id", f"data/places.json#/{index}")
        for variation in variations:
            if isinstance(variation, str) and variation.strip():
                owners[" ".join(variation.split()).casefold()].add((owner, variation))
    conflicts = []
    for matches in owners.values():
        place_owners = {owner for owner, _ in matches}
        if len(place_owners) > 1:
            conflicts.append(sorted(matches, key=lambda match: (match[0], match[1].casefold())))
    return conflicts


if __name__ == "__main__":
    path = ROOT / "data" / "places.json"
    print(f"Normalized {normalize(path)} hidden place(s).")
    errors = visible_place_errors(json.loads(path.read_text(encoding="utf-8")))
    conflicts = variation_conflicts(json.loads(path.read_text(encoding="utf-8")))
    for conflict in conflicts:
        details = "; ".join(f"{variation!r} in {owner}" for owner, variation in conflict)
        print(f"Warning: conflicting place variation: {details}")
    for error in errors:
        print(error)
    print(f"Checked visible places: {len(errors)} error(s).")
    raise SystemExit(bool(errors))
