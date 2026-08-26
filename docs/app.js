const PREFERENCES_KEY = 'rosenberg-viewer-preferences';
const VALID_DISPLAY_MODES = new Set(['english', 'original']);

function normalizeDisplayMode(value) {
  if (VALID_DISPLAY_MODES.has(value)) return value;
  // Migrate preferences from the previous three-state control.
  return value === 'both' || value === 'german' || value === 'latin' ? 'original' : 'english';
}

function loadPreferences() {
  try {
    const preferences = JSON.parse(localStorage.getItem(PREFERENCES_KEY) || '{}');
    return {
      active: typeof preferences.active === 'string' ? preferences.active : null,
      place: typeof preferences.place === 'string' ? preferences.place : null,
      person: typeof preferences.person === 'string' ? preferences.person : null,
      letter: typeof preferences.letter === 'string' ? preferences.letter : null,
      letterLabels: Array.isArray(preferences.letterLabels) ? preferences.letterLabels : [],
      hiddenLetterLabels: Array.isArray(preferences.hiddenLetterLabels) ? preferences.hiddenLetterLabels : null,
      sealNames: Array.isArray(preferences.sealNames) ? preferences.sealNames : [],
      sealType: ['contrepalle', 'swans', 'helm', 'full', 'unknown'].includes(preferences.sealType) ? preferences.sealType : null,
      language: normalizeDisplayMode(preferences.language),
      showFacts: preferences.showFacts !== false,
      darkMode: preferences.darkMode !== false,
    };
  } catch {
    return { active: null, place: null, person: null, letter: null, letterLabels: [], hiddenLetterLabels: null, sealNames: [], sealType: null, language: 'english', showFacts: true, darkMode: true };
  }
}

function savePreferences() {
  try {
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify({ active: state.active, place: state.place, person: state.person, letter: state.letter, letterLabels: state.letterLabels, hiddenLetterLabels: state.hiddenLetterLabels, sealNames: state.sealNames, sealType: state.sealType, language: state.language, showFacts: state.showFacts, darkMode: state.darkMode }));
  } catch {
    // Preferences are optional; rendering should continue if storage is unavailable.
  }
}

const preferences = loadPreferences();
const state = { manifest: null, active: preferences.active, place: preferences.place, person: preferences.person, letter: preferences.letter, letterLabels: preferences.letterLabels, hiddenLetterLabels: preferences.hiddenLetterLabels, sealNames: preferences.sealNames, sealType: preferences.sealType, language: preferences.language, darkMode: preferences.darkMode, documents: new Map(), people: [], persons: [], places: [], personPattern: null, placePattern: null, snapshot: '', yearHighlightCleanup: null, sealHighlightCleanup: null, sealMarkerCleanup: null, lastRenderedLettersYear: null };
const $ = (selector) => document.querySelector(selector);
const REFRESH_INTERVAL = 30000;

const navigation = new URLSearchParams(location.search);
if (navigation.get('document') || navigation.get('tab') || navigation.get('letter')) { state.place = null; state.person = null; }
if (navigation.get('tab') === 'letters') state.active = 'letters';
if (navigation.get('document')) state.active = navigation.get('document');
if (navigation.get('letter')) state.letter = navigation.get('letter');
if (navigation.get('place')) { state.place = navigation.get('place'); state.person = null; }
if (navigation.get('person')) { state.person = navigation.get('person'); state.place = null; }

function applyTheme() {
  document.documentElement.dataset.theme = state.darkMode ? 'dark' : 'light';
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', state.darkMode ? '#0d0f11' : '#f5f7fa');
  const themeToggle = $('#theme-toggle');
  if (themeToggle) {
    themeToggle.setAttribute('aria-pressed', String(state.darkMode));
    themeToggle.setAttribute('aria-label', state.darkMode ? 'Switch to light mode' : 'Switch to dark mode');
    themeToggle.setAttribute('title', state.darkMode ? 'Switch to light mode' : 'Switch to dark mode');
  }
}

function updateLanguageControl() {
  const languageToggle = $('#language-toggle');
  if (!languageToggle) return;
  const label = state.language === 'original' ? 'English with original text' : 'English only';
  languageToggle.setAttribute('aria-label', `Language: ${label}`);
  languageToggle.setAttribute('title', `Language: ${label}. Click to change`);
}

function updateFactsControl() {
  const factsToggle = $('#facts-toggle');
  if (!factsToggle) return;
  const label = state.showFacts ? 'Hide facts' : 'Show facts';
  factsToggle.setAttribute('aria-label', label);
  factsToggle.setAttribute('title', label);
  factsToggle.setAttribute('aria-pressed', String(state.showFacts));
}

if (location.hash.startsWith('#year-')) history.replaceState(null, '', `${location.pathname}${location.search}`);

function applyMermaidTheme() {
  if (typeof mermaid === 'undefined') return;
  mermaid.initialize({ startOnLoad: false, theme: state.darkMode ? 'dark' : 'default', themeVariables: state.darkMode ? { background: '#11161c', primaryColor: '#1a1e23', primaryTextColor: '#e8edf2', primaryBorderColor: '#526274', lineColor: '#8eb7ff', secondaryColor: '#15181c', tertiaryColor: '#1b2c47' } : {} });
}

applyTheme();
applyMermaidTheme();

function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
}

function linkedMarkup(value = '') {
  const tokens = [];
  const token = (markup) => { const key = `\u0000${tokens.length}\u0000`; tokens.push(markup); return key; };
  let text = String(value);
  for (const { pattern, people } of state.personPattern || []) text = text.replace(pattern, (match) => {
    const normalizedMatch = match.replace(/\s*\([^)]*\)(?=\s(?:von|v\.|de|of)\s)/giu, '');
    const person = people.find((item) => item.names.some((name) => name.toLocaleLowerCase() === match.toLocaleLowerCase() || name.toLocaleLowerCase() === normalizedMatch.toLocaleLowerCase()));
    if (!person) return match;
    const query = encodeURIComponent(person.name);
    return token(`<a class="person-link" href="?person=${query}">${match}</a>`);
  });
  if (state.placePattern) text = text.replace(state.placePattern, (match) => {
    const place = state.places.find((item) => item.names.some((name) => name.toLocaleLowerCase() === match.toLocaleLowerCase()));
    if (!place) return match;
    const query = encodeURIComponent(place.name);
    return token(`<a class="place-link" href="?place=${query}">${match}</a>`);
  });
  return text.replace(/\u0000(\d+)\u0000/g, (match, index) => tokens[Number(index)] ?? match);
}

function inlineMarkup(value = '') {
  const tokens = [];
  const token = (markup) => { const key = `\u0000${tokens.length}\u0000`; tokens.push(markup); return key; };
  let text = escapeHtml(value).replace(/\[\[([^\]]+)\]\]\((https?:\/\/[^)]+)\)/g, (_, label, url) => token(`<a href="${url}" target="_blank" rel="noreferrer">${linkedMarkup(label)}</a>`));
  text = linkedMarkup(text).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  return text.replace(/\u0000(\d+)\u0000/g, (match, index) => tokens[Number(index)] ?? match);
}

function parsePlaces(markdown) {
  return String(markdown).split('\n').map((line) => line.replace(/\/\/.*$/, '').trim()).filter(Boolean).map((line) => {
    const names = line.split(',').map((name) => name.trim()).filter(Boolean);
    return { name: names[0], names: [...new Set(names)] };
  });
}

function buildPlacePattern(places) {
  const names = [...new Set(places.flatMap((place) => place.names))].sort((left, right) => right.length - left.length).map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  return names.length ? new RegExp(`(?<![\\p{L}\\p{N}])(?:${names.join('|')})(?![\\p{L}\\p{N}])`, 'giu') : null;
}

