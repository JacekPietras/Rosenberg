"""Resolve local building names against explicitly linked settlement variants."""

import re

GENERIC_BUILDING_NAMES = {"abbey", "monastery", "burg", "old burg", "schloss", "wasserschloss", "kirche", "evangelische kirche", "johanniskirche", "friedhofskapelle"}


def resolve_place_names(places):
    by_id = {place["id"]: place for place in places if place.get("id")}
    resolved = []
    for place in places:
        names = place.get("variations", [])
        if place.get("parent"):
            parent = by_id.get(place["parent"])
            if not parent or parent.get("category") not in ("city", "village") or parent.get("parent"):
                raise ValueError(f"Invalid settlement parent for {place['id']}")
            parent_names = sorted(parent["variations"], key=len, reverse=True)
            pattern = re.compile(r"(?<![^\W_])(?:" + "|".join(map(re.escape, parent_names)) + r")(?![^\W_])", re.I)
            combined_names = []
            for name in names:
                match = pattern.search(name)
                local_name = (re.sub(r"\s+", " ", f"{name[:match.start()]} {name[match.end():]}".strip(" ,\t\n\r"))
                              if match else name)
                if local_name:
                    settlement = parent["variations"][0]
                    combined = [f"{local_name} {settlement}", f"{settlement} {local_name}",
                                f"{local_name}, {settlement}", f"{settlement}, {local_name}"]
                    combined_names.extend([name, *combined] if match else
                                          combined if name.casefold() in GENERIC_BUILDING_NAMES else [*combined, name])
                else:
                    combined_names.append(name)
            names = combined_names
        names = list(dict.fromkeys(names))
        resolved.append({**place, "variations": names})
    return resolved
