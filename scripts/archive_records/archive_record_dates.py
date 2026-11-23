"""Parse date labels shared by historical archive catalogues."""
from __future__ import annotations

import html
import re
from datetime import date

MONTHS = {
    'januar': 1, 'jan': 1, 'februar': 2, 'feb': 2, 'febr': 2,
    'märz': 3, 'maerz': 3, 'mrz': 3, 'april': 4, 'apr': 4,
    'mai': 5, 'juni': 6, 'jun': 6, 'juli': 7, 'jul': 7,
    'august': 8, 'aug': 8, 'september': 9, 'sept': 9, 'sep': 9,
    'oktober': 10, 'okt': 10, 'november': 11, 'nov': 11,
    'dezember': 12, 'dez': 12,
}


def century_range(value: str) -> str | None:
    centuries = re.findall(r'(?<!\d)(\d{1,2})\s*\.\s*(?:Jh\.?|Jahrhundert)', value, re.I)
    if not centuries:
        return None
    first, last = int(centuries[0]), int(centuries[-1])
    if not 1 <= first <= last <= 99:
        raise ValueError(f'Invalid century: {value!r}')
    return f'{(first - 1) * 100 + 1:04d}-{last * 100:04d}'


def parse_catalogue_date(value: str) -> str:
    """Extract one date or a century range without inventing missing digits."""
    original = value
    value = html.unescape(value).strip()
    century = century_range(value)
    if century:
        return century
    match = re.search(r'(?<!\d)(\d{1,2})\.(\d{1,2})\.(\d{4})(?!\d)', value)
    if match:
        day, month, year = map(int, match.groups())
        return date(year, month, day).isoformat()
    match = re.search(r'(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)', value)
    if match:
        return date(*map(int, match.groups())).isoformat()
    match = re.search(r'(?<!\d)(\d{1,2})\.?\s+([A-Za-zÄÖÜäöüß]+)\.?\s+(\d{4})(?!\d)', value)
    if match and (month := MONTHS.get(match[2].casefold())):
        return date(int(match[3]), month, int(match[1])).isoformat()
    match = re.search(r'(?<!\d)(\d{4})\s+([A-Za-zÄÖÜäöüß]+)\.?(?:\s+(\d{1,2})(?!\d))?', value)
    if match and (month := MONTHS.get(match[2].casefold())):
        year, _, day = match.groups()
        return date(int(year), month, int(day)).isoformat() if day else f'{year}-{month:02d}'
    match = re.search(r'(?<!\d)(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?(?!\d)', value)
    if match:
        return '-'.join(part for part in match.groups() if part)
    match = re.search(r'(?<![\dXx])(\d{2,3})(?:\.{2,}|[Xx?…]+)(?![\dXx])', value)
    if match:
        return match[1] + 'X' * (4 - len(match[1]))
    raise ValueError(f'Could not determine the document date from catalogue label: {original!r}')
