import { imageCardMarkup, imageDisplayTitle } from '../rendering/images.js?v=6';
import { dateYear } from '../image-date-sort.js?v=2';
import { imageLabels } from '../image-labels.js';

export function createImageScreen({ state, escapeHtml, imageMarkup, titleMarkup = escapeHtml, savePreferences, rerender }) {
  const unknownRegionFilter = '__no_region__';
  const normalize = (tag) => String(tag || '').trim().toLocaleLowerCase();
  const driveFileId = (value) => {
    try {
      const url = new URL(String(value || ''), location.href);
      if (url.hostname === 'drive.google.com') return url.searchParams.get('id') || '';
      if (url.hostname.endsWith('googleusercontent.com')) return url.pathname.match(/\/d\/([^/=]+)/)?.[1] || '';
    } catch {}
    return '';
  };

  function renderImagesPage() {
    const path = state.manifest.images;
    const document = path ? state.documents.get(path) : null;
    if (!document) return '<p>No images are available.</p>';
    const entries = (document.entries || []).map((entry, index) => ({
      entry,
      index,
      year: dateYear(entry.date ?? entry.year),
      isDateRange: String(entry.date ?? entry.year ?? '').includes('-'),
    }))
      .sort((a, b) => {
        if (a.year === null && b.year !== null) return 1;
        if (a.year !== null && b.year === null) return -1;
        return (a.year ?? 0) - (b.year ?? 0) || Number(a.isDateRange) - Number(b.isDateRange) || a.index - b.index;
      });
    const selected = new Set(state.imageRegions || []);
    const labels = [...new Set(entries.flatMap(({ entry }) => imageLabels(entry)))];
    const regionNames = (entry) => [...new Set([
      ...(Array.isArray(entry.regions) ? entry.regions : []),
      ...(Array.isArray(entry.img) ? entry.img.flatMap((item) => Array.isArray(item?.regions) ? item.regions : []) : []),
    ].map((region) => String(region?.name || '').trim()).filter(Boolean))];
    const regions = [...new Set(entries.flatMap(({ entry }) => regionNames(entry)))].sort((a, b) => a.localeCompare(b));
    const regionFilters = regions.map((name) => ({ name, value: normalize(name) }));
    if (entries.some(({ entry }) => !regionNames(entry).length)) regionFilters.push({ name: 'Unknown', value: unknownRegionFilter });
    const renderFilters = (items) => items.map(({ name, value }) => `<a href="#" class="${selected.has(value) ? 'selected' : ''}" data-image-filter="${escapeHtml(value)}">${escapeHtml(name)}</a>`).join('');
    const sidebar = labels.length || regionFilters.length ? `<aside class="seal-sidebar image-tag-sidebar" aria-label="Filter images"><section aria-label="Labels"><nav>${renderFilters(labels.map((name) => ({ name, value: `label:${name}` })))}</nav></section><section aria-label="Regions"><nav>${renderFilters(regionFilters)}</nav></section></aside>` : '';
    const selectedLabels = [...selected].filter((value) => value.startsWith('label:'));
    const selectedRegions = [...selected].filter((value) => !value.startsWith('label:'));
    const matchingEntries = entries.filter(({ entry }) => {
      const matchesLabel = !selectedLabels.length || imageLabels(entry).some((label) => selectedLabels.includes(`label:${label}`));
      const names = regionNames(entry).map(normalize);
      const matchesRegion = !selectedRegions.length
        || (selectedRegions.includes(unknownRegionFilter) && !names.length)
        || names.some((name) => selectedRegions.includes(name));
      return matchesLabel && matchesRegion;
    });
    const labelMarkup = (entry, index) => {
      const badge = imageLabels(entry).map((label) => `<span class="image-label">${escapeHtml(label)}</span>`).join('');
      const editor = state.canEditDocuments
        ? `<button class="image-label-edit" type="button" data-edit-image-label="${index}" aria-label="Edit image labels" title="Edit labels"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4Z"/></svg></button>`
        : '';
      return badge || editor ? `<span class="image-label-controls">${badge}${editor}</span>` : '';
    };
    const cards = matchingEntries.map(({ entry, index }) => {
      const previewRegions = selectedRegions.length
        ? (entry.regions || []).filter((region) => selectedRegions.includes(normalize(region?.name)))
        : entry.regions;
      const previewFocus = selectedRegions.length ? previewRegions[0] : entry.focus;
      const label = labelMarkup(entry, index);
      const place = state.places.find((item) => item.id === entry.placeId);
      const placeMarkup = place?.name ? `<span class="image-place-name">${escapeHtml(place.name)}</span>` : '';
      const displayTitle = imageDisplayTitle(entry, document.title);
      if (entry.type === 'link' && entry.url) {
        const collectionImages = state.collectionImages?.[index] || [];
        const cover = entry.coverImage;
        const coverId = driveFileId(cover);
        const coverImageIndex = collectionImages.findIndex((item) => coverId && driveFileId(item?.src || item) === coverId);
        const coverImage = coverImageIndex >= 0 ? collectionImages[coverImageIndex] : null;
        const focus = coverImage?.cropFocus || coverImage?.regions?.[0] || entry.focus || entry.regions?.[0];
        const coverPicker = state.canEditDocuments
          ? `<button class="model-collection-cover-picker" type="button" data-open-collection-cover="${index}" aria-label="Edit cover for ${escapeHtml(entry.title || document.title)}" title="Edit cover"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 5 5 5M4 20l4.5-1 11-11a2.12 2.12 0 0 0-3-3l-11 11L4 20Z"/></svg><span>Cover</span></button><div class="model-collection-cover-images" hidden>${collectionImages.length ? imageMarkup(collectionImages, [], { path, index, title: entry.title || document.title, showRegions: false }) : ''}</div>`
          : '';
        return imageCardMarkup(entry, { focus, controls: coverPicker, label, place: placeMarkup, fallbackTitle: document.title, titleMarkup });
      }
      const media = entry.id ? undefined : entry.url
        ? imageMarkup(entry.url, [], { path, index, title: displayTitle, focus: previewFocus, regions: previewRegions, showRegions: false })
        : undefined;
      return imageCardMarkup(entry, { media, label, place: placeMarkup, fallbackTitle: document.title, titleMarkup });
    }).join('');
    return `<div class="image-tags-layout">${sidebar}<div class="models-grid armorial-grid">${cards || '<p class="status">No images match the selected regions.</p>'}</div></div>`;
  }

  function setupImageFilters() {
    document.querySelectorAll('[data-open-collection-cover]').forEach((button) => button.addEventListener('click', async (event) => {
      const entryIndex = Number(button.dataset.openCollectionCover);
      if (state.collectionImages?.[entryIndex]) return;
      event.preventDefault();
      event.stopPropagation();
      button.disabled = true;
      const entry = state.documents.get(state.manifest.images)?.entries?.[entryIndex];
      try {
        const response = await fetch(`/api/drive-folder?url=${encodeURIComponent(entry?.url || '')}`);
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Could not load Drive folder');
        if (!result.images?.length) throw new Error('No image files found in this Drive folder');
        state.collectionImages ||= {};
        state.collectionImages[entryIndex] = result.images;
        await rerender();
        document.querySelector(`[data-open-collection-cover="${entryIndex}"]`)?.click();
      } catch (error) {
        button.disabled = false;
        button.title = error.message;
        console.error('Could not load Drive folder images', error);
      }
    }));
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

  return { renderImagesPage, setupImageFilters };
}