function parsePeople(markdown, namesMarkdown, places) {
  const namesByCanonical = new Map(String(namesMarkdown).split('\n').map((line) => line.replace(/\/\/.*$/, '').trim()).filter(Boolean).map((line) => {
    const names = line.split(',').map((name) => name.trim()).filter(Boolean);
    return [names[0].toLocaleLowerCase(), [...new Set(names)]];
  }));
  const allNameVariants = [...new Set([...namesByCanonical.values()].flat())].sort((left, right) => right.length - left.length);
  return String(markdown).split('\n').map((line) => line.replace(/\/\/.*$/, '').trim()).filter(Boolean).map((line) => {
    const separatorMatch = [...line.matchAll(/ (?:von|v\.|de|of) /gi)].pop();
    const name = separatorMatch ? line.slice(0, separatorMatch.index) : line;
    const placeName = separatorMatch ? line.slice(separatorMatch.index + separatorMatch[0].length) : '';
    const baseName = allNameVariants.find((candidate) => name.toLocaleLowerCase() === candidate.toLocaleLowerCase() || name.toLocaleLowerCase().startsWith(`${candidate.toLocaleLowerCase()} `));
    const nameAddition = baseName ? name.slice(baseName.length) : '';
    const nameAdditions = /^ d\. ?Ä\.$/i.test(nameAddition)
      ? [' d. Ä.', ' d.Ä.']
      : nameAddition
        ? [nameAddition]
        : ['', ' d. Ä.', ' d.Ä.', ' the Elder', ' der Ältere'];
    const nameVariants = (namesByCanonical.get(baseName?.toLocaleLowerCase()) || [baseName || name]).flatMap((nameVariant) => nameAdditions.map((addition) => `${nameVariant}${addition}`));
    const place = places.find((item) => item.names.some((candidate) => placeName.toLocaleLowerCase() === candidate.toLocaleLowerCase() || placeName.toLocaleLowerCase().startsWith(`${candidate.toLocaleLowerCase()} `)));
    const placeBase = place?.names.find((candidate) => placeName.toLocaleLowerCase() === candidate.toLocaleLowerCase() || placeName.toLocaleLowerCase().startsWith(`${candidate.toLocaleLowerCase()} `));
    const fallbackPlaceBase = allNameVariants.find((candidate) => placeName.toLocaleLowerCase() === candidate.toLocaleLowerCase() || placeName.toLocaleLowerCase().startsWith(`${candidate.toLocaleLowerCase()} `));
    const placeAddition = (placeBase || fallbackPlaceBase) ? placeName.slice((placeBase || fallbackPlaceBase).length) : '';
    const placeAdditions = /^ d\. ?Ä\.$/i.test(placeAddition)
      ? [' d. Ä.', ' d.Ä.']
      : /^, (?:Knight|Ritter)$/i.test(placeAddition)
        ? [', Knight', ', Ritter']
        : placeAddition
          ? [placeAddition]
          : ['', ' d. Ä.', ' d.Ä.', ', Knight', ', Ritter', ' the Elder', ' der Ältere'];
    const placeVariants = place ? place.names.flatMap((placeVariant) => placeAdditions.map((addition) => `${placeVariant}${addition}`)) : (namesByCanonical.get((fallbackPlaceBase || placeName).toLocaleLowerCase()) || [fallbackPlaceBase || placeName]).flatMap((placeVariant) => placeAdditions.map((addition) => `${placeVariant}${addition}`));
    const names = [...new Set(nameVariants.flatMap((nameVariant) => placeVariants.flatMap((placeVariant) => ['von', 'v.', 'de', 'of'].map((connector) => `${nameVariant} ${connector} ${placeVariant}`))))];
    return { name: line, names };
  });
}

function buildPersonPattern(people) {
  const expressions = people.flatMap((person) => [...new Set(person.names)].sort((left, right) => right.length - left.length).map((name) => {
      const connector = name.match(/\s(?:von|v\.|de|of)\s/i);
      if (!connector) return { expression: name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), person };
      const left = name.slice(0, connector.index).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const right = name.slice(connector.index).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      return { expression: `${left}(?:\\s\\([^)]*\\))?${right}`, person };
    }));
  const chunks = [];
  let chunk = [];
  let length = 0;
  expressions.forEach((item) => {
    if (chunk.length && length + item.expression.length > 12000) {
      chunks.push(chunk);
      chunk = [];
      length = 0;
    }
    chunk.push(item);
    length += item.expression.length;
  });
  if (chunk.length) chunks.push(chunk);
  return chunks.map((items) => ({
    pattern: new RegExp(`(?<![\\p{L}\\p{N}])(?:${items.map((item) => item.expression).join('|')})(?![\\p{L}\\p{N}])`, 'giu'),
    people: [...new Set(items.map((item) => item.person))],
  }));
}

function markdownMarkup(value = '') {
  const lines = String(value).split('\n');
  const output = [];
  let listDepth = 0;
  let lastIndent = -1;
  let itemOpen = false;

  const closeLists = () => {
    if (itemOpen) { output.push('</li>'); itemOpen = false; }
    while (listDepth > 0) { output.push('</ul>'); listDepth -= 1; }
    lastIndent = -1;
  };

  lines.forEach((line) => {
    const match = line.match(/^(\s*)[*+-]\s+(.+)$/);
    if (!match) {
      closeLists();
      if (line.trim()) output.push(`<p>${inlineMarkup(line.trim())}</p>`);
      return;
    }

    const indent = match[1].replace(/\t/g, '  ').length;
    if (!listDepth) {
      output.push('<ul class="source-list">');
      listDepth = 1;
    } else if (indent > lastIndent) {
      output.push('<ul>');
      listDepth += 1;
    } else if (indent === lastIndent) {
      if (itemOpen) output.push('</li>');
    } else {
      if (itemOpen) output.push('</li>');
      while (listDepth > 1 && indent < lastIndent) {
        output.push('</ul></li>');
        listDepth -= 1;
        lastIndent = Math.max(0, lastIndent - 2);
      }
    }
    output.push(`<li>${inlineMarkup(match[2])}`);
    itemOpen = true;
    lastIndent = indent;
  });

  closeLists();
  return output.join('');
}

function markdownLinks(value = '') {
  if (!Array.isArray(value)) return inlineMarkup(value);
  return value.map((item) => `<span class="source-line">${inlineMarkup(item)}</span>`).join('');
}

function letterForSource(source) {
  if (!state.manifest?.letters || !source) return null;
  const sourceValues = Array.isArray(source) ? source : [source];
  const sources = sourceValues.flatMap((value) => [value, ...String(value).split(/\s*;\s*/)])
    .filter((value, index, values) => value && values.indexOf(value) === index);
  return sources.reduce((match, citation) => match || state.manifest.letters.reduce((found, path) => {
    if (found) return found;
    const entry = (state.documents.get(path)?.entries || []).find((item) => Array.isArray(item.source) ? item.source.includes(citation) : item.source === citation);
    return entry ? { path, entry } : null;
  }, null), null);
}

function diagramMarkup(value = '') {
  const source = String(value).replace(/^\s*```mermaid\s*\n?/, '').replace(/\n?\s*```\s*$/, '').trim();
  return source ? `<div class="diagram mermaid">${escapeHtml(source)}</div>` : '';
}

function sealAnnotationMarkup(seals = []) {
  if (!Array.isArray(seals)) return '';
  return seals.map((seal) => {
    const x = Number(seal?.position?.split?.(',')?.[0]);
    const y = Number(seal?.position?.split?.(',')?.[1]);
    const size = Number(seal?.size);
    const width = Number.isFinite(Number(seal?.width)) ? Math.max(0, Math.min(1, Number(seal.width))) : 0;
    const wideningRotation = Number.isFinite(Number(seal?.wideningRotation)) ? Number(seal.wideningRotation) : 0;
    const rotation = Number.isFinite(Number(seal?.rotation)) ? Number(seal.rotation) : 0;
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(size) || x < 0 || x > 1 || y < 0 || y > 1 || size <= 0 || !String(seal?.person || '').trim()) return '';
    const person = escapeHtml(seal.person);
    return `<span class="seal-marker" data-size="${size}" data-width="${width}" data-widening-rotation="${wideningRotation}" data-rotation="${rotation}" style="left:${x * 100}%;top:${y * 100}%" role="img" aria-label="Seal of ${person}" title="${person}"><span class="seal-marker-label">${person}</span></span>`;
  }).join('');
}

