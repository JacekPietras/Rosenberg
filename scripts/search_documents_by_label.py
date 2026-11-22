#!/usr/bin/env python3
"""List document and book filenames containing an entry with a given label.

Example:
    python3 scripts/search_documents_by_label.py 'to review'
"""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label", help="label to search for (case-insensitive)")
    args = parser.parse_args()
    query = args.label.strip().casefold()
    if not query:
        parser.error("label must not be empty")

    for category in ("documents", "books"):
        for path in sorted((ROOT / "data" / category).glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            entries = record.get("entries", []) if isinstance(record, dict) else []
            if not isinstance(entries, list):
                entries = []
            for entry in [record, *entries]:
                if not isinstance(entry, dict):
                    continue
                labels = entry.get("label", [])
                if isinstance(labels, str):
                    labels = [labels]
                if isinstance(labels, list) and any(
                    isinstance(label, str) and label.strip().casefold() == query
                    for label in labels
                ):
                    print(path.name)
                    break


if __name__ == "__main__":
    main()
