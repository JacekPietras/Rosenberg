#!/usr/bin/env python3
"""Normalize hidden places and validate visible places."""

import json
from pathlib import Path


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


if __name__ == "__main__":
    path = ROOT / "data" / "places.json"
    print(f"Normalized {normalize(path)} hidden place(s).")
    errors = visible_place_errors(json.loads(path.read_text(encoding="utf-8")))
    for error in errors:
        print(error)
    print(f"Checked visible places: {len(errors)} error(s).")
    raise SystemExit(bool(errors))
