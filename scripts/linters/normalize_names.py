#!/usr/bin/env python3
"""Alphabetize given-name variants and groups in data/names.md."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent


def normalize(path):
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()
    output = []
    groups = []

    def flush_groups():
        groups.sort(key=lambda group: (group[0].casefold(), group[0]))
        output.extend(group[1] for group in groups)
        groups.clear()

    for line in lines:
        if line.startswith("#"):
            flush_groups()
            output.append(line)
            continue
        names, marker, comment = line.partition("//")
        forms = []
        seen_forms = set()
        for form in names.split(","):
            form = form.strip()
            if form and form.lower() not in seen_forms:
                forms.append(form)
                seen_forms.add(form.lower())
        if not forms:
            flush_groups()
            output.append(line)
            continue
        canonical = forms[0]
        variants = sorted(forms[1:], key=lambda form: (form.casefold(), form))
        normalized = ", ".join([canonical, *variants])
        if marker:
            normalized += f" //{comment}"
        groups.append((canonical, normalized))

    flush_groups()
    normalized = "\n".join(output) + ("\n" if original.endswith("\n") else "")
    if normalized != original:
        path.write_text(normalized, encoding="utf-8")
    return int(normalized != original)


if __name__ == "__main__":
    count = normalize(ROOT / "data" / "names.md")
    print(f"Normalized names.md ordering: {count} file(s).")
