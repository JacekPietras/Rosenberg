export function entryAnchor(path, index) {
  return `entry-${path.replace(/[^a-z0-9]+/gi, '-')}-${index}`;
}

export function documentNavigationUrl(path, index) {
  const params = new URLSearchParams();
  if (path.startsWith('data/letters/')) {
    params.set('tab', 'letters');
    params.set('letter', path);
  } else {
    params.set('document', path);
  }
  return `?${params.toString()}#${entryAnchor(path, index)}`;
}
