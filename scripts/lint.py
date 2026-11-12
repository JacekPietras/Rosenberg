#!/usr/bin/env python3
"""Run the repository's data linters."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
LINTERS = Path(__file__).resolve().parent / "linters"
CHECKS = (
    "validate_documents.py",
    "migrate_von_und_zu.py",
    "validate_english_names.py",
    "validate_facts.py",
)


def main():
    failed = False
    for check in CHECKS:
        print(f"\n==> {check}", flush=True)
        result = subprocess.run([sys.executable, str(LINTERS / check)], cwd=ROOT)
        failed = failed or result.returncode != 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
