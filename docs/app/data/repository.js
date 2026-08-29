function dataUrl(path, location = window.location) {
  const parts = location.pathname.split('/').filter(Boolean);
  const owner = location.hostname.split('.')[0];
  const repository = parts[0];
  return location.hostname.endsWith('github.io')
    ? `https://raw.githubusercontent.com/${owner}/${repository}/main/${path}`
    : `../${path}`;
}

export function createRepository({ location = window.location, fetchFunction = window.fetch.bind(window) } = {}) {
  async function getText(path) {
    const response = await fetchFunction(`${dataUrl(path, location)}?v=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`${path}: ${response.status}`);
    return response.text();
  }

  return {
    getText,
    async getJson(path) {
      return JSON.parse(await getText(path));
    },
    async getRepositoryFiles() {
      if (!location.hostname.endsWith('github.io')) {
        const response = await fetchFunction(`/api/files?v=${Date.now()}`, { cache: 'no-store' });
        if (!response.ok) throw new Error(`Local file list: ${response.status}`);
        return response.json();
      }
      const parts = location.pathname.split('/').filter(Boolean);
      const owner = location.hostname.split('.')[0];
      const repository = parts[0];
      if (!owner || !repository) throw new Error('The viewer must be opened from a GitHub Pages project URL.');
      const response = await fetchFunction(`https://api.github.com/repos/${owner}/${repository}/git/trees/HEAD?recursive=1`);
      if (!response.ok) throw new Error(`Repository file listing: ${response.status}`);
      const tree = await response.json();
      return tree.tree
        .filter((item) => item.type === 'blob' && /^data\/(books|letters|notes)\/.*\.json$/.test(item.path))
        .map((item) => ({ path: item.path, version: item.sha }))
        .sort((left, right) => left.path.localeCompare(right.path));
    },
    async saveDocument(path, document) {
      const response = await fetchFunction('/api/save-document', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, document }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `Save failed (${response.status})`);
      return result;
    },
  };
}