function localImageName(fileName) {
  if (!/^https?:\/\//i.test(fileName)) return fileName;
  try {
    const url = new URL(fileName);
    const original = url.searchParams.get('originalBilddatei');
    return (original || url.pathname).split('/').filter(Boolean).pop() || '';
  } catch {
    return '';
  }
}

function imageMarkup(value = '', legacySeals = [], context = {}) {
  const imageNodes = Array.isArray(value) ? value : [value];
  const pathParts = location.pathname.split('/').filter(Boolean);
  const repository = pathParts[0];
  const owner = location.hostname.split('.')[0];
  const images = imageNodes.map((node, imageIndex) => {
    if (node && typeof node === 'object' && node.deleted === 'true') return '';
    const file = typeof node === 'object' && node !== null ? node.src : node;
    const seals = typeof node === 'object' && node !== null ? node.seals : imageIndex === 0 ? legacySeals : [];
    const fileName = String(file || '').trim();
    if (!fileName) return '';
    let source;
    let fallback = '';
    if (/^https?:\/\//i.test(fileName)) {
      fallback = fileName;
      const localName = localImageName(fileName);
      const isImage = /\.(?:svg|png|jpe?g|gif|webp)$/i.test(localName);
      if (!isImage) return '';
      const encodedPath = ['letters', localName].map((part) => encodeURIComponent(part)).join('/');
      source = location.hostname.endsWith('github.io')
        ? `https://raw.githubusercontent.com/${owner}/${repository}/main/data/images/${encodedPath}`
        : `../data/images/${encodedPath}`;
    } else {
      const parts = fileName.split('/');
      if (fileName.includes('\\') || parts.some((part) => !part || part === '.' || part === '..') || !/\.(?:svg|png|jpe?g|gif|webp)$/i.test(fileName)) return '';
      const encodedPath = parts.map((part) => encodeURIComponent(part)).join('/');
      source = location.hostname.endsWith('github.io')
        ? `https://raw.githubusercontent.com/${owner}/${repository}/main/data/images/${encodedPath}`
        : `../data/images/${encodedPath}`;
    }
    const annotations = context.sealScreen ? '' : sealAnnotationMarkup(seals);
    const fallbackAttribute = fallback ? ` data-fallback-src="${escapeHtml(fallback)}"` : '';
    const image = `<img src="${escapeHtml(source)}" alt="${escapeHtml(fileName)}" loading="lazy"${fallbackAttribute}>`;
    const editAttributes = context.path && context.index !== null && context.index !== undefined
      ? ` data-document-path="${escapeHtml(context.path)}" data-entry-index="${context.index}" data-image-index="${context.imageIndex ?? imageIndex}"`
      : '';
    const imageLink = `<a class="image-link" href="${escapeHtml(source)}" aria-label="Open image" data-image-src="${escapeHtml(source)}" data-image-fallback="${escapeHtml(fallback)}"${editAttributes}>${image}</a>`;
    const annotatedImage = context.crop
      ? `<span class="seal-crop is-loading" data-seal-x="${context.crop.x}" data-seal-y="${context.crop.y}" data-seal-size="${context.crop.size}" data-seal-width="${context.crop.width ?? 0}" data-seal-widening-rotation="${context.crop.wideningRotation || 0}" data-seal-rotation="${context.crop.rotation || 0}">${imageLink}</span>`
      : annotations ? `<span class="annotated-image">${imageLink}${annotations}</span>` : imageLink;
    return `<figure class="entry-image">${annotatedImage}</figure>`;
  }).filter(Boolean).join('');
  return images ? `<div class="entry-images">${images}</div>` : '';
}

function setupSealAnnotations() {
  state.sealMarkerCleanup?.();
  state.sealMarkerCleanup = null;
  const annotatedImages = [...document.querySelectorAll('.annotated-image img')];
  const cropImages = [...document.querySelectorAll('.seal-crop img')];
  if (!annotatedImages.length && !cropImages.length) return;
  const cropReveals = new Map();
  const update = () => {
    annotatedImages.forEach((image) => {
      const height = image.clientHeight;
      image.closest('.annotated-image')?.querySelectorAll('.seal-marker').forEach((marker) => {
        marker.style.setProperty('--seal-diameter', `${height * Number(marker.dataset.size)}px`);
        marker.style.setProperty('--seal-width', Number(marker.dataset.width) || 0);
        marker.style.setProperty('--seal-widening-rotation', `${Number(marker.dataset.wideningRotation) || 0}deg`);
        marker.style.setProperty('--seal-rotation', `${Number(marker.dataset.rotation) || 0}deg`);
      });
    });
    cropImages.forEach((image) => {
      if (!image.naturalWidth || !image.naturalHeight) return;
      const crop = image.closest('.seal-crop');
      if (!crop) return;
      const x = Number(crop.dataset.sealX);
      const y = Number(crop.dataset.sealY);
      const size = Number(crop.dataset.sealSize);
      const width = Number(crop.dataset.sealWidth) || 0;
      const wideningRotation = Number(crop.dataset.sealWideningRotation) || 0;
      const rotation = Number(crop.dataset.sealRotation) || 0;
      if (![x, y, size, width, wideningRotation, rotation].every(Number.isFinite) || size <= 0 || !crop.clientWidth || !crop.clientHeight) return;
      positionSealCrop(image, crop, x, y, size, width, wideningRotation, rotation);
    });
  };
  annotatedImages.forEach((image) => image.addEventListener('load', update));
  cropImages.forEach((image) => {
    const reveal = () => {
      update();
      image.closest('.seal-crop')?.classList.remove('is-loading');
    };
    cropReveals.set(image, reveal);
    image.addEventListener('load', reveal);
    if (image.complete && image.naturalWidth && image.naturalHeight) reveal();
  });
  window.addEventListener('resize', update, { passive: true });
  state.sealMarkerCleanup = () => {
    annotatedImages.forEach((image) => image.removeEventListener('load', update));
    cropImages.forEach((image) => image.removeEventListener('load', cropReveals.get(image)));
    window.removeEventListener('resize', update);
  };
  update();
}

function positionSealCrop(image, crop, x, y, size, sealWidth = 0, wideningRotation = 0, rotation = 0) {
  const cropSize = image.naturalHeight * Math.max(size, 0.035);
  const scale = crop.clientHeight / cropSize;
  const imageWidth = image.naturalWidth * scale;
  const height = image.naturalHeight * scale;
  image.style.width = `${imageWidth}px`;
  image.style.height = `${height}px`;
  image.style.left = `${crop.clientWidth / 2 - x * imageWidth}px`;
  image.style.top = `${crop.clientHeight / 2 - y * height}px`;
  image.style.transformOrigin = `${x * imageWidth}px ${y * height}px`;
  image.style.transform = `rotate(${rotation}deg) rotate(${-wideningRotation}deg) scaleX(${1 + sealWidth}) rotate(${wideningRotation}deg)`;
}

document.addEventListener('error', (event) => {
  const image = event.target;
  if (!(image instanceof HTMLImageElement)) return;
  const fallback = image.dataset.fallbackSrc;
  if (!fallback || image.src === fallback) return;
  image.removeAttribute('data-fallback-src');
  image.src = fallback;
}, true);

function setupImageLightbox() {
  const lightbox = $('#image-lightbox');
  const lightboxImage = $('#image-lightbox-image');
  const lightboxStage = $('#image-lightbox-stage');
  const lightboxAnnotations = $('#image-lightbox-annotations');
  const sealPreview = $('#image-lightbox-seal-preview');
  const sealPreviewCrop = sealPreview?.querySelector('.seal-crop');
  const sealPreviewImage = sealPreview?.querySelector('img');
  const sealPreviewName = sealPreview?.querySelector('.image-lightbox-seal-preview-name');
  const closeButton = $('#image-lightbox-close');
  const editor = $('#image-lightbox-editor');
  const addSealButton = $('#image-lightbox-add-seal');
  const removeImageButton = $('#image-lightbox-remove-image');
  const removeSealButton = $('#image-lightbox-remove-seal');
  const selectedSealControls = $('#image-lightbox-seal-selected-controls');
  const sealWidthControl = $('#image-lightbox-seal-width');
  const sealWideningRotationControl = $('#image-lightbox-seal-widening-rotation');
  const sealRotationControl = $('#image-lightbox-seal-rotation');
  const sealTypeControls = [...document.querySelectorAll('input[name="image-lightbox-seal-type"]')];
  const saveStatus = $('#image-lightbox-save-status');
  if (!lightbox || !lightboxImage || !lightboxStage || !lightboxAnnotations || !closeButton) return;
  const editable = !location.hostname.endsWith('github.io');
  let editingContext = null;
  let selectedIndex = null;
  let drag = null;
  let magnifierPoint = null;
  let saveQueue = Promise.resolve();
  const SEAL_SIZE_STEP = 0.002;
  const MAGNIFIER_SIZE = 0.12;
  const MAGNIFIER_SIZE_STEP = 0.01;
  let magnifierSize = MAGNIFIER_SIZE;
  if (editor) editor.hidden = !editable;

  const currentSeals = () => editingContext?.node?.seals || [];
  const magnifierMaximumSize = () => {
    const imageHeight = lightboxAnnotations.clientHeight;
    const previewHeight = sealPreviewCrop?.clientHeight;
    return imageHeight && previewHeight ? Math.max(0.03, Math.min(0.5, previewHeight / imageHeight)) : MAGNIFIER_SIZE;
  };
  const updateSealPreview = () => {
    const seal = selectedIndex !== null ? currentSeals()[selectedIndex] : null;
    if (!sealPreview || !sealPreviewCrop || !sealPreviewImage) return;
    let x;
    let y;
    let size;
    let width = 0;
    let wideningRotation = 0;
    let rotation = 0;
    if (seal) {
      [x, y] = String(seal.position || '').split(',').map(Number);
      size = Number(seal.size);
      width = Number(seal.width) || 0;
      wideningRotation = Number(seal.wideningRotation) || 0;
      rotation = Number(seal.rotation) || 0;
      sealPreview.classList.remove('is-magnifier');
      sealPreview.classList.add('is-seal-preview');
      sealPreviewName.hidden = false;
      sealPreviewName.value = seal.person || '';
    } else if (magnifierPoint) {
      ({ x, y } = magnifierPoint);
      magnifierSize = Math.min(magnifierMaximumSize(), Math.max(0.03, magnifierSize));
      size = magnifierSize;
      sealPreview.classList.add('is-magnifier');
      sealPreview.classList.remove('is-seal-preview');
      sealPreviewName.hidden = true;
      if (magnifierSize >= magnifierMaximumSize() - 0.0001) {
        sealPreview.hidden = true;
        return;
      }
    } else {
      sealPreview.hidden = true;
      return;
    }
    if (![x, y, size].every(Number.isFinite) || size <= 0) {
      if (sealPreview) sealPreview.hidden = true;
      return;
    }
    sealPreview.hidden = false;
    if (seal) {
      const imageRect = lightboxAnnotations.getBoundingClientRect();
      const lightboxRect = lightbox.getBoundingClientRect();
      sealPreview.style.left = `${imageRect.left + x * imageRect.width - lightboxRect.left}px`;
      sealPreview.style.top = `${imageRect.top + y * imageRect.height - lightboxRect.top}px`;
    }
    sealPreviewCrop.dataset.sealX = x;
    sealPreviewCrop.dataset.sealY = y;
    sealPreviewCrop.dataset.sealSize = size;
    sealPreviewCrop.dataset.sealWidth = width;
    sealPreviewCrop.dataset.sealWideningRotation = wideningRotation;
    sealPreviewCrop.dataset.sealRotation = rotation;
    if (sealPreviewImage.src !== lightboxImage.src) sealPreviewImage.src = lightboxImage.src;
    if (sealPreviewImage.naturalWidth && sealPreviewImage.naturalHeight) {
      positionSealCrop(sealPreviewImage, sealPreviewCrop, x, y, size, width, wideningRotation, rotation);
      sealPreviewCrop.classList.remove('is-loading');
    }
  };
  sealPreviewImage?.addEventListener('load', updateSealPreview);
  sealPreviewName?.addEventListener('input', () => {
    const seal = selectedIndex !== null ? currentSeals()[selectedIndex] : null;
    if (!seal) return;
    seal.person = sealPreviewName.value;
  });
  const updateEditorControls = () => {
    const selected = selectedIndex !== null ? currentSeals()[selectedIndex] : null;
    if (selectedSealControls) selectedSealControls.hidden = !selected;
    if (removeSealButton) removeSealButton.hidden = !selected;
    if (sealWidthControl) {
      sealWidthControl.disabled = !selected;
      sealWidthControl.value = String(Number(selected?.width) || 0);
    }
    if (sealRotationControl) {
      sealRotationControl.disabled = !selected;
      sealRotationControl.value = String(Number(selected?.rotation) || 0);
    }
    if (sealWideningRotationControl) {
      sealWideningRotationControl.disabled = !selected;
      sealWideningRotationControl.value = String(Number(selected?.wideningRotation) || 0);
    }
    sealTypeControls.forEach((control) => {
      control.disabled = !selected;
      control.checked = Boolean(selected && sealTypeForSeal(selected) === control.value);
    });
  };
  const updateSelectedModifier = (property, value) => {
    const seal = selectedIndex !== null ? currentSeals()[selectedIndex] : null;
    if (!seal) return;
    seal[property] = Number(value);
    renderLightboxSeals();
  };
  const resizeSeal = (index, amount) => {
    const seal = currentSeals()[index];
    if (!seal) return;
    seal.size = Math.max(0.01, Math.min(0.5, Number(seal.size) + amount));
    renderLightboxSeals();
  };
  const renderLightboxSeals = () => {
    const seals = currentSeals();
    let sealIndex = 0;
    lightboxAnnotations.innerHTML = sealAnnotationMarkup(seals).replace(/class="seal-marker"/g, (match) => {
      const index = sealIndex++;
      return `${match} data-seal-index="${index}"${index === selectedIndex ? ' data-selected="true"' : ''}`;
    });
    lightboxAnnotations.querySelectorAll('.seal-marker').forEach((marker) => {
      if (Number(marker.dataset.sealIndex) === selectedIndex) marker.classList.add('selected');
    });
    updateLightboxAnnotations();
    updateSealPreview();
    updateEditorControls();
  };
  const setSaveStatus = (message, error = false) => {
    if (!saveStatus) return;
    saveStatus.textContent = message;
    saveStatus.classList.toggle('error', error);
  };
  const saveDocument = () => {
    if (!editingContext) return Promise.resolve(true);
    const operation = saveQueue.then(async () => {
      const context = editingContext;
      const entry = state.documents.get(context.path)?.entries?.[Number(context.entryIndex)];
      if (entry) {
        const images = Array.isArray(entry.img) ? entry.img : [entry.img];
        images.forEach((image) => {
          if (image && typeof image === 'object' && Array.isArray(image.seals) && image.seals.length === 0) delete image.seals;
        });
      }
      try {
        setSaveStatus('Saving…');
        const response = await fetch('/api/save-document', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: context.path, document: state.documents.get(context.path) }) });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `Save failed (${response.status})`);
        state.snapshot = '';
        return true;
      } catch (error) {
        setSaveStatus(error.message, true);
        return false;
      }
    });
    saveQueue = operation.catch(() => {});
    return operation;
  };
  const closeLightbox = () => {
    lightbox.close();
  };
  const saveAndCloseLightbox = async () => {
    if (editingContext && !await saveDocument()) return;
    closeLightbox();
  };
  const imagePoint = (event) => {
    const rect = lightboxAnnotations.getBoundingClientRect();
    return { x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)) };
  };
  const updateLightboxAnnotations = () => {
    if (!lightboxImage.naturalWidth || !lightboxImage.naturalHeight) return;
    const stageWidth = lightboxStage.clientWidth;
    const stageHeight = lightboxStage.clientHeight;
    const scale = Math.min(stageWidth / lightboxImage.naturalWidth, stageHeight / lightboxImage.naturalHeight);
    const imageWidth = lightboxImage.naturalWidth * scale;
    const imageHeight = lightboxImage.naturalHeight * scale;
    lightboxAnnotations.style.left = `${(stageWidth - imageWidth) / 2}px`;
    lightboxAnnotations.style.top = `${(stageHeight - imageHeight) / 2}px`;
    lightboxAnnotations.style.width = `${imageWidth}px`;
    lightboxAnnotations.style.height = `${imageHeight}px`;
    lightboxAnnotations.querySelectorAll('.seal-marker').forEach((marker) => {
      marker.style.setProperty('--seal-diameter', `${imageHeight * Number(marker.dataset.size)}px`);
      marker.style.setProperty('--seal-width', Number(marker.dataset.width) || 0);
      marker.style.setProperty('--seal-widening-rotation', `${Number(marker.dataset.wideningRotation) || 0}deg`);
      marker.style.setProperty('--seal-rotation', `${Number(marker.dataset.rotation) || 0}deg`);
    });
  };
  $('#content').addEventListener('click', (event) => {
    const link = event.target.closest('.image-link');
    if (!link) return;
    event.preventDefault();
    const image = link.querySelector('img');
    const path = link.dataset.documentPath;
    const entryIndex = Number(link.dataset.entryIndex);
    const imageIndex = Number(link.dataset.imageIndex);
    const entry = path ? state.documents.get(path)?.entries?.[entryIndex] : null;
    let node = entry && (Array.isArray(entry.img) ? entry.img[imageIndex] : entry.img);
    if (node && typeof node !== 'object') {
      if (entry && !Array.isArray(entry.img)) {
        entry.img = { src: node };
      } else if (entry) entry.img[imageIndex] = { src: node };
      node = entry && (Array.isArray(entry.img) ? entry.img[imageIndex] : entry.img);
    }
    editingContext = editable && entry && node && typeof node === 'object' ? { path, node, entryIndex, imageIndex } : null;
    if (editingContext) {
      if (!Array.isArray(node.seals)) node.seals = [];
    }
    selectedIndex = null;
    lightbox.classList.toggle('is-editable', Boolean(editingContext));
    renderLightboxSeals();
    lightboxImage.onerror = () => {
      const fallback = link.dataset.imageFallback;
      if (fallback && lightboxImage.src !== fallback) lightboxImage.src = fallback;
    };
    lightboxImage.src = image?.currentSrc || link.dataset.imageSrc;
    lightboxImage.alt = image?.alt || '';
    lightboxImage.addEventListener('load', updateLightboxAnnotations, { once: true });
    lightboxImage.addEventListener('load', updateSealPreview, { once: true });
    lightbox.showModal();
    updateLightboxAnnotations();
  });
  window.addEventListener('resize', updateLightboxAnnotations, { passive: true });
  window.addEventListener('resize', updateSealPreview, { passive: true });
  closeButton.addEventListener('click', saveAndCloseLightbox);
  sealWidthControl?.addEventListener('input', () => updateSelectedModifier('width', sealWidthControl.value));
  sealWideningRotationControl?.addEventListener('input', () => updateSelectedModifier('wideningRotation', sealWideningRotationControl.value));
  sealRotationControl?.addEventListener('input', () => updateSelectedModifier('rotation', sealRotationControl.value));
  sealTypeControls.forEach((control) => {
    control.addEventListener('change', () => {
      const seal = selectedIndex !== null ? currentSeals()[selectedIndex] : null;
      if (seal && control.checked) seal.type = control.value;
    });
  });
  lightboxAnnotations.addEventListener('pointerdown', (event) => {
    if (!editingContext) return;
    const marker = event.target.closest('.seal-marker');
    if (!marker) return;
    selectedIndex = Number(marker.dataset.sealIndex);
    const point = imagePoint(event);
    drag = { index: selectedIndex, offsetX: currentSeals()[selectedIndex].position.split(',')[0] - point.x, offsetY: currentSeals()[selectedIndex].position.split(',')[1] - point.y };
    lightboxAnnotations.querySelectorAll('.seal-marker').forEach((item) => item.classList.toggle('selected', item === marker));
    updateEditorControls();
    marker.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  });
  lightboxAnnotations.addEventListener('pointermove', (event) => {
    if (!drag) return;
    const point = imagePoint(event);
    const seal = currentSeals()[drag.index];
    const x = Math.max(0, Math.min(1, point.x + Number(drag.offsetX)));
    const y = Math.max(0, Math.min(1, point.y + Number(drag.offsetY)));
    seal.position = `${x.toFixed(4)},${y.toFixed(4)}`;
    const marker = lightboxAnnotations.querySelector(`.seal-marker[data-seal-index="${drag.index}"]`);
    if (marker) {
      marker.style.left = `${x * 100}%`;
      marker.style.top = `${y * 100}%`;
    }
    updateSealPreview();
  });
  lightboxAnnotations.addEventListener('pointerup', () => { drag = null; });
  lightboxStage.addEventListener('click', async (event) => {
    if (!editingContext) return;
    const marker = event.target.closest?.('.seal-marker');
    if (marker) {
      magnifierPoint = null;
      selectedIndex = Number(marker.dataset.sealIndex);
      renderLightboxSeals();
      return;
    }
    const deselectedIndex = selectedIndex;
    selectedIndex = null;
    renderLightboxSeals();
    const savingMarker = deselectedIndex === null
      ? null
      : lightboxAnnotations.querySelector(`.seal-marker[data-seal-index="${deselectedIndex}"]`);
    savingMarker?.classList.add('saving');
    try {
      await saveDocument();
    } finally {
      savingMarker?.classList.remove('saving');
    }
  });
  lightboxStage.addEventListener('pointermove', (event) => {
    if (!editingContext || selectedIndex !== null) return;
    const rect = lightboxAnnotations.getBoundingClientRect();
    if (!rect.width || !rect.height || event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) {
      magnifierPoint = null;
      updateSealPreview();
      return;
    }
    const wasInactive = !magnifierPoint;
    magnifierPoint = {
      x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
    };
    if (wasInactive) magnifierSize = magnifierMaximumSize();
    updateSealPreview();
    const lightboxRect = lightbox.getBoundingClientRect();
    sealPreview.style.left = `${event.clientX - lightboxRect.left}px`;
    sealPreview.style.top = `${event.clientY - lightboxRect.top}px`;
  });
  lightboxStage.addEventListener('pointerleave', () => {
    if (selectedIndex !== null) return;
    magnifierPoint = null;
    updateSealPreview();
  });
  lightbox.addEventListener('wheel', (event) => {
    // A modal should own the wheel while it is open; otherwise the page can
    // scroll underneath it. The marker, when present, is the resize target.
    event.preventDefault();
    if (!editingContext) return;
    if (selectedIndex === null && magnifierPoint) {
      const maximum = magnifierMaximumSize();
      magnifierSize = Math.max(0.03, Math.min(maximum, magnifierSize + (event.deltaY < 0 ? -MAGNIFIER_SIZE_STEP : MAGNIFIER_SIZE_STEP)));
      updateSealPreview();
      return;
    }
    const marker = event.target.closest('.seal-marker');
    if (!marker) return;
    const index = Number(marker.dataset.sealIndex);
    if (index !== selectedIndex) return;
    // deltaMode differs between mouse wheels, trackpads, and browsers. Use
    // the direction only so one gesture has predictable precision everywhere.
    resizeSeal(index, event.deltaY < 0 ? SEAL_SIZE_STEP : -SEAL_SIZE_STEP);
  }, { passive: false });
  addSealButton?.addEventListener('click', () => {
    if (!editingContext) return;
    const person = window.prompt('Person shown by this seal:');
    if (!person?.trim()) return;
    editingContext.node.seals.push({ person: person.trim(), position: '0.5,0.5', size: 0.08, width: 0, wideningRotation: 0, rotation: 0, type: 'full' });
    selectedIndex = editingContext.node.seals.length - 1;
    renderLightboxSeals();
  });
  removeImageButton?.addEventListener('click', async () => {
    if (!editingContext || !window.confirm('Remove this image from the document?')) return;
    const entry = state.documents.get(editingContext.path)?.entries?.[Number(editingContext.entryIndex)];
    if (!entry) return;
    if (Array.isArray(entry.img)) {
      const image = entry.img[Number(editingContext.imageIndex)];
      if (image && typeof image === 'object') image.deleted = 'true';
      else entry.img[Number(editingContext.imageIndex)] = { src: image, deleted: 'true' };
    } else {
      if (entry.img && typeof entry.img === 'object') entry.img.deleted = 'true';
      else entry.img = { src: entry.img, deleted: 'true' };
    }
    if (!await saveDocument()) return;
    lightbox.close();
    await renderActive();
  });
  removeSealButton?.addEventListener('click', () => {
    if (selectedIndex === null) return;
    currentSeals().splice(selectedIndex, 1);
    selectedIndex = null;
    renderLightboxSeals();
  });
  lightbox.addEventListener('click', (event) => {
    if (event.target === lightbox) saveAndCloseLightbox();
  });
  lightbox.addEventListener('cancel', (event) => {
    event.preventDefault();
    saveAndCloseLightbox();
  });
  lightbox.addEventListener('close', () => {
    lightboxImage.removeAttribute('src');
    lightboxAnnotations.replaceChildren();
    if (sealPreview) sealPreview.hidden = true;
    magnifierPoint = null;
    sealPreviewImage?.removeAttribute('src');
    editingContext = null;
    selectedIndex = null;
    drag = null;
    lightbox.classList.remove('is-editable');
    setSaveStatus('');
  });
}

