export function createArmorialScreen({ state, escapeHtml, formatDate, imageMarkup, savePreferences, rerender }) {
  const normalize = (tag) => String(tag || '').trim().toLocaleLowerCase();

  function renderArmorialsPage() {
    const path = state.manifest.armorials;
    const document = path ? state.documents.get(path) : null;
    if (!document) return '<p>No armorials are available.</p>';
    const entries = document.entries || [];
    const selected = new Set(state.imageRegions || []);
    const regionNames = (entry) => (Array.isArray(entry.regions) ? entry.regions : []).map((region) => String(region?.name || '').trim()).filter(Boolean);
    const regions = [...new Set(entries.flatMap(regionNames))].sort((a, b) => a.localeCompare(b));
    const filters = regions.map((name) => ({ name, value: normalize(name) }));
    if (entries.some((entry) => !regionNames(entry).length)) filters.push({ name: 'Unknown', value: 'unknown' });
    const sidebar = filters.length ? `<aside class="seal-sidebar image-tag-sidebar" aria-label="Filter images by region"><nav>${filters.map(({ name, value }) => `<a href="#" class="${selected.has(value) ? 'selected' : ''}" data-image-region="${escapeHtml(value)}">${escapeHtml(name)}</a>`).join('')}</nav></aside>` : '';
    const cards = entries.map((entry, index) => ({ entry, index })).filter(({ entry }) => {
      if (!selected.size) return true;
      if (selected.has('unknown')) return !regionNames(entry).length;
      return regionNames(entry).some((name) => selected.has(normalize(name)));
    }).map(({ entry, index }) => {
      return `<article class="model-card armorial-card"><div class="model-info"><h2>${escapeHtml(entry.title || document.title)}</h2>${entry.date ? `<p class="entry-date">${escapeHtml(formatDate(entry.date))}</p>` : ''}</div>${entry.url ? imageMarkup(entry.url, [], { path, index, title: entry.title || document.title, focus: entry.focus, regions: entry.regions, showRegions: false }) : ''}</article>`;
    }).join('');
    return `<div class="image-tags-layout">${sidebar}<div class="models-grid armorial-grid">${cards || '<p class="status">No images match the selected regions.</p>'}</div></div>`;
  }

  function setupArmorialFilters() {
    document.querySelectorAll('[data-image-region]').forEach((link) => link.addEventListener('click', (event) => {
      event.preventDefault();
      const region = link.dataset.imageRegion;
      const selected = state.imageRegions || (state.imageRegions = []);
      if (selected.length === 1 && selected[0] === region) selected.length = 0;
      else state.imageRegions = [region];
      savePreferences();
      rerender();
    }));
  }

  return { renderArmorialsPage, setupArmorialFilters };
}
