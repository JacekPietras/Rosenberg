#!/usr/bin/env python3
"""Find legacy and typed facts by person ID, name, title, surname, or place.

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


def name_groups(include_person_ids=True):
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
    for person in people if include_person_ids else []:
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


def typed_fact_text(fact, people_by_id, include_ids=True, unresolved_references=()):
    """Render fields directly; a matching name never identifies a participant."""
    def participant(field, with_titles=True):
        reference = fact.get(field, "")
        person = people_by_id.get(reference)
        name = person.get("name", reference) if person else reference
        if person and include_ids:
            name += f" [{reference}]"
        elif not person and reference in unresolved_references:
            name += " [not recognised]"
        titles = fact.get(field + "Title", []) if with_titles else []
        return ", ".join([name, *titles])

    kind = fact.get("type")
    if kind == "generic":
        status = " (deceased)" if fact.get("personDeceased") is True else ""
        return f"{participant('person')}{status}: {fact.get('content', '')}"
    if kind == "title":
        return f"{participant('person', False)} is designated {', '.join(fact.get('personTitle', []))}."
    if kind == "death":
        when = fact.get("diedOn")
        wording = f"died on {when}" if when else f"died before {fact.get('diedBefore')}"
        circumstances = fact.get("circumstances")
        return f"{participant('person')} {wording}" + (f" ({circumstances})" if circumstances else "") + "."
    if kind in {"parent", "sibling", "spouse", "kin"}:
        term = f" ({fact.get('term', '')})" if kind == "kin" else ""
        return f"{participant('person')} is {kind} of {participant('of')}{term}."
    return ""


def fact_records(data_dir, people_by_id=None):
    """Yield stored facts and runtime seal facts, including nested research JSON."""
    if people_by_id is None:
        people = json.loads((ROOT / "data/people.json").read_text(encoding="utf-8"))
        people_by_id = {person['id']: person for person in people if person.get('id')}
    for path in sorted(data_dir.rglob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        explicit_dates = bool({'books', 'notes'} & set(path.parts)) or (isinstance(document, dict) and 'book' in document)

        def visit(value, location=(), inherited_date=""):
            if isinstance(value, dict):
                date = "" if explicit_dates else value.get("date", inherited_date)
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
                            yield path, location, f"seal-{len(seen_seals)}", date, source, text, metadata, None
                for key, child in value.items():
                    if key == "facts" and isinstance(child, list):
                        for fact_index, fact in enumerate(child, 1):
                            if isinstance(fact, dict):
                                typed = fact if 'type' in fact else None
                                text = typed_fact_text(fact, people_by_id) if typed else fact.get("text", "")
                                fact_date = fact.get("date", date)
                            else:
                                typed = None
                                text, fact_date = str(fact), date
                            if text:
                                metadata = " ".join(str(value.get(key, "")) for key in ("place", "title", "name", "label"))
                                yield path, location, fact_index, fact_date, value.get("source") or value.get("title", ""), text, metadata, typed
                    elif isinstance(child, (dict, list)):
                        yield from visit(child, location + (key,), date)
            elif isinstance(value, list):
                for index, child in enumerate(value, 1):
                    yield from visit(child, location + (str(index),), inherited_date)

        yield from visit(document)


def main(argv=None, on_match=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="person ID, full name, given name, surname, or place")
    parser.add_argument("--direct", action="store_true", help="return only facts containing the supplied person ID (requires a known person ID)")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    groups = name_groups()
    aliases = alias_map(groups)
    typed_aliases = alias_map(name_groups(include_person_ids=False))
    id_names = person_id_name_tokens()
    people = json.loads((ROOT / "data/people.json").read_text(encoding="utf-8"))
    person_by_id = {norm(person.get("id", "")): person for person in people if person.get("id")}
    person_names = {norm(person.get("id", "")): person.get("name", "") for person in people if person.get("id") and person.get("name")}
    exact_people_by_id = {person['id']: person for person in people if person.get('id')}
    query_id = norm(args.name)
    selected_person = exact_people_by_id.get(args.name) or person_by_id.get(query_id)
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

    def matches_name(name):
        tokens = [norm(token) for token in re.findall(r"[^\W_]+", name, flags=re.UNICODE)]
        return all(any(q == token or token in typed_aliases.get(q, {q}) for token in tokens) for q in query)

    def emit_match(text):
        if on_match is None:
            print(text)
        else:
            on_match(text)

    found = 0
    for path, location, fact_index, date, source, text, metadata, typed in fact_records(args.data_dir, exact_people_by_id):
        # Typed identity comes only from exact field values, never generated text.
        if typed and selected_person:
            references = [typed[field] for field in ('person', 'of') if field in typed]
            id_match = selected_person['id'] in references
            name_match = any(matches_name(exact_people_by_id.get(ref, {}).get('name', ref)) for ref in references)
            if id_match or (not args.direct and name_match):
                found += 1
                prefix = f"[{date}] " if date else ""
                unresolved = [ref for ref in references if ref not in exact_people_by_id and matches_name(ref)]
                emit_match(prefix + typed_fact_text(typed, exact_people_by_id, unresolved_references=unresolved))
            continue
        search_text = typed_fact_text(typed, exact_people_by_id, include_ids=False) if typed else text
        tokens = [norm(token) for token in re.findall(r"[^\W_]+", search_text, flags=re.UNICODE)]
        identifiers = [] if typed else [norm(identifier) for identifier in re.findall(r"\[([^]]+)\]", text)]
        tokens.extend(identifiers)
        for identifier in identifiers:
            tokens.extend(id_names.get(identifier, ()))
        metadata_tokens = [norm(token) for token in re.findall(r"[^\W_]+", metadata, flags=re.UNICODE)]
        is_place_query = not selected_person and len(query) == 1 and query[0] in place_variants
        fact_aliases = typed_aliases if typed else aliases

        def equivalent(q, token):
            return q == token or token in fact_aliases.get(q, {q})
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
            rendered = text if typed else re.sub(
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
            emit_match(f"{prefix}{rendered}")
    if not found and on_match is None:
        print("No matching facts found.")


if __name__ == "__main__":
    main()
