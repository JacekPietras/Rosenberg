import { titleDateYear } from '../image-date-sort.js';

export function createArmorialScreen({ state, escapeHtml, formatDate, imageMarkup, savePreferences, rerender }) {
  const unknownRegionFilter = '__no_region__';
  const normalize = (tag) => String(tag || '').trim().toLocaleLowerCase();

  function renderArmorialsPage() {
    const path = state.manifest.images;
    const document = path ? state.documents.get(path) : null;
    if (!document) return '<p>No armorials are available.</p>';
    const entries = (document.entries || []).map((entry, index) => ({ entry, index, year: titleDateYear(entry.title) }))
      .sort((a, b) => {
        if (a.year === null && b.year !== null) return 1;
        if (a.year !== null && b.year === null) return -1;
        return (a.year ?? 0) - (b.year ?? 0) || a.index - b.index;
      });
    const selected = new Set(state.imageRegions || []);
    const labels = [...new Set(entries.map(({ entry }) => entry.label).filter(Boolean))];
    const regionNames = (entry) => (Array.isArray(entry.regions) ? entry.regions : []).map((region) => String(region?.name || '').trim()).filter(Boolean);
    const regions = [...new Set(entries.flatMap(({ entry }) => regionNames(entry)))].sort((a, b) => a.localeCompare(b));
    const regionFilters = regions.map((name) => ({ name, value: normalize(name) }));
    if (entries.some(({ entry }) => !regionNames(entry).length)) regionFilters.push({ name: 'Unknown', value: unknownRegionFilter });
    const renderFilters = (items) => items.map(({ name, value }) => `<a href="#" class="${selected.has(value) ? 'selected' : ''}" data-image-filter="${escapeHtml(value)}">${escapeHtml(name)}</a>`).join('');
    const sidebar = labels.length || regionFilters.length ? `<aside class="seal-sidebar image-tag-sidebar" aria-label="Filter images"><section aria-label="Labels"><nav>${renderFilters(labels.map((name) => ({ name, value: `label:${name}` })))}</nav></section><section aria-label="Regions"><nav>${renderFilters(regionFilters)}</nav></section></aside>` : '';
    const selectedLabels = [...selected].filter((value) => value.startsWith('label:'));
    const selectedRegions = [...selected].filter((value) => !value.startsWith('label:'));
    const matchingEntries = entries.filter(({ entry }) => {
      const matchesLabel = !selectedLabels.length || selectedLabels.includes(`label:${entry.label}`);
      const names = regionNames(entry).map(normalize);
      const matchesRegion = !selectedRegions.length
        || (selectedRegions.includes(unknownRegionFilter) && !names.length)
        || names.some((name) => selectedRegions.includes(name));
      return matchesLabel && matchesRegion;
    });
    const cards = matchingEntries.map(({ entry, index }) => {
      const previewRegions = selectedRegions.length
        ? (entry.regions || []).filter((region) => selectedRegions.includes(normalize(region?.name)))
        : entry.regions;
      const previewFocus = selectedRegions.length ? previewRegions[0] : entry.focus;
      const label = `<span class="image-label">${escapeHtml(entry.label || '')}</span>`;
      if (entry.label === 'effigy') return entry.id
        ? `<article class="model-card"><div class="image-record-visual"><div class="model-frame"><iframe title="${escapeHtml(entry.title)}" src="https://sketchfab.com/models/${encodeURIComponent(entry.id)}/embed?ui_theme=dark" allow="autoplay; fullscreen; xr-spatial-tracking" allowfullscreen loading="lazy"></iframe></div>${label}</div><div class="model-info"><h2>${escapeHtml(entry.title)}</h2></div></article>`
        : `<a class="model-card model-collection-link" href="${escapeHtml(entry.url)}" target="_blank" rel="noopener noreferrer"><div class="image-record-visual">${entry.preview ? `<img class="model-collection-preview" src="${escapeHtml(entry.preview)}" alt="" referrerpolicy="no-referrer">` : ''}${label}</div><div class="model-info"><h2>${escapeHtml(entry.title)}</h2></div></a>`;
      return `<article class="model-card armorial-card"><div class="model-info"><h2>${escapeHtml(entry.title || document.title)}</h2>${entry.date ? `<p class="entry-date">${escapeHtml(formatDate(entry.date))}</p>` : ''}</div><div class="image-record-visual">${entry.url ? imageMarkup(entry.url, [], { path, index, title: entry.title || document.title, focus: previewFocus, regions: previewRegions, showRegions: false }) : ''}${label}</div></article>`;
    }).join('');
    return `<div class="image-tags-layout">${sidebar}<div class="models-grid armorial-grid">${cards || '<p class="status">No images match the selected regions.</p>'}</div></div>`;
  }

  function setupArmorialFilters() {
    document.querySelectorAll('a[data-image-filter]').forEach((link) => link.addEventListener('click', (event) => {
      event.preventDefault();
      const region = link.dataset.imageFilter;
      const selected = new Set(state.imageRegions || []);
      if (selected.has(region)) selected.delete(region);
      else selected.add(region);
      state.imageRegions = [...selected];
      savePreferences();
      rerender();
    }));
  }

  return { renderArmorialsPage, setupArmorialFilters };
}
