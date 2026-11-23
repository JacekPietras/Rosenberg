#!/usr/bin/env python3
"""Normalize source citations and remove redundant descriptions."""

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent.parent
STRING = r'"(?:[^"\\]|\\.)*"'
SOURCE = re.compile(r'("source"\s*:\s*)(' + STRING + r'|\[\s*(?:' + STRING + r'\s*(?:,\s*' + STRING + r'\s*)*)?\])')


def normalize(path):
    original = path.read_text(encoding="utf-8")
    # Never change an invalid document or one with duplicate keys.
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    data = json.loads(original, object_pairs_hook=unique)

    def expected(value):
        if isinstance(value, dict):
            return {key: (clean(child) if key == "source" else expected(child))
                    for key, child in value.items()}
        if isinstance(value, list):
            return [expected(child) for child in value]
        return value

    def clean(value):
        if isinstance(value, str):
            return value.replace("{", "").replace("}", "")
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            items = [clean(item) for item in value]
            return [item for index, item in enumerate(items)
                    if not any(item in other and not re.fullmatch(re.escape(item) + r",? Verweisung(?: \d+)?", other) and (len(item) < len(other) or
                               (item == other and earlier < index))
                               for earlier, other in enumerate(items) if earlier != index)]
        return expected(value)

    def replace_source(match):
        raw = match.group(2)
        value = json.loads(raw)
        normalized = clean(value)
        if value == normalized:
            return match.group(0)
        if isinstance(value, str):
            replacement = json.dumps(normalized, ensure_ascii=False)
        else:
            tokens = list(re.finditer(STRING, raw))
            values = [clean(json.loads(token.group())) for token in tokens]
            kept = []
            for token, item in zip(tokens, values):
                if item in normalized and item not in [entry[0] for entry in kept]:
                    encoded = token.group() if json.loads(token.group()) == item else json.dumps(item, ensure_ascii=False)
                    kept.append((item, encoded))
            prefix = raw[:tokens[0].start()]
            suffix = raw[tokens[-1].end():]
            separator = raw[tokens[0].end():tokens[1].start()] if len(tokens) > 1 else ", "
            replacement = prefix + separator.join(encoded for _, encoded in kept) + suffix
        return match.group(1) + replacement

    updated = SOURCE.sub(replace_source, original)
    if json.loads(updated, object_pairs_hook=unique) != expected(data):
        raise ValueError(f"{path}: cannot safely normalize source fields")
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main():
    changed = 0
    failed = False
    for path in sorted((ROOT / "data").rglob("*.json")):
        try:
            changed += normalize(path)
        except (OSError, ValueError) as error:
            print(f"Could not normalize {path}: {error}")
            failed = True
    if changed:
        print(f"Normalized source citations in {changed} file(s).")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
