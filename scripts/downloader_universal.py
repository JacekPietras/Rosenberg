#!/usr/bin/env python3
"""Route an archive record URL to the downloader for its domain."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DOWNLOADERS = {
    "gda.bayern.de": "downloader_gda_bayern.py",
    "landesarchiv-bw.de": "downloader_landesarchiv.py",
    "regesta-imperii.de": "downloader_regesta_imperii.py",
    "archive.nrw.de": "downloader_archive_nrw.py",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", help="archive record URL")
    parser.add_argument(
        "downloader_args",
        nargs=argparse.REMAINDER,
        help="optional arguments forwarded to the selected downloader",
    )
    parser.add_argument("--list", action="store_true", help="list supported archive domains")
    args = parser.parse_args()

    if args.list:
        for domain in sorted(DOWNLOADERS):
            print(f"{domain}: {DOWNLOADERS[domain]}")
        return 0
    if not args.url:
        parser.error("supply an archive record URL (or use --list)")

    parsed = urlsplit(args.url)
    domain = (parsed.hostname or "").lower().rstrip(".").removeprefix("www.")
    if parsed.scheme not in {"http", "https"} or not domain:
        parser.error("URL must have an http or https scheme and a hostname")
    script_name = DOWNLOADERS.get(domain)
    if script_name is None:
        supported = ", ".join(sorted(DOWNLOADERS))
        print(f"Unsupported archive domain {domain!r}. Supported domains: {supported}", file=sys.stderr)
        return 2

    script_path = REPOSITORY_ROOT / "scripts" / script_name
    command = [sys.executable, str(script_path), args.url, *args.downloader_args]
    return subprocess.run(command, cwd=REPOSITORY_ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
