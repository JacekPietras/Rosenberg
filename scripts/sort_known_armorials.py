#!/usr/bin/env python3
"""Sort the known armorials table by the first year in its date column."""

import argparse
from pathlib import Path
import re

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data/known_armorials.md"
DATE = re.compile(r"(\d{4})(?:-(\d{4}))?\Z")


def sort_table(text: str) -> str:
    lines = text.splitlines(keepends=True)
    headers = [i for i, line in enumerate(lines)
               if line.startswith("|") and [cell.strip() for cell in line.split("|")][1:3] == ["Name of armorial", "Date"]]
    if len(headers) != 1:
        raise ValueError("Expected exactly one armorials table header")
    start = headers[0] + 2  # Preserve the header and Markdown separator.
    if start > len(lines) or not lines[start - 1].startswith("|"):
        raise ValueError("Missing table separator")
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1

    def sort_key(line: str) -> int:
        cells = line.split("|")
        if len(cells) < 4:
            raise ValueError("Malformed table row")
        date = cells[2].strip()
        if date == "—":
            return 10000
        match = DATE.fullmatch(date)
        if not match:
            raise ValueError(f"Invalid date: {date!r}")
        return int(match.group(1))

    rows = lines[start:end]
    # A row lacking a final newline cannot safely be moved before another row.
    if any(not row.endswith(('\n', '\r')) for row in rows):
        raise ValueError("Every table row must end with a newline")
    lines[start:end] = sorted(rows, key=sort_key)
    return "".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH,
                        help="Markdown file to sort (default: data/known_armorials.md)")
    args = parser.parse_args()
    try:
        with args.path.open(encoding="utf-8", newline="") as file:
            original = file.read()
        result = sort_table(original)
        if result != original:
            with args.path.open("w", encoding="utf-8", newline="") as file:
                file.write(result)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")


if __name__ == "__main__":
    main()
