#!/usr/bin/env python3
"""Check document JSON files and warn about entries without English text.

Examples:
    python3 scripts/validate_documents.py
    python3 scripts/validate_documents.py data/documents/1397-04-29.json
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def collect_files(paths):
    files = set()
    missing = []
    for path in paths:
        if path.is_dir():
            files.update(item.resolve() for item in path.rglob("*.json") if item.is_file())
        elif path.is_file():
            files.add(path.resolve())
        else:
            missing.append(path)
    return sorted(files), missing


def display_path(path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", type=Path, help="document JSON files or directories (default: data/documents)")
    args = parser.parse_args(argv)

    files, missing = collect_files(args.paths or [ROOT / "data/documents"])
    errors = 0
    warnings = 0

    for path in missing:
        print(f"{path}: error: input path does not exist or is not a file/directory")
        errors += 1

    for path in files:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            print(f"{display_path(path)}: error: cannot read JSON: {exc}")
            errors += 1
            continue

        if isinstance(document, dict) and document.get("deleted") == "true":
            continue

        entries = document.get("entries") if isinstance(document, dict) else None
        if not isinstance(entries, list):
            print(f"{display_path(path)}: error: expected an entries array")
            errors += 1
            continue

        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                print(f"{display_path(path)}#/entries/{index}: error: expected an entry object")
                errors += 1
                continue
            english = entry.get("english")
            if not isinstance(english, str) or not english.strip():
                print(f"{display_path(path)}#/entries/{index}/english: warning: missing English text")
                warnings += 1

    print(f"Checked documents: {len(files)} file(s), {warnings} warning(s), {errors} error(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