async function getJson(path) {
  const parts = location.pathname.split('/').filter(Boolean);
  const owner = location.hostname.split('.')[0];
  const repository = parts[0];
  const dataPath = location.hostname.endsWith('github.io')
    ? `https://raw.githubusercontent.com/${owner}/${repository}/main/${path}`
    : `../${path}`;
  const response = await fetch(`${dataPath}?v=${Date.now()}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

async function getRepositoryFiles() {
  if (!location.hostname.endsWith('github.io')) {
    const response = await fetch(`/api/files?v=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`Local file list: ${response.status}`);
    return response.json();
  }
  const parts = location.pathname.split('/').filter(Boolean);
  const owner = location.hostname.split('.')[0];
  const repository = parts[0];
  if (!owner || !repository) throw new Error('The viewer must be opened from a GitHub Pages project URL.');
  const response = await fetch(`https://api.github.com/repos/${owner}/${repository}/git/trees/HEAD?recursive=1`);
  if (!response.ok) throw new Error(`GitHub repository tree: ${response.status}`);
  const tree = await response.json();
  return tree.tree
    .filter((item) => item.type === 'blob' && (/^data\/(books|letters)\/.*\.json$/.test(item.path) || item.path === 'data/notes.json'))
    .map((item) => ({ path: item.path, version: item.sha }))
    .sort((left, right) => left.path.localeCompare(right.path));
}

