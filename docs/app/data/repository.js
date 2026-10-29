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
    revision: 0,
    getText,
    async isLocalServer() {
      try {
        const response = await fetchFunction('/api/local-server', { cache: 'no-store' });
        return response.ok;
      } catch {
        return false;
      }
    },
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
        .filter((item) => item.type === 'blob' && /^(?:data\/(?:books|documents|notes|images)\/.*\.json|data\/(?:people\.json|places\.json|names\.md)|scripts\/.*\.py)$/.test(item.path))
        .map((item) => ({ path: item.path, version: item.sha }))
        .sort((left, right) => left.path.localeCompare(right.path));
    },
    async saveDocument(path, document) {
      const requestBody = JSON.stringify({ path, document });
      const requestUrl = new URL('/api/save-document', location.href);
      const diagnostic = {
        path,
        requestUrl: requestUrl.href,
        pageUrl: location.href,
        payloadBytes: new Blob([requestBody]).size,
        browserOnline: navigator.onLine,
        startedAt: new Date().toISOString(),
      };
      console.info('Saving document', diagnostic);
      let response;
      try {
        response = await fetchFunction('/api/save-document', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: requestBody,
        });
      } catch (error) {
        let probe = 'probe failed';
        try {
          const probeResponse = await fetchFunction(`/api/local-server?diagnostic=${Date.now()}`, { cache: 'no-store' });
          probe = `probe returned HTTP ${probeResponse.status}`;
        } catch (probeError) {
          probe = `probe failed (${probeError?.name || 'Error'}: ${probeError?.message || String(probeError)})`;
        }
        console.error('Document save request failed before an HTTP response', { ...diagnostic, error, probe });
        const failure = new Error(`Save request failed (${error?.name || 'Error'}: ${error?.message || String(error)}). ${probe} at ${requestUrl.origin}; browser online: ${navigator.onLine}. Check server output for a POST /api/save-document entry.`);
        failure.cause = error;
        throw failure;
      }
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `Save failed (${response.status})`);
      this.revision += 1;
      return result;
    },
  };
}
