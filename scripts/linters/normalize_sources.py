#!/usr/bin/env python3
"""Remove the redundant ', Verweisung' marker from source citations."""

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent.parent
STRING = r'"(?:[^"\\]|\\.)*"'
SOURCE = re.compile(r'("source"\s*:\s*)(' + STRING + r'|\[\s*(?:' + STRING + r'\s*(?:,\s*' + STRING + r'\s*)*)?\])')


def normalize(path):
    original = path.read_text(encoding="utf-8")
    # Never change an invalid document or one with duplicate keys.
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    data = json.loads(original, object_pairs_hook=unique)

    def expected(value):
        if isinstance(value, dict):
            return {key: (clean(child) if key == "source" else expected(child))
                    for key, child in value.items()}
        if isinstance(value, list):
            return [expected(child) for child in value]
        return value

    def clean(value):
        if isinstance(value, str):
            return value.replace(", Verweisung", "")
        if isinstance(value, list):
            return [clean(child) for child in value]
        return expected(value)
    updated, count = SOURCE.subn(
        lambda match: match.group(1) + match.group(2).replace(", Verweisung", ""),
        original,
    )
    if json.loads(updated, object_pairs_hook=unique) != expected(data):
        raise ValueError(f"{path}: cannot safely normalize source fields")
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main():
    changed = 0
    failed = False
    for path in sorted((ROOT / "data").rglob("*.json")):
        try:
            changed += normalize(path)
        except (OSError, ValueError) as error:
            print(f"Could not normalize {path}: {error}")
            failed = True
    if changed:
        print(f"Normalized source citations in {changed} file(s).")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