function formatDate(date) {
  const range = String(date || '').split('/');
  if (range.length === 2) {
    const start = formatDate(range[0]);
    const end = formatDate(range[1]);
    return start !== range[0] && end !== range[1] ? `${start} – ${end}` : date;
  }

  const match = String(date || '').match(/^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/);
  if (!match) return date;

  const [, year, month, day] = match;
  if (!month) return year;
  const value = new Date(Date.UTC(Number(year), Number(month) - 1, day ? Number(day) : 1));
  const monthName = new Intl.DateTimeFormat('en-US', { month: 'long', timeZone: 'UTC' }).format(value);
  return day ? `${year}, ${monthName} ${Number(day)}` : `${year}, ${monthName}`;
}

function documentTitle(doc, path) { return doc.book || formatDate(doc.date) || path.split('/').pop().replace(/\.json$/, ''); }

function documentYear(doc) {
  const match = String(doc?.date || '').match(/^(\d{4})/);
  return match ? match[1] : null;
}

function bookSortYear(doc, path) {
  const match = String(doc?.book || path || '').match(/\d{4}/);
  return match ? Number(match[0]) : -Infinity;
}

function sealSortYear(entry) {
  const years = String(entry?.date || '').match(/\d{4}/g);
  return years?.length ? Math.min(...years.map(Number)) : Infinity;
}

const SEAL_TYPES = new Set(['contrepalle', 'swans', 'helm', 'full']);

function sealTypeForSeal(seal) {
  if (SEAL_TYPES.has(seal?.type)) return seal.type;
  return null;
}

function letterSealEntries() {
  const sealEntries = [];
  state.manifest.letters.forEach((path) => {
    const document = state.documents.get(path);
    (document?.entries || []).forEach((entry, entryIndex) => {
      const imageNodes = Array.isArray(entry.img) ? entry.img : [entry.img];
      imageNodes.forEach((node, imageIndex) => {
        if (node && typeof node === 'object' && node.deleted === 'true') return;
        const seals = node && typeof node === 'object' ? node.seals : imageIndex === 0 ? entry.seals : [];
        if (!Array.isArray(seals) || !seals.length || !node) return;
        seals.forEach((seal) => {
          const person = String(seal?.person || '').trim();
          const position = String(seal?.position || '').split(',').map(Number);
          const size = Number(seal?.size);
          const width = Number(seal?.width) || 0;
          const wideningRotation = Number(seal?.wideningRotation) || 0;
          const rotation = Number(seal?.rotation) || 0;
          if (!person || position.length !== 2 || !position.every(Number.isFinite) || !Number.isFinite(size) || size <= 0) return;
          sealEntries.push({
            title: person,
            source: entry.source,
            date: entry.date || document.date,
            url: entry.url || document.url,
            img: [node],
            seals,
            crop: { x: position[0], y: position[1], size, width, wideningRotation, rotation },
            sourcePath: path,
            sourceIndex: entryIndex,
            sourceImageIndex: imageIndex,
            type: sealTypeForSeal(seal),
          });
        });
      });
    });
  });
  return sealEntries;
}

const sealTypeFilters = [
  ['contrepalle', 'contrepalle'],
  ['swans', 'swans'],
  ['helm', 'helm'],
  ['full', 'full'],
  ['unknown', 'unknown'],
];

function sealMatchesType(entry, selected) {
  return !selected || (selected === 'unknown' ? !entry.type : entry.type === selected);
}

function sealTypeYearSpan(entries, type) {
  const years = entries
    .filter((entry) => entry.type === type)
    .flatMap((entry) => String(entry.date || '').match(/\d{4}/g) || [])
    .map(Number);
  if (!years.length) return '';
  const first = Math.min(...years);
  const last = Math.max(...years);
  return first === last ? String(first) : `${first}-${last}`;
}

function normalizeSealFilter(value) {
  const label = String(value || '').trim();
  return label.includes('?') ? 'unknown' : label.toLocaleLowerCase();
}

