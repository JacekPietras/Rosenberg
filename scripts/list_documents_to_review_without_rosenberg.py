#!/usr/bin/env python3
"""List review documents and show any mention of a Rosenberg place variant."""

import json
import re
from pathlib import Path

from place_names import resolve_place_names


def strings_in(value):
    """Yield string values recursively from a JSON document."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings_in(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings_in(item)


def rosenberg_patterns(places_file):
    places = resolve_place_names(json.loads(places_file.read_text(encoding="utf-8")))
    variations = next(
        place["variations"]
        for place in places
        if place.get("id") == "rosenberg-town"
    )
    names = "|".join(re.escape(name) for name in sorted(variations, key=len, reverse=True))
    name_pattern = re.compile(
        rf"(?<![\w])(?:{names})(?![\w])",
        re.IGNORECASE,
    )
    particle_name_pattern = re.compile(
        rf"(?<![\w])(?:von\.?|v\.?|de)\s+(?:{names})(?![\w])",
        re.IGNORECASE,
    )
    return name_pattern, particle_name_pattern


def mention_snippets(document, pattern):
    snippets = []
    for value in strings_in(document):
        for match in pattern.finditer(value):
            start = max(0, match.start() - 10)
            end = min(len(value), match.end() + 10)
            excerpt = value[start:end]
            if "\n" in excerpt or "\r" in excerpt:
                continue
            snippets.append("..." + excerpt + "...")
    return snippets


def main():
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    documents_dir = repo_root / "data" / "documents"
    places_file = repo_root / "data" / "places.json"
    name_pattern, particle_name_pattern = rosenberg_patterns(places_file)

    for path in sorted(documents_dir.glob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"Warning: could not read {path}: {error}")
            continue

        labels = document.get("label", [])
        if isinstance(labels, str):
            labels = [labels]
        if "to review" not in labels:
            continue
        values = list(strings_in(document))
        if any(particle_name_pattern.search(value) for value in values):
            continue

        snippets = mention_snippets(document, name_pattern)
        print(path.relative_to(repo_root))
        if snippets:
            for snippet in snippets:
                print(f"    {snippet}")
        elif not any(name_pattern.search(value) for value in values):
            print("    No Rosenberg")


if __name__ == "__main__":
    main()
