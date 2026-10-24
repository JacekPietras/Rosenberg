import { escapeHtml } from './html.js';
import { localImageName, imageRootForPath } from './image-paths.js';
import { sealAnnotationMarkup } from './seal-markup.js';

export function createImageRenderer({ location = window.location } = {}) {
  const regionMarkup = (regions = []) => regions.map((region) => {
    const { x, y, width, height } = region || {};
    if (![x, y, width, height].every((value) => Number.isFinite(Number(value))) || !String(region?.name || '').trim()) return '';
    return `<span class="image-region" style="left:${Number(x) * 100}%;top:${Number(y) * 100}%;width:${Number(width) * 100}%;height:${Number(height) * 100}%"><span>${escapeHtml(region.name)}</span></span>`;
  }).join('');
  return function imageMarkup(value = '', legacySeals = [], context = {}) {
    const nodes = Array.isArray(value) ? value : [value];
    const parts = location.pathname.split('/').filter(Boolean);
    const owner = location.hostname.split('.')[0]; const repository = parts[0];
    const images = nodes.map((node, imageIndex) => {
      if (node && typeof node === 'object' && node.deleted === 'true') return '';
      const file = typeof node === 'object' && node !== null ? node.src : node;
      const seals = typeof node === 'object' && node !== null ? node.seals : imageIndex === 0 ? legacySeals : [];
      const fileName = String(file || '').trim(); if (!fileName) return '';
      const alt = String(node && typeof node === 'object' ? node.name || context.title || fileName : context.title || fileName);
      let source; let fallback = '';
      if (/^https?:\/\//i.test(fileName)) {
        const driveUrl = new URL(fileName);
        if (driveUrl.hostname === 'drive.google.com') {
          if (!/\.(?:svg|png|jpe?g|gif|webp)$/i.test(alt) && !context.title) return '';
          const driveFileId = driveUrl.searchParams.get('id');
          if (driveUrl.pathname === '/thumbnail' && driveFileId) {
            fallback = fileName;
            source = `https://lh3.googleusercontent.com/d/${encodeURIComponent(driveFileId)}=${driveUrl.searchParams.get('sz') || 'w1600'}`;
          } else source = fileName;
        } else {
        fallback = fileName; const localName = localImageName(fileName);
        if (!/\.(?:svg|png|jpe?g|gif|webp)$/i.test(localName)) return '';
        const imagePath = `${imageRootForPath(context.path)}/img/${localName}`;
        const encoded = imagePath.split('/').map((part) => encodeURIComponent(part)).join('/');
        source = location.hostname.endsWith('github.io') ? `https://raw.githubusercontent.com/${owner}/${repository}/main/${encoded}` : `../${encoded}`;
        }
      } else {
        const fileParts = fileName.split('/');
        if (fileName.includes('\\') || fileParts.some((part) => !part || part === '.' || part === '..') || !/\.(?:svg|png|jpe?g|gif|webp)$/i.test(fileName)) return '';
        const imagePath = `${imageRootForPath(context.path)}/${fileName}`;
        const encoded = imagePath.split('/').map((part) => encodeURIComponent(part)).join('/');
        source = location.hostname.endsWith('github.io') ? `https://raw.githubusercontent.com/${owner}/${repository}/main/${encoded}` : `../${encoded}`;
      }
      const annotations = context.sealScreen ? '' : sealAnnotationMarkup(seals, escapeHtml);
      const sourceRegions = node && typeof node === 'object' ? node.regions : context.regions;
      const regions = context.showRegions === false ? '' : regionMarkup(sourceRegions);
      const fallbackAttribute = fallback ? ` data-fallback-src="${escapeHtml(fallback)}"` : '';
      const focus = (node && typeof node === 'object' ? node.cropFocus : context.focus)
        || sourceRegions?.[0];
      const focusAttributes = focus && [focus.x, focus.y, focus.width, focus.height].every((value) => Number.isFinite(Number(value)))
        ? ` data-focus-x="${Number(focus.x)}" data-focus-y="${Number(focus.y)}" data-focus-width="${Number(focus.width)}" data-focus-height="${Number(focus.height)}"`
        : '';
      const image = `<img src="${escapeHtml(source)}" alt="${escapeHtml(alt)}" loading="lazy" referrerpolicy="no-referrer"${fallbackAttribute}${focusAttributes}>`;
      const edit = context.path && context.index !== null && context.index !== undefined ? ` data-document-path="${escapeHtml(context.path)}" data-entry-index="${context.index}" data-image-index="${context.imageIndex ?? imageIndex}"` : '';
      const link = `<a class="image-link" href="${escapeHtml(source)}" aria-label="Open image" data-image-src="${escapeHtml(source)}" data-image-fallback="${escapeHtml(fallback)}"${edit}>${image}</a>`;
      const content = context.crop ? `<span class="seal-crop is-loading" data-seal-x="${context.crop.x}" data-seal-y="${context.crop.y}" data-seal-size="${context.crop.size}" data-seal-width="${context.crop.width ?? 0}" data-seal-widening-rotation="${context.crop.wideningRotation || 0}" data-seal-rotation="${context.crop.rotation || 0}">${link}</span>` : annotations || regions ? `<span class="annotated-image">${link}${annotations}${regions}</span>` : link;
      return `<figure class="entry-image">${content}</figure>`;
    }).filter(Boolean).join('');
    return images ? `<div class="entry-images">${images}</div>` : '';
  };
}

