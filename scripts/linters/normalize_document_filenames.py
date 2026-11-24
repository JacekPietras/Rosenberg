#!/usr/bin/env python3
"""Warn about document filenames and normalize numeric suffixes."""

import re
import sys
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
FILENAME = re.compile(r"([0-9]{4}(?:-[0-9]{2}(?:-[0-9]{2})?)?)(?:_([0-9]+))?\.json\Z")


def normalize(directory):
    groups = defaultdict(list)
    warnings = 0
    for path in sorted(directory.glob("*.json")):
        if not path.is_file():
            continue
        match = FILENAME.fullmatch(path.name)
        if not match:
            print(f"{path}: warning: invalid document filename")
            warnings += 1
            continue
        date, suffix = match.groups()
        groups[date].append((path, suffix))

    for date, members in sorted(groups.items()):
        if not any(suffix is not None for _, suffix in members):
            continue
        members.sort(key=lambda item: (-1 if item[1] is None else int(item[1]), item[0].name))
        moves = [(path, directory / f"{date}_{index}.json")
                 for index, (path, _) in enumerate(members, 1)]
        moves = [(source, target) for source, target in moves if source != target]
        sources = {source for source, _ in moves}
        if any(target.exists() and target not in sources for _, target in moves):
            print(f"{directory / date}: error: cannot normalize filenames: destination exists")
            return warnings, False
        # Stage every source before assigning destinations, so overlapping names
        # never overwrite another document.
        if moves:
            with TemporaryDirectory(prefix=".document-renames-", dir=directory) as temporary:
                staged = []
                try:
                    for index, (source, target) in enumerate(moves):
                        temp = Path(temporary) / str(index)
                        source.rename(temp)
                        staged.append((source, target, temp))
                    for source, target, temp in staged:
                        temp.rename(target)
                except OSError:
                    for source, target, temp in reversed(staged):
                        if not temp.exists() and target.exists():
                            target.rename(temp)
                    for source, _, temp in staged:
                        if temp.exists():
                            temp.rename(source)
                    raise
            for source, target in moves:
                print(f"Renamed {source} -> {target}")
    return warnings, True


def main():
    warnings, success = normalize(ROOT / "data/documents")
    print(f"Checked document filenames: {warnings} warning(s).")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
