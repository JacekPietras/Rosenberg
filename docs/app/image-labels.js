export function imageLabels(entry) {
  const value = entry?.label;
  return [...new Set((Array.isArray(value) ? value : [value])
    .map((label) => String(label || '').trim())
    .filter(Boolean))];
}
