export function formatDate(date) {
  const range = String(date || '').split('/');
  if (range.length === 2) {
    const start = formatDate(range[0]);
    const end = formatDate(range[1]);
    return start !== range[0] && end !== range[1] ? `${start} – ${end}` : date;
  }

  const match = String(date || '').match(/^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/);
  if (!match) return date;

  const [, year, month, day] = match;
  if (!month) return year;
  const value = new Date(Date.UTC(Number(year), Number(month) - 1, day ? Number(day) : 1));
  const monthName = new Intl.DateTimeFormat('en-US', { month: 'long', timeZone: 'UTC' }).format(value);
  return day ? `${year}, ${monthName} ${Number(day)}` : `${year}, ${monthName}`;
}

export function dateSortValue(date) {
  const match = String(date || '').match(/^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?/);
  if (!match) return Infinity;
  return Number(`${match[1]}${match[2] || '01'}${match[3] || '01'}`);
}
