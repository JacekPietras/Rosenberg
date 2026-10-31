#!/usr/bin/env python3
"""Expand 'von und zu NAME' in English text and split fact titles.

Preview changes by default; pass --apply to write them. Optional paths limit
the scan to JSON files or directories (default: source JSON under data/).
"""

import argparse
import difflib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
# A single name component, including accented letters, apostrophes and hyphens.
FORM = re.compile(r"\bvon und zu ([^\W\d_]+(?:[-’'][^\W\d_]+)*)", re.UNICODE)


def expand(value):
    return FORM.sub(lambda match: f"von {match[1]} zu {match[1]}", value)


def migrate_fact(fact):
    if not isinstance(fact, dict):
        return
    for field, title_field in (("person", "personTitle"), ("of", "ofTitle")):
        value = fact.get(field)
        if not isinstance(value, str):
            continue
        matches = list(FORM.finditer(value))
        if not matches:
            continue
        fact[field] = FORM.sub(lambda match: f"von {match[1]}", value)
        titles = fact.setdefault(title_field, [])
        if not isinstance(titles, list):
            raise ValueError(f"{title_field} is not an array")
        for match in matches:
            title = f"zu {match[1]}"
            if title not in titles:
                titles.append(title)
    # Names embedded in prose have no associated participant title field.
    for field in ("content", "circumstances"):
        if isinstance(fact.get(field), str):
            fact[field] = expand(fact[field])


def migrate(value):
    if isinstance(value, list):
        for item in value:
            migrate(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key == "english" and isinstance(item, str):
                value[key] = expand(item)
            elif key == "facts" and isinstance(item, list):
                for fact in item:
                    migrate_fact(fact)
            else:
                migrate(item)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="JSON files or directories")
    parser.add_argument("--apply", action="store_true", help="write the displayed changes")
    args = parser.parse_args(argv)
    paths = args.paths or [ROOT / "data" / name for name in ("documents", "books", "images", "notes")]
    files = set()
    for path in paths:
        if path.is_dir():
            files.update(path.rglob("*.json"))
        elif path.is_file() and path.suffix == ".json":
            files.add(path)
        else:
            parser.error(f"not a JSON file or directory: {path}")
    for path in sorted(files):
        # The tree is generated from source facts, not a source to migrate.
        if path.resolve() == (ROOT / "data" / "tree.json").resolve():
            continue
        original = path.read_text(encoding="utf-8")
        data = json.loads(original)
        # Avoid reformatting files that do not use the repository's standard style.
        canonical = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        migrate(data)
        updated = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if updated == canonical:
            continue
        if original != canonical:
            raise ValueError(f"{path}: nonstandard JSON formatting; refusing to reformat")
        print("".join(difflib.unified_diff(original.splitlines(keepends=True), updated.splitlines(keepends=True), fromfile=str(path), tofile=str(path))), end="")
        if args.apply:
            path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
