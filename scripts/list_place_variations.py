#!/usr/bin/env python3
"""Print canonical place names and their recognized spelling variations."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-churches",
        action="store_true",
        help="include places categorized as churches",
    )
    parser.add_argument(
        "places_file",
        nargs="?",
        type=Path,
        default=Path("data/places.json"),
        help="places JSON file (default: data/places.json)",
    )
    args = parser.parse_args()

    places = json.loads(args.places_file.read_text(encoding="utf-8"))
    for place in places:
        variations = place.get("variations", [])
        if len(variations) < 2:
            continue
        if not args.include_churches and place.get("category") == "church":
            continue
        print(f"{variations[0]}: {', '.join(variations[1:])}")


if __name__ == "__main__":
    main()
