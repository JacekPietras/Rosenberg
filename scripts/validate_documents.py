#!/usr/bin/env python3
"""Validate document JSON files, warning and fixing simple document issues.

Examples:
    python3 scripts/validate_documents.py
    python3 scripts/validate_documents.py data/documents/1397-04-29.json
"""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_FIELDS = ("date", "place", "label", "transcribed", "deleted", "entries")
ENTRY_FIELDS = ("source", "url", "summary", "german", "latin", "english", "facts", "guesses", "img")
SOURCE_SUFFIX = " (http://www.klaster.vyssibrod.cz)"


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


def canonical_url(value):
    """Return a comparison key for URLs with known equivalent archive routes."""
    parts = urlsplit(value.strip())
    host = parts.hostname.lower() if parts.hostname else ""

    # GDA Bayern serves the same record through archive.xhtml and archive.jsf.
    # Their `id` parameter identifies the record; parent and fragment values
    # only control the viewer state.
    if host == "www.gda.bayern.de" and parts.path in {
        "/gvl/archive.xhtml",
        "/gvl/archive.jsf",
    }:
        record_id = parse_qs(parts.query).get("id", [None])[0]
        if record_id is not None:
            return ("gda.bayern.de", record_id)

    # Ignore fragments and normalize scheme/host casing for ordinary duplicate
    # links, while retaining paths and query parameters.
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def url_domain(value):
    """Return a normalized hostname for a URL, or None when it has no host."""
    try:
        host = urlsplit(value.strip()).hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.lower().rstrip(".")
    return re.sub(r"^www\d*\.", "", host)


def reorder_fields(value, field_order):
    """Order known fields first, preserving the order of unknown fields."""
    ordered_keys = [key for key in field_order if key in value]
    ordered_keys.extend(key for key in value if key not in field_order)
    return {key: value[key] for key in ordered_keys}


