#!/usr/bin/env python3
"""Warn when a given-name form belongs to more than one group."""

from collections import defaultdict
from pathlib import Path
import sys

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_ROOT))
ROOT = Path(__file__).resolve().parents[2]


def main():
    groups_by_form = defaultdict(list)
    text = (ROOT / "data/names.md").read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        forms = [form.strip() for form in line.split("//", 1)[0].split(",") if form.strip()]
        line_forms = {}
        for form in forms:
            line_forms.setdefault(form.lower(), form)
        for form in line_forms.values():
            groups_by_form[form.lower()].append((form, line_number))

    conflicts = 0
    for occurrences in groups_by_form.values():
        if len(occurrences) < 2:
            continue
        descriptions = ", ".join(
            f"{form!r} on line {line_number}" for form, line_number in occurrences
        )
        print(f"Warning: name variant appears in multiple groups: {descriptions}")
        conflicts += 1
    print(f"Checked name variants: {conflicts} warning(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
