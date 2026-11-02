"""Read data/names.md: comma-separated variant lines under `# Men`, `# Women` or other headers."""

GENDERS = {'men': 'man', 'women': 'woman'}


def name_groups(text):
    """Yield (forms, gender) per variant line; the first form is canonical, gender is 'man', 'woman' or None."""
    gender = None
    for line in text.splitlines():
        if line.startswith('#'):
            gender = GENDERS.get(line.lstrip('#').strip().casefold())
            continue
        forms = [form.strip() for form in line.split('//', 1)[0].split(',') if form.strip()]
        if forms:
            yield forms, gender
