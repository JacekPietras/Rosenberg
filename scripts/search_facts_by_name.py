#!/usr/bin/env python3
"""Find facts mentioning a person name, including spelling variants.

Examples:
    python3 scripts/search_facts_by_name.py 'Eberhardi v. Roßenberg'
    python3 scripts/search_facts_by_name.py Eberhard
    python3 scripts/search_facts_by_name.py Rosenberg
"""

import argparse
import json
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def norm(value):
    value = value.replace("ß", "ss").replace("ſ", "s")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def name_groups():
    groups = []
    for line in (ROOT / "data/names.md").read_text(encoding="utf-8").splitlines():
        names = [item.strip() for item in line.split(",")]
        names = [item for item in names if item and not item.startswith("//")]
        if names:
            groups.append({norm(name) for name in names if norm(name)})
    # Place variations can also appear in personal names, e.g. "de Rosinberg".
    try:
        places = json.loads((ROOT / "data/places.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        places = []
    for place in places:
        variations = place.get("variations", [])
        group = {norm(value) for value in variations if norm(value)}
        if len(group) > 1:
            groups.append(group)
    # Let a query by a person's name also find facts that have already been
    # disambiguated to their [people.json ID].
    try:
        people = json.loads((ROOT / "data/people.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        people = []
    for person in people:
        person_id = norm(person.get("id", ""))
        if not person_id:
            continue
        person_names = [person.get("name", ""), *person.get("titles", [])]
        for name in person_names:
            for token in re.findall(r"[^\W_]+", name, flags=re.UNICODE):
                token = norm(token)
                if token:
                    groups.append({token, person_id})
    return groups


def alias_map(groups):
    aliases = {}
    for group in groups:
        for variant in group:
            aliases.setdefault(variant, set()).update(group)
    return aliases


def fact_records(data_dir):
    """Yield every fact array in the data tree, including nested research JSON."""
    for path in sorted(data_dir.rglob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        def visit(value, location=(), inherited_date=""):
            if isinstance(value, dict):
                date = value.get("date") or inherited_date
                for key, child in value.items():
                    if key == "facts" and isinstance(child, list):
                        for fact_index, fact in enumerate(child, 1):
                            if isinstance(fact, dict):
                                text, fact_date = fact.get("text", ""), fact.get("date", date)
                            else:
                                text, fact_date = str(fact), date
                            if text:
                                yield path, location, fact_index, fact_date, value.get("source") or value.get("title", ""), text
                    elif isinstance(child, (dict, list)):
                        yield from visit(child, location + (key,), date)
            elif isinstance(value, list):
                for index, child in enumerate(value, 1):
                    yield from visit(child, location + (str(index),), inherited_date)

        yield from visit(document)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="full name, given name, or surname")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data", help=argparse.SUPPRESS)
    args = parser.parse_args()

    groups = name_groups()
    aliases = alias_map(groups)
    query = [norm(token) for token in re.findall(r"[^\W_]+", args.name, flags=re.UNICODE)]
    query = [token for token in query if token not in {"v", "von", "de", "van", "zu", "der", "die", "das"}]
    if not query:
        parser.error("query must contain a name or surname")

    def equivalent(q, token):
        return q == token or token in aliases.get(q, {q})

    found = 0
    for path, location, fact_index, date, source, text in fact_records(args.data_dir):
        tokens = [norm(token) for token in re.findall(r"[^\W_]+", text, flags=re.UNICODE)]
        tokens.extend(norm(identifier) for identifier in re.findall(r"\[([^]]+)\]", text))
        if all(any(equivalent(q, token) for token in tokens) for q in query):
            found += 1
            relative_path = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
            context = "/".join(location) or "root"
            print(f"{relative_path} | {context} | fact {fact_index}" + (f" | {date}" if date else "") + (f" | {source}" if source else ""))
            print(f"  {text}")
    if not found:
        print("No matching facts found.")


if __name__ == "__main__":
    main()