function sealMatchesSelected(title, selected) {
  const label = String(title || '').trim();
  const normalized = label.toLocaleLowerCase();
  if (selected.has('unknown') && label.includes('?')) return true;
  return [...selected].some((key) => {
    if (key === 'unknown') return false;
    if (normalized === key) return true;
    if (key.includes(' ')) return false;
    const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const namePattern = new RegExp(`(?:^|[+\\/\\s])${escaped}\\??(?=$|[+\\/\\s])`, 'iu');
    const vonPattern = new RegExp(`(?:^|[+\\/\\s])${escaped}\\??\\s+von(?:\\s|$)`, 'iu');
    return namePattern.test(label) && !vonPattern.test(label);
  });
}

function sealSourceMarkup(source) {
  const match = letterForSource(source);
  if (!match) return markdownLinks(source);
  const params = new URLSearchParams({ tab: 'letters', letter: match.path });
  return `<a href="?${params.toString()}">${markdownLinks(source)}</a>`;
}

function sealLetterUrlMarkup(source) {
  const match = letterForSource(source);
  if (!match) return '';
  const url = match.entry.url || state.documents.get(match.path)?.url;
  return url ? urlMarkup(url) : '';
}

function renderSealSidebar(entries) {
  const labels = new Map();
  entries.forEach((entry, index) => {
    const label = String(entry.title || '').trim();
    if (/[+/]/.test(label) || /\szu\s/i.test(label) || /\s(?:elder|knight|nobleman)$/i.test(label)) return;
    const key = label.includes('?') ? 'unknown' : label.toLocaleLowerCase();
    if (label && !labels.has(key)) labels.set(key, { label, index });
  });
  const links = [...labels.values()]
    .map((item) => item.label.includes('?') ? { ...item, label: 'unknown', key: 'unknown' } : { ...item, key: item.label.toLocaleLowerCase() })
    .sort((left, right) => left.key === 'unknown' ? -1 : right.key === 'unknown' ? 1 : left.label.localeCompare(right.label, undefined, { sensitivity: 'base' }))
    .map(({ label, key }) => {
      return `<a href="#" class="${state.sealNames.includes(key) ? 'selected' : ''}" data-seal-name="${escapeHtml(key)}">${escapeHtml(label)}</a>`;
    })
    .join('');
  const hasUnknownTypes = entries.some((entry) => !entry.type);
  const typeLinks = sealTypeFilters.filter(([type]) => type !== 'unknown' || hasUnknownTypes).map(([type, label]) => {
    const detail = type === 'unknown'
      ? `(${entries.filter((entry) => !entry.type).length})`
      : sealTypeYearSpan(entries, type);
    return `<a href="#" class="${state.sealType === type ? 'selected' : ''}" data-seal-type="${type}"><span>${label}</span>${detail ? `<small>${detail}</small>` : ''}</a>`;
  }).join('');
  const nameSidebar = links ? `<aside class="seal-sidebar seal-name-sidebar" aria-label="Seals by name"><nav>${links}</nav></aside>` : '';
  const typeSidebar = typeLinks ? `<aside class="seal-sidebar seal-type-sidebar" aria-label="Seals by type"><nav>${typeLinks}</nav></aside>` : '';
  return `${nameSidebar}${typeSidebar}`;
}

function renderSealsPage() {
  const allEntries = letterSealEntries().sort((left, right) => sealSortYear(left) - sealSortYear(right) || left.title.localeCompare(right.title));
  const selected = new Set(state.sealNames);
  const entries = allEntries.filter((entry) => (!selected.size || sealMatchesSelected(entry.title, selected)) && sealMatchesType(entry, state.sealType));
  const content = entries.map((entry, index) => {
    const titleMarkup = entry.title ? `<h3>${escapeHtml(entry.title)}</h3>` : '';
    const dateMarkup = entry.date ? `<small>${escapeHtml(formatDate(entry.date))}</small>` : '';
    const sourceMarkup = entry.source ? `<p class="source">${sealSourceMarkup(entry.source)}</p>` : '';
    const urlMarkupForLetter = entry.source ? sealLetterUrlMarkup(entry.source) || urlMarkup(entry.url) : urlMarkup(entry.url);
    const imageContext = { path: entry.sourcePath, index: entry.sourceIndex, imageIndex: entry.sourceImageIndex, crop: entry.crop, sealScreen: true };
    return `<article class="entry seal-entry" id="seal-${index}"><div class="seal-entry-meta">${titleMarkup}${dateMarkup}${sourceMarkup}${urlMarkupForLetter}</div><div class="seal-entry-media">${imageMarkup(entry.img, entry.seals, imageContext)}</div></article>`;
  }).join('');
  if (!allEntries.length) return '<article class="document"><h2>Seals</h2><p class="status">No named seals are recorded in the letter images.</p></article>';
  if (!entries.length) return `<div class="seals-layout">${renderSealSidebar(allEntries)}<article class="document seals-document"><p class="status">No seals match the selected filters.</p></article></div>`;
  return `<div class="seals-layout">${renderSealSidebar(allEntries)}<article class="document seals-document">${content}</article></div>`;
}

function setupSealHighlight(entries) {
  state.sealHighlightCleanup?.();
  state.sealHighlightCleanup = null;
  const links = [...document.querySelectorAll('.seal-sidebar a')];
  const nameLinks = links.filter((link) => link.dataset.sealName);
  const targets = entries.map((_, index) => document.querySelector(`#seal-${index}`)).filter(Boolean);
  if (!links.length || !targets.length) return;
  links.forEach((link) => link.addEventListener('click', (event) => {
    event.preventDefault();
    if (link.dataset.sealType) {
      state.sealType = state.sealType === link.dataset.sealType ? null : link.dataset.sealType;
    } else {
      const name = link.dataset.sealName;
      const index = state.sealNames.indexOf(name);
      if (index >= 0) state.sealNames.splice(index, 1);
      else state.sealNames.push(name);
    }
    savePreferences();
    renderActive();
  }));
  const update = () => {
    const marker = window.scrollY + 160;
    let current = 0;
    targets.forEach((target, index) => {
      if (target.getBoundingClientRect().top + window.scrollY <= marker) current = index;
    });
    const currentTitle = entries[current]?.title?.trim() || '';
    const name = currentTitle.includes('?') ? 'unknown' : currentTitle.toLocaleLowerCase();
    nameLinks.forEach((link) => {
      const active = link.dataset.sealName === name;
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
  };
  window.addEventListener('scroll', update, { passive: true });
  state.sealHighlightCleanup = () => window.removeEventListener('scroll', update);
  update();
}

function urlLabel(value) {
  try {
    const hostname = new URL(value).hostname.replace(/^www\./i, '');
    return hostname.split('.').slice(-2).join('.');
  } catch {
    return value;
  }
}

function urlMarkup(value) {
  const links = (Array.isArray(value) ? value : [value])
    .filter((url) => /^https?:\/\//i.test(String(url || '')))
    .map((url) => `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(urlLabel(url))}</a>`);
  return links.length ? `<p class="document-url">${links.join(' · ')}</p>` : '';
}

function findEntityByName(entities, name) {
  return entities.find((entity) => entity.names.some((candidate) => candidate.toLocaleLowerCase() === String(name).toLocaleLowerCase()));
}

function placeForName(name) {
  return findEntityByName(state.places, name);
}

function placeMentions(place) {
  const pattern = buildPlacePattern([place]);
  const mentions = [];
  state.documents.forEach((doc, path) => (doc.entries || []).forEach((entry, index) => {
    const fields = ['title', 'source', 'german', 'latin', 'english', 'facts'];
    const documentPlace = String(doc.place || '');
    if (documentPlace.match(pattern) || fields.some((field) => (Array.isArray(entry[field]) ? entry[field].join('\n') : String(entry[field] || '')).match(pattern))) {
      mentions.push({ doc, path, entry, index });
    }
  }));
  return mentions;
}

function displayedLanguagesFor(entry) {
  const available = ['english', 'german', 'latin'].filter((language) => String(entry[language] || '').trim());
  if (!available.length) return [];
  const original = ['german', 'latin'].find((language) => available.includes(language));
  const languages = state.language === 'original'
    ? ['english', original].filter(Boolean).filter((language) => available.includes(language))
    : ['english'].filter((language) => available.includes(language));
  return languages.length ? languages : available.slice(0, 1);
}

function entityExcerpt(value, pattern) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  const sentences = text.split(/(?<=[.!?。！？])\s+/).filter((sentence) => { pattern.lastIndex = 0; return pattern.test(sentence); });
  let excerpt = sentences.slice(0, 2).join(' ');
  if (!excerpt) excerpt = text;
  let source = excerpt;
  pattern.lastIndex = 0;
  let match = pattern.exec(source);
  if (!match) {
    source = text;
    pattern.lastIndex = 0;
    match = pattern.exec(source);
  }
  if (match && source.length > 420) {
    const limit = 360;
    const maxStart = Math.max(0, source.length - limit);
    let start = Math.min(Math.max(0, match.index - 170), maxStart);
    if (match.index + match[0].length > start + limit) start = Math.min(match.index, maxStart);
    excerpt = `${start ? '…' : ''}${source.slice(start, start + limit)}${start + limit < source.length ? '…' : ''}`;
  }
  return inlineMarkup(excerpt);
}

function entityLanguageMarkup(entry, pattern) {
  const displayedLanguages = displayedLanguagesFor(entry);
  if (!displayedLanguages.length) return '';
  return `<div class="text-grid ${displayedLanguages.length === 1 ? 'single' : ''}">${displayedLanguages.map((language) => `<div class="language"><div class="text"><p>${entityExcerpt(entry[language], pattern)}</p></div></div>`).join('')}</div>`;
}

function entryAnchor(path, index) {
  return `entry-${path.replace(/[^a-z0-9]+/gi, '-')}-${index}`;
}

function documentNavigationUrl(path, index) {
  const params = new URLSearchParams();
  if (path.startsWith('data/letters/')) {
    params.set('tab', 'letters');
    params.set('letter', path);
  } else {
    params.set('document', path);
  }
  return `?${params.toString()}#${entryAnchor(path, index)}`;
}

function renderEntityMentionsPage(entity, mentions, { kind, notFoundMessage, languageMarkup, extraMarkup } = {}) {
  if (!entity) return `<article class="document"><h2>${kind === 'place' ? 'Place' : 'Person'} not found</h2><p class="status">${notFoundMessage}</p></article>`;
  const heading = `<article class="document ${kind}-document-heading"><div class="document-heading"><div><h2>${escapeHtml(entity.name)}</h2><p class="${kind}-variants">${entity.names.map(escapeHtml).join(' · ')}</p></div><small>${mentions.length} mention${mentions.length === 1 ? '' : 's'}</small></div></article>`;
  const content = mentions.map(({ doc, path, entry, index }) => `<article class="document ${kind}-mention" role="link" tabindex="0" data-document-href="${escapeHtml(documentNavigationUrl(path, index))}"><p class="entry-title">${markdownLinks(entry.title || documentTitle(doc, path))}</p>${entry.date ? `<p class="entry-date">${escapeHtml(formatDate(entry.date))}</p>` : ''}${entry.source ? `<p class="source">${markdownLinks(entry.source)}</p>` : ''}${entry.german || entry.latin || entry.english ? languageMarkup(entry) : ''}${extraMarkup ? extraMarkup(doc, entry) : ''}${state.showFacts && entry.facts?.length ? `<ul class="facts">${entry.facts.map((fact) => `<li>${inlineMarkup(fact)}</li>`).join('')}</ul>` : ''}</article>`).join('');
  return `${heading}${content || '<article class="document"><p class="status">No mentions found.</p></article>'}`;
}

function renderPlacePage() {
  const place = placeForName(state.place) || state.places.find((item) => item.name.toLocaleLowerCase() === String(state.place || '').toLocaleLowerCase());
  return renderEntityMentionsPage(place, place ? placeMentions(place) : [], {
    kind: 'place',
    notFoundMessage: `No place named “${escapeHtml(state.place || '')}” is listed in data/places.md.`,
    languageMarkup: (entry) => entityLanguageMarkup(entry, buildPlacePattern([place])),
    extraMarkup: (doc, entry) => doc.place && !entry.german && !entry.latin && !entry.english ? `<p class="place-record">Document place: ${inlineMarkup(doc.place)}</p>` : '',
  });
}

function setupMentionNavigation(mentionClass, excludeSelector) {
  document.querySelectorAll(`.${mentionClass}[data-document-href]`).forEach((frame) => {
    const navigate = () => { window.location.href = frame.dataset.documentHref; };
    frame.addEventListener('click', (event) => {
      if (event.target.closest(excludeSelector)) return;
      navigate();
    });
    frame.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); navigate(); }
    });
  });
}

