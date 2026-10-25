#!/usr/bin/env python3
"""Find facts by person ID, person name, surname, or place.

Examples:
    python3 scripts/search_facts_by_name.py 'Eberhardi v. Roßenberg'
    python3 scripts/search_facts_by_name.py Eberhard
    python3 scripts/search_facts_by_name.py Rosenberg
    python3 scripts/search_facts_by_name.py vogt_zu_Lauda
    python3 scripts/search_facts_by_name.py vogt_zu_Lauda --direct
    python3 scripts/search_facts_by_name.py Boxberg
"""

import argparse
import json
import re
import unicodedata
from pathlib import Path
from place_names import resolve_place_names


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
        places = resolve_place_names(json.loads((ROOT / "data/places.json").read_text(encoding="utf-8")))
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


def person_id_name_tokens():
    """Map normalized people IDs to the name tokens they stand for."""
    try:
        people = json.loads((ROOT / "data/people.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result = {}
    for person in people:
        person_id = norm(person.get("id", ""))
        if person_id:
            result[person_id] = {
                norm(token)
                for token in re.findall(r"[^\W_]+", person.get("name", ""), flags=re.UNICODE)
                if norm(token)
            }
    return result


def fact_records(data_dir):
    """Yield stored facts and runtime seal facts, including nested research JSON."""
    for path in sorted(data_dir.rglob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        def visit(value, location=(), inherited_date=""):
            if isinstance(value, dict):
                date = value.get("date") or inherited_date
                images = value.get("img", [])
                if isinstance(images, dict):
                    images = [images]
                seen_seals = set()
                if isinstance(images, list):
                    for image in images:
                        if not isinstance(image, dict) or image.get("deleted") in (True, "true"):
                            continue
                        for seal in image.get("seals", []):
                            if not isinstance(seal, dict):
                                continue
                            person = seal.get("person", "")
                            if not isinstance(person, str):
                                continue
                            person = person.strip()
                            if not person or person == "?" or person.casefold() == "unknown" or person in seen_seals:
                                continue
                            seen_seals.add(person)
                            source = value.get("source") or value.get("title") or path.stem
                            if isinstance(source, list):
                                source = "; ".join(str(reference) for reference in source)
                            text = f"The seal of {person} is under document {source}."
                            metadata = " ".join(str(value.get(key, "")) for key in ("place", "title", "name", "label"))
                            yield path, location, f"seal-{len(seen_seals)}", date, source, text, metadata
                for key, child in value.items():
                    if key == "facts" and isinstance(child, list):
                        for fact_index, fact in enumerate(child, 1):
                            if isinstance(fact, dict):
                                text, fact_date = fact.get("text", ""), fact.get("date", date)
                            else:
                                text, fact_date = str(fact), date
                            if text:
                                metadata = " ".join(str(value.get(key, "")) for key in ("place", "title", "name", "label"))
                                yield path, location, fact_index, fact_date, value.get("source") or value.get("title", ""), text, metadata
                    elif isinstance(child, (dict, list)):
                        yield from visit(child, location + (key,), date)
            elif isinstance(value, list):
                for index, child in enumerate(value, 1):
                    yield from visit(child, location + (str(index),), inherited_date)

        yield from visit(document)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="person ID, full name, given name, surname, or place")
    parser.add_argument("--direct", action="store_true", help="return only facts containing the supplied person ID (requires a known person ID)")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data", help=argparse.SUPPRESS)
    args = parser.parse_args()

    groups = name_groups()
    aliases = alias_map(groups)
    id_names = person_id_name_tokens()
    people = json.loads((ROOT / "data/people.json").read_text(encoding="utf-8"))
    person_by_id = {norm(person.get("id", "")): person for person in people if person.get("id")}
    person_names = {norm(person.get("id", "")): person.get("name", "") for person in people if person.get("id") and person.get("name")}
    query_id = norm(args.name)
    selected_person = person_by_id.get(query_id)
    if args.direct and not selected_person:
        parser.error("--direct requires a known person ID from data/people.json")
    places = resolve_place_names(json.loads((ROOT / "data/places.json").read_text(encoding="utf-8")))
    place_variants = {norm(v) for place in places for v in place.get("variations", [])}
    query = [norm(token) for token in re.findall(r"[^\W_]+", args.name, flags=re.UNICODE)]
    particles = {
        norm(line.strip())
        for line in (ROOT / "data/nobiliary_particles.md").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    query = [token for token in query if token not in particles]
    if selected_person:
        query = [norm(token) for token in re.findall(r"[^\W_]+", selected_person.get("name", ""), flags=re.UNICODE)]
    if not query:
        parser.error("query must contain a name or surname")

    def equivalent(q, token):
        return q == token or token in aliases.get(q, {q})

    found = 0
    for path, location, fact_index, date, source, text, metadata in fact_records(args.data_dir):
        tokens = [norm(token) for token in re.findall(r"[^\W_]+", text, flags=re.UNICODE)]
        identifiers = [norm(identifier) for identifier in re.findall(r"\[([^]]+)\]", text)]
        tokens.extend(identifiers)
        for identifier in identifiers:
            tokens.extend(id_names.get(identifier, ()))
        metadata_tokens = [norm(token) for token in re.findall(r"[^\W_]+", metadata, flags=re.UNICODE)]
        is_place_query = not selected_person and len(query) == 1 and query[0] in place_variants
        if selected_person:
            id_match = query_id in identifiers
            name_match = all(any(equivalent(q, token) for token in tokens) for q in query)
            matched = id_match if args.direct else id_match or name_match
            uncertain = matched and not identifiers
        elif is_place_query:
            matched = any(equivalent(query[0], token) for token in tokens + metadata_tokens)
            uncertain = False
        else:
            matched = all(any(equivalent(q, token) for token in tokens + metadata_tokens) for q in query)
            uncertain = False
        if matched:
            found += 1
            prefix = f"[{date}] " if date else ""
            rendered = re.sub(
                r"\[([^]]+)\]",
                lambda match: (
                    f"{person_names.get(norm(match.group(1)), '')} [{match.group(1)}]"
                    if norm(match.group(1)) in person_names
                    else match.group(0)
                ),
                text,
            )
            if uncertain and selected_person:
                full_name = selected_person.get("name", "")
                rendered = re.sub(
                    rf"(?<![\w])({re.escape(full_name)})(?![\w])",
                    r"\1 [not recognised]",
                    rendered,
                    count=1,
                    flags=re.IGNORECASE,
                )
            print(f"{prefix}{rendered}")
    if not found:
        print("No matching facts found.")


if __name__ == "__main__":
    main()
