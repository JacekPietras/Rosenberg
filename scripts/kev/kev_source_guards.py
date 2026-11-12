"""Conservative source-text postfilters for historical family labels.

These rules only reject a model acceptance. They never create or change a
family prediction, and they do not infer people, kinship, or genealogy.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT_FIELDS = ("german", "latin", "english", "summary")
ELIGIBLE = ("franconian", "schenk", "monch", "rorschach", "czech")
FAMILY_ALIASES = (
    "Rosenberg", "Rosinberg", "Rosemberg", "Rossenberg", "Rosenbergs",
    "Roßenberg", "Rosenberch", "Rosemberch", "Rosenburgk", "Rusenberg",
    "Rosperg", "Rosenperg", "Rosenbergk", "Rosenerg", "Rosennberg",
    "Rosinberch", "Rosenberk", "Rozmberk", "Rožmberk", "Rossberg",
)
SWISS_PLACES = ("Zuckenriet", "Zukkenriet", "Herisau", "Berneck", "Rorschach")
GIVEN_SPECIAL = {
    "czech": ("Vok", "Wok", "Peter", "Petr", "Jost", "Jodok", "Jodocus", "Ulrich", "Vlrich", "Johann", "Johannes"),
    "swiss": ("Eglolf", "Egilolf", "Egloff", "Egli", "Eglin"),
}


def _alternation(values):
    return "(?:" + "|".join(sorted((re.escape(v) for v in values), key=len, reverse=True)) + ")"


def _given_names():
    names = {"male": set(), "female": set()}
    group = None
    for line in (ROOT / "data/names.md").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line == "# Men": group = "male"; continue
        if line == "# Women": group = "female"; continue
        if line.startswith("#") or not line or group is None: continue
        for name in line.split(","):
            name = name.strip()
            if name and not name.startswith("//"): names[group].add(name)
    return names


def _family_aliases():
    try:
        places = json.loads((ROOT / "data/places.json").read_text(encoding="utf-8"))
        entry = next(p for p in places if p.get("id") == "rosenberg-town")
        return tuple(dict.fromkeys((*entry.get("variations", ()), *FAMILY_ALIASES)))
    except (OSError, ValueError, StopIteration):
        return FAMILY_ALIASES


GIVEN = _given_names()
ROS = _alternation(_family_aliases())
ROS_PARTICLE = rf"(?:von|v\.?|de|zu|z[u]?|ze)\s+{ROS}"
PERSON_ROS = re.compile(rf"\b(?:{_alternation(GIVEN['male'] | GIVEN['female'])})\s+{ROS_PARTICLE}\b", re.I)
MONCH = re.compile(rf"\b(?:m[oöu]n(?:ch|ich)|muench|m[uü]nch)(?:in)?\s+{ROS_PARTICLE}\b", re.I)
SCHENK = re.compile(rf"\b(?:schenk\s+{ROS_PARTICLE}|schenk\s+von\s+rossberg)\b", re.I)
CZECH_VOK = re.compile(rf"\b(?:vok|wok|woko|wokko)\s+{ROS_PARTICLE}\b", re.I)
CZECH_HOUSE = re.compile(r"\b(?:house|haus|dynasty|dynastie|family|familie|geschlecht)\s+(?:of\s+|von\s+|de\s+)?ro[zž]mberk\b|\bro[zž]mberk(?:er)?\s+(?:house|haus|dynasty|dynastie|family|familie|geschlecht)\b|\b(?:herren|gebr[uü]der|familie)\s+(?:zu|von|de)\s+ro[zž]mberk\b", re.I)
SWISS_PERSON = re.compile(rf"\b{_alternation(GIVEN_SPECIAL['swiss'])}\s+{ROS_PARTICLE}\b", re.I)
SWISS_RORSCHACH = re.compile(rf"\b{_alternation(GIVEN_SPECIAL['swiss'])}\s+(?:von|v\.?|de)\s+rorschach\b", re.I)
PLACE_PATTERNS = [re.compile(rf"\b{re.escape(x)}\b", re.I) for x in SWISS_PLACES]
ST_GALLEN = re.compile(r"\bst\.?\s*gallen\b", re.I)


def source_text(doc: dict, *, remove_brackets: bool = False) -> str:
    parts = []
    for entry in doc.get("entries", []):
        for field in TEXT_FIELDS:
            value = entry.get(field)
            if isinstance(value, str) and value.strip():
                parts.append(value)
    text = unicodedata.normalize("NFKC", "\n".join(parts)).replace("ſ", "s")
    if remove_brackets:
        text = re.sub(r"\[[^\]]*\]", " ", text)
        # Regest apparatus and editorial indexes are not personal attestations.
        text = re.sub(r"(?im)^\s*(?:siegler(?:vermerk)?|sealer|seal|index|register|inserat|editorial note|rückvermerk)\s*[:.]?.*$", " ", text)
        text = re.sub(r"(?i)(?<=[.!?;\n])\s*[-–—]?\s*(?:siegler(?:vermerk)?|sealer|seal|index|register|inserat|editorial note|rückvermerk)\b[^.!?;\n]*", " ", text)
    return text


def _direct(pattern: re.Pattern, text: str) -> bool:
    """A question-marked attribution is too uncertain for an automatic label."""
    for match in pattern.finditer(text):
        if "?" not in text[max(0, match.start() - 12):min(len(text), match.end() + 12)]:
            return True
    return False


def evidence(doc: dict) -> dict[str, bool]:
    direct = source_text(doc, remove_brackets=True)
    ev = {key: False for key in ELIGIBLE}
    ev["schenk"] = _direct(SCHENK, direct)
    ev["monch"] = _direct(MONCH, direct)

    # Explicit South Bohemian identifiers only. A lone Wok, Rosenberg witness,
    # or Hohenfurt/Krumau place reference does not establish Rožmberk identity.
    multi_names = _alternation(GIVEN_SPECIAL["czech"][2:])
    for segment in re.split(r"[;\n.!?]+", direct):
        names = {m.casefold() for m in re.findall(rf"\b{multi_names}\b", segment, re.I)}
        if len(names) >= 2 and re.search(rf"{ROS_PARTICLE}", segment, re.I):
            ev["czech"] = True
            break
    ev["czech"] = ev["czech"] or _direct(CZECH_VOK, direct) or _direct(CZECH_HOUSE, direct)

    ev["rorschach"] = _direct(SWISS_PERSON, direct) or _direct(SWISS_RORSCHACH, direct)
    person_attributions = [m for m in PERSON_ROS.finditer(direct)
                          if "?" not in direct[max(0, m.start() - 12):min(len(direct), m.end() + 12)]]
    swiss_place_linked = False
    if person_attributions and not ST_GALLEN.search(direct):
        bounds = [0] + [m.end() for m in re.finditer(r"[;\n.!?]+", direct)] + [len(direct)]
        for pm in person_attributions:
            start = max((b for b in bounds if b <= pm.start()), default=0)
            end = min((b for b in bounds if b >= pm.end()), default=len(direct))
            local_people = [x for x in person_attributions if start <= x.start() < end]
            if len(local_people) == 1 and any(p.search(direct[start:end]) for p in PLACE_PATTERNS):
                swiss_place_linked = True
                break
    if not ev["rorschach"] and swiss_place_linked:
        ev["rorschach"] = True

    # A named-person ROS form is Franconian evidence unless that same clause
    # directly identifies the person with another branch. A separate bare-ROS
    # participant remains competing evidence and causes abstention downstream.
    generic_person = False
    boundaries = [0] + [m.end() for m in re.finditer(r"[;\n.!?]+", direct)] + [len(direct)]
    for m in PERSON_ROS.finditer(direct):
        start = max((b for b in boundaries if b <= m.start()), default=0)
        end = min((b for b in boundaries if b >= m.end()), default=len(direct))
        clause = direct[start:end]
        names = {x.casefold() for x in re.findall(rf"\b{_alternation(GIVEN_SPECIAL['czech'][2:])}\b", clause, re.I)}
        czech_group = len(names) >= 2 and re.search(ROS_PARTICLE, clause, re.I)
        if "?" in direct[max(0, m.start() - 12):min(len(direct), m.end() + 12)]:
            continue
        local_start, local_end = m.start() - start, m.end() - start
        branch_patterns = (MONCH, SCHENK, SWISS_PERSON, SWISS_RORSCHACH, CZECH_VOK, CZECH_HOUSE)
        overlaps_branch = any(x.start() < local_end and x.end() > local_start
                              for pattern in branch_patterns for x in pattern.finditer(clause))
        person_name = m.group(0).split()[0].casefold()
        same_person_swiss_place = swiss_place_linked and any(p.search(clause) for p in PLACE_PATTERNS)
        if not overlaps_branch and not (czech_group and person_name in names) and not same_person_swiss_place:
            generic_person = True
            break
    ev["franconian"] = generic_person or _direct(
        re.compile(rf"\b(?:herren|gebr[uü]der|familie)\s+(?:der|von)\s+{ROS}\b", re.I), direct)

    # Question-marked matches are held by _direct; bracketed editorial text is
    # removed before every positive match above. Titles, citations, images/seals,
    # and place fields never enter this source-text evidence pass.
    return ev


def accepted_prediction(doc: dict, row: dict, cfg: dict) -> tuple[bool, str]:
    """Return whether the probability-selected label survives source-evidence gates."""
    label = row.get("prediction")
    probs = row.get("probabilities")
    eligible = cfg.get("eligible_choices", ELIGIBLE)
    threshold = cfg.get("acceptance_threshold", .6)
    margin = cfg.get("minimum_margin", .15)
    if label not in eligible or not isinstance(probs, dict) or label not in probs:
        return False, "outside eligible family choices"
    ranked = sorted(probs.values(), reverse=True)
    if probs[label] < threshold:
        return False, "below probability threshold"
    if len(ranked) < 2 or ranked[0] - ranked[1] < margin:
        return False, "below minimum top-choice margin"
    ev = evidence(doc)
    if not ev.get(label, False):
        return False, f"no direct {label} source attribution"
    competitors = [name for name, present in ev.items() if present and name != label]
    if competitors:
        return False, "competing named branch evidence: " + ", ".join(competitors)
    return True, "direct source attribution passed"
