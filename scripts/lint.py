#!/usr/bin/env python3
"""Run the repository's data linters."""

from pathlib import Path
import re
import subprocess
import sys
import json
import argparse


ROOT = Path(__file__).resolve().parent.parent
LINTERS = Path(__file__).resolve().parent / "linters"
CHECKS = (
    "validate_documents.py",
    "migrate_von_und_zu.py",
    "validate_english_names.py",
    "validate_facts.py",
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all",
        action="store_true",
        help="include documents normally skipped by document validation",
    )
    args = parser.parse_args(argv)
    failed = False
    issues = 0
    normalized_names = 0
    for path in sorted((ROOT / "data").rglob("*.json")):
        duplicates = []

        def reject_duplicate_fields(pairs):
            fields = set()
            for field, value in pairs:
                if field in fields:
                    duplicates.append(field)
                fields.add(field)
            return dict(pairs)

        try:
            with path.open(encoding="utf-8") as source:
                json.load(source, object_pairs_hook=reject_duplicate_fields)
        except (OSError, json.JSONDecodeError):
            # The schema validators report unreadable or malformed JSON.
            continue
        for field in duplicates:
            print(f"Duplicate JSON field: {path.relative_to(ROOT)}: {field}")
            issues += 1
            failed = True
    for check in CHECKS:
        command = [sys.executable, str(LINTERS / check)]
        if args.all and check == "validate_documents.py":
            command.append("--all")
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines(keepends=True):
            if line.startswith("Checked documents:"):
                match = re.search(r", (\d+) warning\(s\), (\d+) error\(s\)\.", line)
                if match:
                    issues += int(match[1]) + int(match[2])
            elif line.startswith("Checked English name forms:"):
                match = re.search(r": (\d+) finding\(s\)\.", line)
                if match:
                    issues += int(match[1])
            elif line.startswith("Checked ") and " facts (" in line:
                match = re.search(r": (\d+) errors?, (\d+) warnings?\.", line)
                if match:
                    issues += int(match[1]) + int(match[2])
            elif line.startswith("Normalized "):
                match = re.search(r"Normalized (\d+) English name form\(s\)\.", line)
                if match:
                    normalized_names += int(match[1])
            else:
                sys.stdout.write(line)
        sys.stdout.write(result.stderr)
        failed = failed or result.returncode != 0
    print(f"Lint found {issues} issue(s); normalized {normalized_names} English name form(s).")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