export function imageDisplayTitle(entry, fallback = '') {
  const date = entry.date ?? entry.year;
  return [entry.title || fallback, date ? `[${date}]` : ''].filter(Boolean).join(' ');
}

export function imageCardMarkup(entry, { media, focus, controls = '', label = '', place = '', fallbackTitle = '' } = {}) {
  const title = imageDisplayTitle(entry, fallbackTitle);
  const isCollection = entry.type === 'link' && entry.url;
  const heading = isCollection
    ? `<a class="model-collection-anchor" href="${escapeHtml(entry.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(title)}</a>`
    : escapeHtml(title);
  if (media === undefined) {
    if (isCollection) {
      const cover = entry.coverImage;
      focus ||= entry.focus || entry.regions?.[0];
      const focusAttributes = focus && [focus.x, focus.y, focus.width, focus.height].every((value) => Number.isFinite(Number(value)))
        ? ` data-focus-x="${Number(focus.x)}" data-focus-y="${Number(focus.y)}" data-focus-width="${Number(focus.width)}" data-focus-height="${Number(focus.height)}"`
        : '';
      media = cover ? `<a class="model-collection-preview-link" href="${escapeHtml(entry.url)}" target="_blank" rel="noopener noreferrer" aria-label="Open ${escapeHtml(title)} collection"><img class="model-collection-preview" src="${escapeHtml(cover)}" alt="${escapeHtml(title)}" referrerpolicy="no-referrer"${focusAttributes}></a>` : '';
    } else if (entry.id) {
      media = `<div class="model-frame"><iframe title="${escapeHtml(title)}" src="https://sketchfab.com/models/${encodeURIComponent(entry.id)}/embed?ui_theme=dark" allow="autoplay; fullscreen; xr-spatial-tracking" allowfullscreen loading="lazy"></iframe></div>`;
    } else if (entry.url) {
      media = createImageRenderer()(entry.url, [], { title });
    } else {
      media = entry.preview ? `<img class="model-collection-preview" src="${escapeHtml(entry.preview)}" alt="${escapeHtml(title)}" referrerpolicy="no-referrer">` : '';
    }
  }
  const modelLink = entry.sketchfabUrl ? `<a class="model-3d-link model-3d-overlay" href="${escapeHtml(entry.sketchfabUrl)}" target="_blank" rel="noopener noreferrer">3D</a>` : '';
  const cardClass = isCollection ? 'model-collection-link' : entry.id ? '' : 'armorial-card';
  const visualClass = isCollection ? 'model-collection-visual' : 'image-record-visual';
  return `<article class="model-card ${cardClass}"><div class="model-info"><h2>${heading}</h2></div><div class="${visualClass}">${media}${place}${modelLink}${controls}${label}</div></article>`;
}