function personForName(name) {
  return findEntityByName(state.persons, name);
}

function personMentions(person) {
  const patterns = buildPersonPattern([person]);
  const mentions = [];
  state.documents.forEach((doc, path) => (doc.entries || []).forEach((entry, index) => {
    const fields = ['title', 'source', 'german', 'latin', 'english', 'facts'];
    if (fields.some((field) => patterns.some(({ pattern }) => (Array.isArray(entry[field]) ? entry[field].join('\n') : String(entry[field] || '')).match(pattern)))) {
      mentions.push({ doc, path, entry, index });
    }
  }));
  return mentions;
}

function renderPersonPage() {
  const person = personForName(state.person) || state.persons.find((item) => item.name.toLocaleLowerCase() === String(state.person || '').toLocaleLowerCase());
  return renderEntityMentionsPage(person, person ? personMentions(person) : [], {
    kind: 'person',
    notFoundMessage: `No person matching “${escapeHtml(state.person || '')}” is generated from data/names.md and data/places.md.`,
    languageMarkup: (entry) => entityLanguageMarkup(entry, buildPersonPattern([person])[0].pattern),
  });
}

function renderTabs() {
  const tabs = [...state.manifest.books, ...(state.manifest.notes ? [{ path: 'data/notes.json', label: 'Notes' }] : []), { path: 'letters', label: 'Letters' }, { path: 'seals', label: 'Seals' }];
  $('#tabs').innerHTML = tabs.map((tab) => `<button class="tab ${state.active === tab.path ? 'active' : ''}" data-path="${escapeHtml(tab.path)}">${escapeHtml(tab.label)}</button>`).join('');
  document.querySelectorAll('.tab').forEach((button) => button.addEventListener('click', () => { state.active = button.dataset.path; state.place = null; state.person = null; savePreferences(); renderTabs(); renderActive(); }));
}

function languageMarkup(entry) {
  const displayedLanguages = displayedLanguagesFor(entry);
  if (!displayedLanguages.length) return '';
  return `<div class="text-grid ${displayedLanguages.length === 1 ? 'single' : ''}">${displayedLanguages.map((language) => `<div class="language"><div class="text">${markdownMarkup(entry[language])}</div></div>`).join('')}</div>`;
}

function renderEntry(entry, { title = true, date = true, source = true, path = '', index = null } = {}) {
  const entryDate = date && entry.date ? `<p class="entry-date">${escapeHtml(formatDate(entry.date))}</p>` : '';
  const anchor = path && index !== null ? ` id="${entryAnchor(path, index)}"` : '';
  return `<article class="entry"${anchor}>${title && entry.title ? `<p class="entry-title">${markdownLinks(entry.title)}</p>` : ''}${entryDate}${source && entry.source ? `<p class="source">${markdownLinks(entry.source)}</p>` : ''}${entry.url ? urlMarkup(entry.url) : ''}${entry.german || entry.latin || entry.english ? languageMarkup(entry) : ''}${entry.img ? imageMarkup(entry.img, [], { path, index }) : ''}${entry.diagram ? diagramMarkup(entry.diagram) : ''}${state.showFacts && entry.facts?.length ? `<ul class="facts">${entry.facts.map((fact) => `<li>${inlineMarkup(fact)}</li>`).join('')}</ul>` : ''}</article>`;
}

function bookSections(entries) {
  return entries.reduce((sections, entry) => {
    if (entry.title || !sections.length) sections.push({ title: entry.title || '', entries: [] });
    sections[sections.length - 1].entries.push(entry);
    return sections;
  }, []);
}

function renderDocument(doc, path, index) {
  const entries = doc.entries || [];
  const title = documentTitle(doc, path);
  const date = doc.date && formatDate(doc.date) !== title ? `<small>${escapeHtml(formatDate(doc.date))}</small>` : '';
  const label = String(doc.label || '').trim();
  const headingAside = label || date ? `<div class="document-heading-aside">${label ? `<span class="letter-label">${escapeHtml(label)}</span>` : ''}${date}</div>` : '';
  const url = doc.url ? urlMarkup(doc.url) : '';
  const year = documentYear(doc);
  const anchor = year ? ` id="year-${year}-${index}"` : '';
  if (path.startsWith('data/books/') || path === 'data/notes.json') {
    return bookSections(entries).map((section, sectionIndex) => {
      const sectionTitle = section.title || (sectionIndex === 0 ? title : 'Untitled section');
      const sectionContent = section.entries.map((entry) => renderEntry(entry, { title: false, path, index: entries.indexOf(entry) })).join('');
      return `<article class="document book-document"><div class="document-heading"><div><h2>${markdownLinks(sectionTitle)}</h2>${sectionIndex === 0 ? url : ''}</div>${sectionIndex === 0 ? date : ''}</div>${sectionContent}</article>`;
    }).join('');
  }
  const content = entries.map((entry, entryIndex) => renderEntry(entry, { path, index: entryIndex })).join('');
  const important = label.toLocaleLowerCase() === 'important' ? ' important' : '';
  const dimmed = ['hessen', 'schenk', 'mönch'].includes(label.toLocaleLowerCase()) ? ' dimmed' : '';
  return `<article class="document${important}${dimmed}"${anchor}><div class="document-heading"><div><h2>${inlineMarkup(title)}</h2>${url}</div>${headingAside}</div>${content}</article>`;
}

const GREY_LETTER_LABELS = new Set(['hessen', 'schenk', 'mönch']);

function letterLabelForPath(path) {
  return String(state.documents.get(path)?.label || '').trim().toLocaleLowerCase();
}

function visibleLetterPaths(paths) {
  const selected = new Set(state.letterLabels);
  const hidden = new Set(state.hiddenLetterLabels || []);
  return paths.filter((path) => {
    const label = letterLabelForPath(path);
    if (hidden.has(label)) return false;
    return !selected.size || selected.has(label);
  });
}

