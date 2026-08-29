import { escapeHtml } from './html.js';
import { localImageName, imageRootForPath } from './image-paths.js';
import { sealAnnotationMarkup } from './seal-markup.js';

export function createImageRenderer({ location = window.location } = {}) {
  return function imageMarkup(value = '', legacySeals = [], context = {}) {
    const nodes = Array.isArray(value) ? value : [value];
    const parts = location.pathname.split('/').filter(Boolean);
    const owner = location.hostname.split('.')[0]; const repository = parts[0];
    const images = nodes.map((node, imageIndex) => {
      if (node && typeof node === 'object' && node.deleted === 'true') return '';
      const file = typeof node === 'object' && node !== null ? node.src : node;
      const seals = typeof node === 'object' && node !== null ? node.seals : imageIndex === 0 ? legacySeals : [];
      const fileName = String(file || '').trim(); if (!fileName) return '';
      let source; let fallback = '';
      if (/^https?:\/\//i.test(fileName)) {
        fallback = fileName; const localName = localImageName(fileName);
        if (!/\.(?:svg|png|jpe?g|gif|webp)$/i.test(localName)) return '';
        const imagePath = `${imageRootForPath(context.path)}/img/${localName}`;
        const encoded = imagePath.split('/').map((part) => encodeURIComponent(part)).join('/');
        source = location.hostname.endsWith('github.io') ? `https://raw.githubusercontent.com/${owner}/${repository}/main/${encoded}` : `../${encoded}`;
      } else {
        const fileParts = fileName.split('/');
        if (fileName.includes('\\') || fileParts.some((part) => !part || part === '.' || part === '..') || !/\.(?:svg|png|jpe?g|gif|webp)$/i.test(fileName)) return '';
        const imagePath = `${imageRootForPath(context.path)}/${fileName}`;
        const encoded = imagePath.split('/').map((part) => encodeURIComponent(part)).join('/');
        source = location.hostname.endsWith('github.io') ? `https://raw.githubusercontent.com/${owner}/${repository}/main/${encoded}` : `../${encoded}`;
      }
      const annotations = context.sealScreen ? '' : sealAnnotationMarkup(seals, escapeHtml);
      const fallbackAttribute = fallback ? ` data-fallback-src="${escapeHtml(fallback)}"` : '';
      const image = `<img src="${escapeHtml(source)}" alt="${escapeHtml(fileName)}" loading="lazy"${fallbackAttribute}>`;
      const edit = context.path && context.index !== null && context.index !== undefined ? ` data-document-path="${escapeHtml(context.path)}" data-entry-index="${context.index}" data-image-index="${context.imageIndex ?? imageIndex}"` : '';
      const link = `<a class="image-link" href="${escapeHtml(source)}" aria-label="Open image" data-image-src="${escapeHtml(source)}" data-image-fallback="${escapeHtml(fallback)}"${edit}>${image}</a>`;
      const content = context.crop ? `<span class="seal-crop is-loading" data-seal-x="${context.crop.x}" data-seal-y="${context.crop.y}" data-seal-size="${context.crop.size}" data-seal-width="${context.crop.width ?? 0}" data-seal-widening-rotation="${context.crop.wideningRotation || 0}" data-seal-rotation="${context.crop.rotation || 0}">${link}</span>` : annotations ? `<span class="annotated-image">${link}${annotations}</span>` : link;
      return `<figure class="entry-image">${content}</figure>`;
    }).filter(Boolean).join('');
    return images ? `<div class="entry-images">${images}</div>` : '';
  };
}
