export function sortByTitleDate(items) {
  return items
    .map((item, index) => ({ item, index, year: titleDateYear(item.title) }))
    .sort((a, b) => {
      if (a.year === null && b.year !== null) return 1;
      if (a.year !== null && b.year === null) return -1;
      return (a.year ?? 0) - (b.year ?? 0) || a.index - b.index;
    })
    .map(({ item }) => item);
}

export function titleDateYear(title) {
  const match = String(title || '').match(/\[(?:c\.\s*)?(\d{4})(?:-\d{4})?\]/i);
  return match ? Number(match[1]) : null;
}
