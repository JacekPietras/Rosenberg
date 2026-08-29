export function localImageName(fileName) {
  if (!/^https?:\/\//i.test(fileName)) return fileName;
  try {
    const url = new URL(fileName);
    const original = url.searchParams.get('originalBilddatei');
    return (original || url.pathname).split('/').filter(Boolean).pop() || '';
  } catch {
    return '';
  }
}

export function imageRootForPath(path) {
  const match = String(path || '').match(/^data\/(books|letters|notes)\//);
  return match ? `data/${match[1]}` : 'data';
}
