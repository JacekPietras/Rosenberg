#!/usr/bin/env python3
"""Move an image into the locally synced Google Drive objects folder."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


DESTINATION = Path(
    os.environ.get(
        "ROSENBERG_GOOGLE_DRIVE_OBJECTS",
        "/Users/jpietras/GoogleDrivePrivate/[Rycerskie]/Boxberg/objects",
    )
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move an image into the Boxberg objects Google Drive folder."
    )
    parser.add_argument("image", type=Path, help="Image file to add to Google Drive")
    args = parser.parse_args()

    source = args.image.expanduser()
    if not source.is_file():
        parser.error(f"image file does not exist: {source}")
    if not DESTINATION.is_dir():
        parser.error(f"Google Drive destination is not available: {DESTINATION}")

    target = DESTINATION / source.name
    if target.exists():
        parser.error(f"destination already contains a file named {source.name!r}")

    try:
        shutil.move(str(source), str(target))
    except OSError as exc:
        print(f"Could not move image: {exc}", file=sys.stderr)
        return 1

    print(f"Added to Google Drive folder: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
