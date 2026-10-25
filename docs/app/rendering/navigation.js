export function entryAnchor(path, index) {
  return `entry-${path.replace(/[^a-z0-9]+/gi, '-')}-${index}`;
}

export function documentNavigationUrl(path, index) {
  const params = new URLSearchParams();
  if (path.startsWith('data/documents/')) {
    params.set('tab', 'documents');
    params.set('record', path);
  } else {
    params.set('document', path);
  }
  return `?${params.toString()}#${entryAnchor(path, index)}`;
}
