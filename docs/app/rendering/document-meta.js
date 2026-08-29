import { formatDate } from './dates.js';

export function documentTitle(doc, path) {
  return doc.book || formatDate(doc.date) || path.split('/').pop().replace(/\.json$/, '');
}

export function documentYear(doc) {
  const match = String(doc?.date || '').match(/^(\d{4})/);
  return match ? match[1] : null;
}

export function bookSortYear(doc, path) {
  const match = String(doc?.book || path || '').match(/\d{4}/);
  return match ? Number(match[0]) : -Infinity;
}
