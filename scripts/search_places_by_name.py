#!/usr/bin/env python3
"""List unique known places mentioned in facts matching a person's name."""

import argparse
from collections import Counter
import json
import re

from place_names import resolve_place_names
from search_facts_by_name import ROOT, main as search_facts


def places_in_text(text, places):
    """Find place variations, preferring longer matches at overlapping positions."""
    candidates = []
    for place in places:
        variations = place.get("variations", [])
        if not variations:
            continue
        for variation in variations:
            # Allow the same flexible whitespace around commas as the place loader.
            pattern = re.escape(variation)
            pattern = pattern.replace(r",\ ", r"\s*,\s*").replace(r"\ ", r"\s+")
            for match in re.finditer(r"(?<![^\W_])" + pattern + r"(?![^\W_])", text, re.IGNORECASE):
                candidates.append((match.start(), match.end(), variations[0]))
    selected = []
    for start, end, name in sorted(candidates, key=lambda item: (-(item[1] - item[0]), item[0])):
        if not any(start < other_end and end > other_start for other_start, other_end in selected):
            selected.append((start, end))
            yield name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="person ID, full name, given name, or surname")
    parser.add_argument("--count", action="store_true", help="show the number of matching fact records mentioning each place")
    parser.add_argument("--direct", action="store_true", help="only match facts containing the supplied person ID")
    args = parser.parse_args()

    places = resolve_place_names(json.loads((ROOT / "data/places.json").read_text(encoding="utf-8")))
    counts = Counter()

    def count_record(text):
        counts.update(set(places_in_text(text, places)))

    search_facts([args.name, *(["--direct"] if args.direct else [])], on_match=count_record)
    for name in sorted(counts, key=str.casefold):
        print(f"{name}: {counts[name]}" if args.count else name)


if __name__ == "__main__":
    main()