def order_document(document):
    changed = False
    reordered = reorder_fields(document, DOCUMENT_FIELDS)
    if reordered.get("place") in ("....", "o. O."):
        del reordered["place"]
        changed = True
    elif isinstance(reordered.get("place"), str):
        place = reordered["place"]
        if (place.startswith("(") and place.endswith(")")) or (
            place.startswith("[") and place.endswith("]")
        ):
            reordered["place"] = place[1:-1]
            changed = True
    changed |= list(reordered) != list(document)
    entries = reordered.get("entries")
    if isinstance(entries, list):
        ordered_entries = []
        for entry in entries:
            if isinstance(entry, dict):
                cleaned_entry = dict(entry)
                source = cleaned_entry.get("source")
                if isinstance(source, str) and SOURCE_SUFFIX in source:
                    cleaned_entry["source"] = source.replace(SOURCE_SUFFIX, "")
                    changed = True
                elif isinstance(source, list):
                    cleaned_source = [
                        item.replace(SOURCE_SUFFIX, "")
                        if isinstance(item, str) else item
                        for item in source
                    ]
                    if cleaned_source != source:
                        cleaned_entry["source"] = cleaned_source
                        changed = True
                urls = cleaned_entry.get("url")
                if isinstance(urls, list):
                    https_urls = {
                        urlunsplit(("https", *urlsplit(url)[1:]))
                        for url in urls
                        if isinstance(url, str) and urlsplit(url).scheme.lower() == "https"
                    }
                    filtered_urls = [
                        url for url in urls
                        if not (
                            isinstance(url, str)
                            and urlsplit(url).scheme.lower() == "http"
                            and urlunsplit(("https", *urlsplit(url)[1:])) in https_urls
                        )
                    ]
                    if len(filtered_urls) != len(urls):
                        cleaned_entry["url"] = filtered_urls
                        changed = True
                for field in ("facts", "guesses"):
                    if cleaned_entry.get(field) == []:
                        del cleaned_entry[field]
                        changed = True
                ordered_entry = reorder_fields(cleaned_entry, ENTRY_FIELDS)
                changed |= list(ordered_entry) != list(entry)
                ordered_entries.append(ordered_entry)
            else:
                ordered_entries.append(entry)
        reordered["entries"] = ordered_entries
    return reordered, changed


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

        if isinstance(document, dict):
            if document.get("deleted") in (True, "true"):
                continue
            labels = document.get("label", [])
            if isinstance(labels, str):
                labels = [labels]
            if isinstance(labels, list) and {"Czechia", "Schenk", "Mönch"}.intersection(labels):
                continue

        if isinstance(document, dict):
            document, reordered = order_document(document)
            if reordered:
                try:
                    original = path.read_text(encoding="utf-8")
                    trailing_newline = original.endswith("\n")
                    updated = json.dumps(document, ensure_ascii=False, indent=2)
                    if trailing_newline:
                        updated += "\n"
                    path.write_text(updated, encoding="utf-8")
                    print(f"{display_path(path)}: reordered document fields")
                except (OSError, UnicodeError) as exc:
                    print(f"{display_path(path)}: error: cannot reorder fields: {exc}")
                    errors += 1
                    continue
            for key in document:
                if key not in DOCUMENT_FIELDS and key != "abstract":
                    print(f"{display_path(path)}#/{key}: warning: unexpected document field {key!r}")
                    warnings += 1

        def warn_abstract(value, location):
            nonlocal warnings
            if isinstance(value, dict):
                for key, child in value.items():
                    child_location = f"{location}/{key.replace('~', '~0').replace('/', '~1')}"
                    if key == "abstract":
                        print(
                            f"{display_path(path)}#{child_location}: warning: "
                            "`summary` is expected; consult rules/json-formats.md"
                        )
                        warnings += 1
                    else:
                        warn_abstract(child, child_location)
            elif isinstance(value, list):
                for child_index, child in enumerate(value):
                    warn_abstract(child, f"{location}/{child_index}")

        warn_abstract(document, "")

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
            urls = entry.get("url")
            if isinstance(urls, str):
                urls = [urls]
            if isinstance(urls, list):
                seen_urls = set()
                seen_domains = set()
                for url_index, url in enumerate(urls):
                    if not isinstance(url, str):
                        continue
                    if urlsplit(url.strip()).hostname and urlsplit(url.strip()).hostname.lower() == "www2.landesarchiv-bw.de":
                        print(
                            f"{display_path(path)}#/entries/{index}/url/{url_index}: warning: "
                            "this is not a Landesarchiv BW permalink; use "
                            "`http://www.landesarchiv-bw.de/plink/...`"
                        )
                        warnings += 1
                    if url.strip().startswith("https://www.gda.bayern.de/gvl/archive.xhtml?id="):
                        print(
                            f"{display_path(path)}#/entries/{index}/url/{url_index}: warning: "
                            "use the GDA Bayern permalink form "
                            "`https://www.gda.bayern.de/gvl/document/...`"
                        )
                        warnings += 1
                    key = canonical_url(url)
                    if key in seen_urls:
                        print(
                            f"{display_path(path)}#/entries/{index}/url/{url_index}: "
                            "warning: URL duplicates an earlier URL in this entry"
                        )
                        warnings += 1
                    else:
                        seen_urls.add(key)

                    domain = url_domain(url)
                    if domain is not None:
                        if domain in seen_domains:
                            print(
                                f"{display_path(path)}#/entries/{index}/url/{url_index}: "
                                f"warning: multiple sources in this entry use the {domain} domain"
                            )
                            warnings += 1
                        else:
                            seen_domains.add(domain)

            english = entry.get("english")
            if not isinstance(english, str) or not english.strip():
                print(f"{display_path(path)}#/entries/{index}/english: warning: missing English text")
                warnings += 1
            if "latin" in entry and "german" in entry:
                print(
                    f"{display_path(path)}#/entries/{index}: warning: both `latin` and `german` "
                    "are present; check whether this is intentional"
                )
                warnings += 1
            if "date" in entry:
                print(
                    f"{display_path(path)}#/entries/{index}/date: warning: `date` belongs "
                    "on the document, not the entry"
                )
                warnings += 1
            for key in entry:
                if key not in ENTRY_FIELDS and key not in {"abstract", "date"}:
                    print(
                        f"{display_path(path)}#/entries/{index}/{key}: "
                        f"warning: unexpected entry field {key!r}"
                    )
                    warnings += 1

    print(f"Checked documents: {len(files)} file(s), {warnings} warning(s), {errors} error(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
