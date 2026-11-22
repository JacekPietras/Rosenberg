#!/usr/bin/env python3
"""List document and book filenames whose entries mention a supplied person.

Examples:
    python3 scripts/search_documents_by_name.py 'Eberhard von Rosenberg'
    python3 scripts/search_documents_by_name.py 'eberhard_jagstberg'

Searches each entry's generated ``mention`` list and the ``person`` and ``of``
participants in its ``facts`` and ``guesses``. Multiple matching entries in a
book are printed separately with their title or subheading.
"""

import argparse
import json
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def normalize(value):
    """Normalize names for case-, accent-, and punctuation-insensitive matching."""
    value = value.replace("ß", "ss").replace("ſ", "s")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def entry_matches(entry, query, people_by_id):
    def matches(value):
        value = str(value)
        person = people_by_id.get(value)
        return normalize(person.get("name", "") if person else value) == query

    mention = entry.get("mention", [])
    if isinstance(mention, list):
        for item in mention:
            if isinstance(item, dict) and matches(item.get("person", "")):
                return True

    for field in ("facts", "guesses"):
        assertions = entry.get(field, [])
        if not isinstance(assertions, list):
            continue
        for assertion in assertions:
            if not isinstance(assertion, dict):
                continue
            if any(matches(assertion.get(participant, ""))
                   for participant in ("person", "of")):
                return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="full name or person ID to search for")
    args = parser.parse_args()
    query = normalize(args.name)
    if not query:
        parser.error("name must contain at least one letter or digit")
    try:
        people = json.loads((ROOT / "data" / "people.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        people = []
    people_by_id = {person["id"]: person for person in people
                    if isinstance(person, dict) and person.get("id") and person.get("name")}

    for category in ("documents", "books"):
        for path in sorted((ROOT / "data" / category).glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            entries = record.get("entries", []) if isinstance(record, dict) else []
            for index, entry in enumerate(entries, start=1):
                if not isinstance(entry, dict) or not entry_matches(entry, query, people_by_id):
                    continue
                identifier = entry.get("title") or entry.get("subheading")
                if identifier:
                    print(f"{path.name} — entry {index}: {identifier}")
                else:
                    print(f"{path.name} — entry {index}")


if __name__ == "__main__":
    main()