function renderYearSidebar(paths, labelPaths = paths) {
  const years = [...new Set(paths.map((path) => documentYear(state.documents.get(path))).filter(Boolean))]
    .sort((left, right) => Number(left) - Number(right));
  const yearLinks = years.map((year) => {
    const index = paths.findIndex((path) => documentYear(state.documents.get(path)) === year);
    return `<a href="#" data-sidebar-type="year" data-path="${escapeHtml(paths[index])}">${year}</a>`;
  }).join('');
  const labels = new Map();
  labelPaths.forEach((path) => {
    const label = String(state.documents.get(path)?.label || '').trim();
    if (label && !labels.has(label.toLocaleLowerCase())) labels.set(label.toLocaleLowerCase(), { label, path });
  });
  const labelLinks = [...labels.values()]
    .sort((left, right) => left.label.localeCompare(right.label, undefined, { sensitivity: 'base' }))
    .map(({ label, path }) => {
      const key = label.toLocaleLowerCase();
      const selected = GREY_LETTER_LABELS.has(key) ? state.hiddenLetterLabels.includes(key) : state.letterLabels.includes(key);
      return `<a href="#" class="${selected ? 'selected' : ''}" data-sidebar-type="label" data-label="${escapeHtml(key)}" data-path="${escapeHtml(path)}">${escapeHtml(label)}</a>`;
    })
    .join('');
  if (!yearLinks && !labelLinks) return '';
  return `${yearLinks ? `<aside class="year-sidebar" aria-label="Letters by year"><nav>${yearLinks}</nav></aside>` : ''}${labelLinks ? `<aside class="label-sidebar" aria-label="Letters by label"><nav>${labelLinks}</nav></aside>` : ''}`;
}

function setupYearHighlight(paths) {
  state.yearHighlightCleanup?.();
  state.yearHighlightCleanup = null;
  const links = [...document.querySelectorAll('.year-sidebar a, .label-sidebar a')];
  const targets = paths
    .map((path, index) => ({ path, element: document.querySelector(`#year-${documentYear(state.documents.get(path))}-${index}`) }))
    .filter(({ element }) => element);
  if (!links.length || !targets.length) return;
  let selectedLink = null;

  links.forEach((link) => link.addEventListener('click', (event) => {
    event.preventDefault();
    if (link.dataset.sidebarType === 'label') {
      const label = link.dataset.label;
      const values = GREY_LETTER_LABELS.has(label) ? state.hiddenLetterLabels : state.letterLabels;
      const index = values.indexOf(label);
      if (index >= 0) values.splice(index, 1);
      else values.push(label);
      savePreferences();
      renderActive();
      return;
    }
    const target = targets.find((item) => item.path === link.dataset.path);
    if (!target) return;
    state.letter = target.path;
    savePreferences();
    window.scrollTo(0, target.element.getBoundingClientRect().top + window.scrollY - 104);
  }));

  const update = () => {
    const marker = window.scrollY + 160;
    let current = targets[0];
    targets.forEach((target) => {
      if (target.element.getBoundingClientRect().top + window.scrollY <= marker) current = target;
    });
    state.letter = current.path;
    savePreferences();
    const year = current.element.id.match(/^year-(\d{4})-/)?.[1];
    const currentLabel = String(state.documents.get(current.path)?.label || '').trim().toLocaleLowerCase();
    links.forEach((link) => {
      const active = link.dataset.sidebarType === 'year'
        ? link.textContent === year
        : link.dataset.label === currentLabel;
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
      if (active && link !== selectedLink) {
        link.scrollIntoView({ block: 'nearest' });
        selectedLink = link;
      }
    });
  };

  window.addEventListener('scroll', update, { passive: true });
  state.yearHighlightCleanup = () => window.removeEventListener('scroll', update);
  update();
}

function restoreLetter(paths) {
  const index = paths.indexOf(state.letter);
  if (index < 0) return;
  const target = document.querySelector(`#year-${documentYear(state.documents.get(state.letter))}-${index}`);
  if (target) window.scrollTo(0, target.getBoundingClientRect().top + window.scrollY - 104);
}

function scrollToEntryHash() {
  const hash = decodeURIComponent(location.hash.slice(1));
  if (!hash) return;
  const target = document.getElementById(hash);
  if (target) target.scrollIntoView({ block: 'start' });
}

async function renderActive() {
  state.sealMarkerCleanup?.();
  state.sealMarkerCleanup = null;
  if (state.person) {
    $('#content').innerHTML = renderPersonPage();
    setupMentionNavigation('person-mention', 'a.place-link, a.person-link');
    return;
  }
  if (state.place) {
    $('#content').innerHTML = renderPlacePage();
    setupMentionNavigation('place-mention', 'a.place-link');
    return;
  }
  state.sealHighlightCleanup?.();
  state.sealHighlightCleanup = null;
  if (state.active === 'seals') {
    $('#status').textContent = '';
    $('#content').innerHTML = renderSealsPage();
    const allEntries = letterSealEntries().sort((left, right) => sealSortYear(left) - sealSortYear(right) || left.title.localeCompare(right.title));
    const selectedNames = new Set(state.sealNames);
    const entries = allEntries.filter((entry) => (!selectedNames.size || sealMatchesSelected(entry.title, selectedNames)) && sealMatchesType(entry, state.sealType));
    setupSealHighlight(entries);
    setupSealAnnotations();
    return;
  }
  const allLetterPaths = state.manifest.letters;
  const paths = state.active === 'letters' ? visibleLetterPaths(allLetterPaths) : [state.active];
  const selectedYear = documentYear(state.documents.get(state.letter));
  const shouldRestoreLetter = state.active === 'letters'
    && selectedYear
    && (state.lastRenderedLettersYear === null || selectedYear !== state.lastRenderedLettersYear);
  $('#status').textContent = '';
  state.yearHighlightCleanup?.();
  state.yearHighlightCleanup = null;
  if (state.active === 'letters') {
    $('#content').innerHTML = `<div class="letters-layout">${renderYearSidebar(paths, allLetterPaths)}<div class="letters-list">${paths.map((path, index) => renderDocument(state.documents.get(path), path, index)).join('')}</div></div>`;
  } else {
    $('#content').innerHTML = paths.map((path, index) => renderDocument(state.documents.get(path), path, index)).join('');
  }
  setupSealAnnotations();
  const diagrams = $('#content').querySelectorAll('.mermaid');
  if (diagrams.length && typeof mermaid !== 'undefined') await mermaid.run({ nodes: diagrams });
  if (state.active === 'letters') {
    if (shouldRestoreLetter) restoreLetter(paths);
    setupYearHighlight(paths);
    state.lastRenderedLettersYear = documentYear(state.documents.get(state.letter));
  }
  scrollToEntryHash();
}

async function loadAll() {
  const files = await getRepositoryFiles();
  const paths = files.map((file) => typeof file === 'string' ? file : file.path);
  const snapshot = JSON.stringify(files);
  const [placesText, peopleText, namesText, documents] = await Promise.all([
    getText('data/places.md'),
    getText('data/people.md'),
    getText('data/names.md'),
    new Map(await Promise.all(paths.map(async (path) => [path, await getJson(path)]))),
  ]);
  state.places = parsePlaces(placesText);
  state.people = parsePeople(peopleText, namesText, state.places);
  state.persons = state.people;
  state.personPattern = buildPersonPattern(state.persons);
  state.placePattern = buildPlacePattern(state.places);
  const bookPaths = paths
    .filter((path) => path.startsWith('data/books/'))
    .sort((left, right) => bookSortYear(documents.get(right), right) - bookSortYear(documents.get(left), left) || left.localeCompare(right));
  const letterPaths = paths.filter((path) => path.startsWith('data/letters/'));
  const manifest = {
    books: bookPaths.map((path) => ({ path, label: documents.get(path)?.book || path })),
    notes: paths.includes('data/notes.json'),
    letters: letterPaths,
  };
  state.manifest = manifest; state.documents = documents; state.snapshot = snapshot;
  if (!Array.isArray(state.hiddenLetterLabels)) state.hiddenLetterLabels = [...GREY_LETTER_LABELS];
  state.sealNames = [...new Set(state.sealNames.map(normalizeSealFilter).filter(Boolean))];
  if (state.active !== 'letters' && state.active !== 'seals' && !paths.includes(state.active)) state.active = manifest.books[0]?.path || 'letters';
  savePreferences();
  renderTabs(); await renderActive();
}

async function refreshIfChanged() {
  if ($('#image-lightbox')?.open) return;
  try {
    const files = await getRepositoryFiles();
    if ($('#image-lightbox')?.open) return;
    if (JSON.stringify(files) !== state.snapshot) await loadAll();
  } catch (error) {
    // A temporary network failure should not interrupt the next refresh attempt.
    console.warn('Could not check for data updates:', error);
  }
}

const languageToggle = $('#language-toggle');
updateLanguageControl();
updateFactsControl();
languageToggle.addEventListener('click', () => {
  state.language = state.language === 'english' ? 'original' : 'english';
  updateLanguageControl();
  savePreferences();
  renderActive();
});
const factsToggle = $('#facts-toggle');
factsToggle.addEventListener('click', () => {
  state.showFacts = !state.showFacts;
  updateFactsControl();
  savePreferences();
  renderActive();
});
const themeToggle = $('#theme-toggle');
themeToggle.addEventListener('click', () => {
  state.darkMode = !state.darkMode;
  applyTheme();
  applyMermaidTheme();
  savePreferences();
  renderActive();
});

setupImageLightbox();

async function getText(path) {
  const parts = location.pathname.split('/').filter(Boolean);
  const owner = location.hostname.split('.')[0];
  const repository = parts[0];
  const dataPath = location.hostname.endsWith('github.io')
    ? `https://raw.githubusercontent.com/${owner}/${repository}/main/${path}`
    : `../${path}`;
  const response = await fetch(`${dataPath}?v=${Date.now()}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.text();
}
loadAll().catch((error) => {
  $('#status').textContent = `Could not load data: ${error.message}`;
  $('#status').classList.add('error');
});

setInterval(refreshIfChanged, REFRESH_INTERVAL);
