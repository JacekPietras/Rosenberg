#!/usr/bin/env python3
"""Move an image into Google Drive's synced objects folder and print its URL."""

from __future__ import annotations

import argparse
import os
import sqlite3
import shutil
import sys
import time
from pathlib import Path


DESTINATION = Path(
    os.environ.get(
        "ROSENBERG_GOOGLE_DRIVE_OBJECTS",
        "/Users/jpietras/GoogleDrivePrivate/[Rycerskie]/Boxberg/objects",
    )
)
DESTINATION_FOLDER_ID = "1IsXSTRMEPEmAAgwtbOq_hUa6P3ge-vbU"
DRIVEFS_ROOT = Path.home() / "Library/Application Support/Google/DriveFS"


def find_drive_file_id(filename: str) -> str | None:
    """Look up a synced file in Drive for desktop's local metadata index."""
    for database_path in DRIVEFS_ROOT.glob("*/mirror_metadata_sqlite.db"):
        try:
            database = sqlite3.connect(
                f"file:{database_path}?mode=ro", uri=True, timeout=1
            )
            try:
                rows = database.execute(
                    """
                    SELECT synced.cloud_id
                    FROM items AS item
                    JOIN stable_parents AS parent
                      ON parent.item_stable_id = item.stable_id
                    JOIN items AS folder
                      ON folder.stable_id = parent.parent_stable_id
                    JOIN stable_ids AS synced
                      ON synced.stable_id = item.stable_id
                    WHERE item.local_title = ?
                      AND folder.id = ?
                      AND item.trashed = 0
                      AND item.is_tombstone = 0
                    """,
                    (filename, DESTINATION_FOLDER_ID),
                ).fetchall()
            finally:
                database.close()
        except sqlite3.Error:
            continue

        ids = {row[0] for row in rows if row[0] and not row[0].startswith("local-")}
        if len(ids) == 1:
            return ids.pop()
        if len(ids) > 1:
            raise RuntimeError(
                f"More than one Drive file named {filename!r} exists in the objects folder"
            )
    return None


def wait_for_drive_file_id(filename: str, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while True:
        file_id = find_drive_file_id(filename)
        if file_id:
            return file_id
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Google Drive has not indexed {filename!r} after {timeout:g} seconds"
            )
        time.sleep(min(2, max(0, deadline - time.monotonic())))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Move an image into the Boxberg objects Google Drive folder and "
            "print its direct image URL."
        )
    )
    parser.add_argument("image", type=Path, help="Image file to add to Google Drive")
    parser.add_argument(
        "--timeout",
        type=float,
        default=180,
        help="seconds to wait for Drive for desktop to index the uploaded file (default: 180)",
    )
    args = parser.parse_args()

    source = args.image.expanduser()
    if not source.is_file():
        parser.error(f"image file does not exist: {source}")
    if not DESTINATION.is_dir():
        parser.error(f"Google Drive destination is not available: {DESTINATION}")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    target = DESTINATION / source.name
    if target.exists():
        parser.error(f"destination already contains a file named {source.name!r}")

    try:
        shutil.move(str(source), str(target))
    except OSError as exc:
        print(f"Could not move image: {exc}", file=sys.stderr)
        return 1

    try:
        file_id = wait_for_drive_file_id(target.name, args.timeout)
    except (TimeoutError, RuntimeError) as exc:
        print(
            f"Image was moved to {target}, but its Drive URL could not be retrieved: {exc}",
            file=sys.stderr,
        )
        return 1

    print(f"https://drive.google.com/thumbnail?id={file_id}&sz=w1600")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
