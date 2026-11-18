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
    normalized_variations = 0
    normalized_hidden = 0
    for place in places:
        if not isinstance(place, dict):
            continue
        variations = place.get("variations")
        if isinstance(variations, list):
            seen = set()
            unique = []
            for variation in variations:
                key = " ".join(variation.split()).casefold() if isinstance(variation, str) else None
                if key is not None and key in seen:
                    normalized_variations += 1
                    continue
                if key is not None:
                    seen.add(key)
                unique.append(variation)
            place["variations"] = unique
        if place.get("showOnMap") is False:
            removed = False
            for field in ("lat", "lon", "category"):
                if field in place:
                    del place[field]
                    removed = True
            normalized_hidden += removed
    if normalized_variations or normalized_hidden:
        if original != canonical:
            raise ValueError(f"{path}: nonstandard JSON formatting; refusing to reformat")
        path.write_text(json.dumps(places, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized_variations, normalized_hidden


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


def duplicate_place_ids(places):
    """Return IDs used by more than one place record, with their indexes."""
    indexes = defaultdict(list)
    for index, place in enumerate(places):
        if isinstance(place, dict):
            place_id = place.get("id")
            if isinstance(place_id, str) and place_id.strip():
                indexes[place_id].append(index)
    return {
        place_id: record_indexes
        for place_id, record_indexes in indexes.items()
        if len(record_indexes) > 1
    }


if __name__ == "__main__":
    path = ROOT / "data" / "places.json"
    variations, hidden = normalize(path)
    if variations:
        print(f"Removed {variations} duplicate place variation(s).")
    print(f"Normalized {hidden} hidden place(s).")
    errors = visible_place_errors(json.loads(path.read_text(encoding="utf-8")))
    conflicts = variation_conflicts(json.loads(path.read_text(encoding="utf-8")))
    duplicate_ids = duplicate_place_ids(json.loads(path.read_text(encoding="utf-8")))
    for conflict in conflicts:
        details = "; ".join(f"{variation!r} in {owner}" for owner, variation in conflict)
        print(f"Warning: conflicting place variation: {details}")
    for place_id, indexes in duplicate_ids.items():
        records = ", ".join(f"data/places.json#/{index}" for index in indexes)
        print(f"Warning: duplicate place ID {place_id!r}: {records}")
    for error in errors:
        print(error)
    print(f"Checked visible places: {len(errors)} error(s).")
    raise SystemExit(bool(errors))
