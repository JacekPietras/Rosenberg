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
      language: normalizeDisplayMode(preferences.language),
      showFacts: preferences.showFacts !== false,
      darkMode: preferences.darkMode !== false,
    };
  } catch {
    return { active: null, place: null, person: null, letter: null, language: 'english', showFacts: true, darkMode: true };
  }
}

function savePreferences() {
  try {
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify({ active: state.active, place: state.place, person: state.person, letter: state.letter, language: state.language, showFacts: state.showFacts, darkMode: state.darkMode }));
  } catch {
    // Preferences are optional; rendering should continue if storage is unavailable.
  }
}

const preferences = loadPreferences();
const state = { manifest: null, active: preferences.active, place: preferences.place, person: preferences.person, letter: preferences.letter, language: preferences.language, darkMode: preferences.darkMode, documents: new Map(), people: [], persons: [], places: [], personPattern: null, placePattern: null, snapshot: '', yearHighlightCleanup: null, sealMarkerCleanup: null, lastRenderedLettersYear: null };
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
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(size) || x < 0 || x > 1 || y < 0 || y > 1 || size <= 0 || !String(seal?.person || '').trim()) return '';
    const person = escapeHtml(seal.person);
    return `<span class="seal-marker" data-size="${size}" style="left:${x * 100}%;top:${y * 100}%" role="img" aria-label="Seal of ${person}" title="${person}"><span class="seal-marker-label">${person}</span></span>`;
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

function imageMarkup(value = '', context = {}) {
  const imageNodes = Array.isArray(value) ? value : [value];
  const pathParts = location.pathname.split('/').filter(Boolean);
  const repository = pathParts[0];
  const owner = location.hostname.split('.')[0];
  const images = imageNodes.map((node, imageIndex) => {
    if (node && typeof node === 'object' && node.deleted === 'true') return '';
    const file = typeof node === 'object' && node !== null ? node.src : node;
    const seals = typeof node === 'object' && node !== null ? node.seals : [];
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
    const annotations = sealAnnotationMarkup(seals);
    const fallbackAttribute = fallback ? ` data-fallback-src="${escapeHtml(fallback)}"` : '';
    const image = `<img src="${escapeHtml(source)}" alt="${escapeHtml(fileName)}" loading="lazy"${fallbackAttribute}>`;
    const editAttributes = context.path && context.index !== null && context.index !== undefined
      ? ` data-document-path="${escapeHtml(context.path)}" data-entry-index="${context.index}" data-image-index="${context.imageIndex ?? imageIndex}"`
      : '';
    const imageLink = `<a class="image-link" href="${escapeHtml(source)}" aria-label="Open image" data-image-src="${escapeHtml(source)}" data-image-fallback="${escapeHtml(fallback)}"${editAttributes}>${image}</a>`;
    const annotatedImage = annotations ? `<span class="annotated-image">${imageLink}${annotations}</span>` : imageLink;
    return `<figure class="entry-image">${annotatedImage}</figure>`;
  }).filter(Boolean).join('');
  return images ? `<div class="entry-images">${images}</div>` : '';
}

function setupSealAnnotations() {
  state.sealMarkerCleanup?.();
  state.sealMarkerCleanup = null;
  const annotatedImages = [...document.querySelectorAll('.annotated-image img')];
  if (!annotatedImages.length) return;
  const update = () => {
    annotatedImages.forEach((image) => {
      const height = image.clientHeight;
      image.closest('.annotated-image')?.querySelectorAll('.seal-marker').forEach((marker) => {
        marker.style.setProperty('--seal-diameter', `${height * Number(marker.dataset.size)}px`);
      });
    });
  };
  annotatedImages.forEach((image) => image.addEventListener('load', update));
  window.addEventListener('resize', update, { passive: true });
  state.sealMarkerCleanup = () => {
    annotatedImages.forEach((image) => image.removeEventListener('load', update));
    window.removeEventListener('resize', update);
  };
  update();
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
  const closeButton = $('#image-lightbox-close');
  const editor = $('#image-lightbox-editor');
  const addSealButton = $('#image-lightbox-add-seal');
  const removeImageButton = $('#image-lightbox-remove-image');
  const removeSealButton = $('#image-lightbox-remove-seal');
  const saveStatus = $('#image-lightbox-save-status');
  if (!lightbox || !lightboxImage || !lightboxStage || !lightboxAnnotations || !closeButton) return;
  const editable = !location.hostname.endsWith('github.io');
  let editingContext = null;
  let selectedIndex = null;
  let saveTimer = null;
  let drag = null;
  if (editor) editor.hidden = !editable;

  const currentSeals = () => editingContext?.node?.seals || [];
  const updateEditorControls = () => {
    const selected = selectedIndex !== null ? currentSeals()[selectedIndex] : null;
    if (removeSealButton) removeSealButton.hidden = !selected;
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
    updateEditorControls();
  };
  const setSaveStatus = (message, error = false) => {
    if (!saveStatus) return;
    saveStatus.textContent = message;
    saveStatus.classList.toggle('error', error);
  };
  const saveDocument = async () => {
    if (!editingContext) return;
    const entry = state.documents.get(editingContext.path)?.entries?.[Number(editingContext.entryIndex)];
    if (entry) {
      const images = Array.isArray(entry.img) ? entry.img : [entry.img];
      images.forEach((image) => {
        if (image && typeof image === 'object' && Array.isArray(image.seals) && image.seals.length === 0) delete image.seals;
      });
    }
    try {
      const response = await fetch('/api/save-document', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: editingContext.path, document: state.documents.get(editingContext.path) }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `Save failed (${response.status})`);
      state.snapshot = '';
      return true;
    } catch (error) {
      setSaveStatus(error.message, true);
      return false;
    }
  };
  const queueSave = () => {
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(saveDocument, 100);
  };
  const closeLightbox = async () => {
    window.clearTimeout(saveTimer);
    if (editingContext && !await saveDocument()) return;
    lightbox.close();
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
    if (editingContext && !Array.isArray(node.seals)) node.seals = [];
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
    lightbox.showModal();
    updateLightboxAnnotations();
  });
  window.addEventListener('resize', updateLightboxAnnotations, { passive: true });
  closeButton.addEventListener('click', closeLightbox);
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
  });
  lightboxAnnotations.addEventListener('pointerup', () => { if (drag) queueSave(); drag = null; });
  lightboxAnnotations.addEventListener('click', (event) => {
    const marker = event.target.closest('.seal-marker');
    if (marker && editingContext) { selectedIndex = Number(marker.dataset.sealIndex); renderLightboxSeals(); }
  });
  lightboxAnnotations.addEventListener('wheel', (event) => {
    if (!editingContext) return;
    const marker = event.target.closest('.seal-marker');
    if (!marker) return;
    const index = Number(marker.dataset.sealIndex);
    const seal = currentSeals()[index];
    if (!seal) return;
    seal.size = Math.max(0.01, Math.min(0.5, Number(seal.size) + (event.deltaY < 0 ? 0.001 : -0.001)));
    selectedIndex = index;
    renderLightboxSeals();
    queueSave();
    event.preventDefault();
  }, { passive: false });
  addSealButton?.addEventListener('click', () => {
    if (!editingContext) return;
    const person = window.prompt('Person shown by this seal:');
    if (!person?.trim()) return;
    editingContext.node.seals.push({ person: person.trim(), position: '0.5,0.5', size: 0.08 });
    selectedIndex = editingContext.node.seals.length - 1;
    renderLightboxSeals();
    queueSave();
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
    queueSave();
  });
  lightbox.addEventListener('click', (event) => {
    if (event.target === lightbox) closeLightbox();
  });
  lightbox.addEventListener('close', () => {
    lightboxImage.removeAttribute('src');
    lightboxAnnotations.replaceChildren();
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

function placeForName(name) {
  return state.places.find((place) => place.names.some((candidate) => candidate.toLocaleLowerCase() === String(name).toLocaleLowerCase()));
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

function placeExcerpt(value, place) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  const pattern = buildPlacePattern([place]);
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

function placeLanguageMarkup(entry, place) {
  const available = ['english', 'german', 'latin'].filter((language) => String(entry[language] || '').trim());
  if (!available.length) return '';
  const original = ['german', 'latin'].find((language) => available.includes(language));
  const languages = state.language === 'original'
    ? ['english', original].filter(Boolean).filter((language) => available.includes(language))
    : ['english'].filter((language) => available.includes(language));
  const displayedLanguages = languages.length ? languages : available.slice(0, 1);
  return `<div class="text-grid ${displayedLanguages.length === 1 ? 'single' : ''}">${displayedLanguages.map((language) => `<div class="language"><div class="text"><p>${placeExcerpt(entry[language], place)}</p></div></div>`).join('')}</div>`;
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

function renderPlacePage() {
  const place = placeForName(state.place) || state.places.find((item) => item.name.toLocaleLowerCase() === String(state.place || '').toLocaleLowerCase());
  if (!place) return `<article class="document"><h2>Place not found</h2><p class="status">No place named “${escapeHtml(state.place || '')}” is listed in data/places.md.</p></article>`;
  const mentions = placeMentions(place);
  const heading = `<article class="document place-document-heading"><div class="document-heading"><div><h2>${escapeHtml(place.name)}</h2><p class="place-variants">${place.names.map(escapeHtml).join(' · ')}</p></div><small>${mentions.length} mention${mentions.length === 1 ? '' : 's'}</small></div></article>`;
  const content = mentions.map(({ doc, path, entry, index }) => `<article class="document place-mention" role="link" tabindex="0" data-document-href="${escapeHtml(documentNavigationUrl(path, index))}"><p class="entry-title">${markdownLinks(entry.title || documentTitle(doc, path))}</p>${entry.date ? `<p class="entry-date">${escapeHtml(formatDate(entry.date))}</p>` : ''}${entry.source ? `<p class="source">${markdownLinks(entry.source)}</p>` : ''}${entry.german || entry.latin || entry.english ? placeLanguageMarkup(entry, place) : ''}${doc.place && !entry.german && !entry.latin && !entry.english ? `<p class="place-record">Document place: ${inlineMarkup(doc.place)}</p>` : ''}${state.showFacts && entry.facts?.length ? `<ul class="facts">${entry.facts.map((fact) => `<li>${inlineMarkup(fact)}</li>`).join('')}</ul>` : ''}</article>`).join('');
  return `${heading}${content || '<article class="document"><p class="status">No mentions found.</p></article>'}`;
}

function setupPlaceNavigation() {
  document.querySelectorAll('.place-mention[data-document-href]').forEach((frame) => {
    const navigate = () => { window.location.href = frame.dataset.documentHref; };
    frame.addEventListener('click', (event) => {
      if (event.target.closest('a.place-link')) return;
      navigate();
    });
    frame.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); navigate(); }
    });
  });
}

function personForName(name) {
  return state.persons.find((person) => person.names.some((candidate) => candidate.toLocaleLowerCase() === String(name).toLocaleLowerCase()));
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

function personExcerpt(value, person) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  const pattern = buildPersonPattern([person])[0].pattern;
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

function personLanguageMarkup(entry, person) {
  const available = ['english', 'german', 'latin'].filter((language) => String(entry[language] || '').trim());
  if (!available.length) return '';
  const original = ['german', 'latin'].find((language) => available.includes(language));
  const languages = state.language === 'original'
    ? ['english', original].filter(Boolean).filter((language) => available.includes(language))
    : ['english'].filter((language) => available.includes(language));
  const displayedLanguages = languages.length ? languages : available.slice(0, 1);
  return `<div class="text-grid ${displayedLanguages.length === 1 ? 'single' : ''}">${displayedLanguages.map((language) => `<div class="language"><div class="text"><p>${personExcerpt(entry[language], person)}</p></div></div>`).join('')}</div>`;
}

function renderPersonPage() {
  const person = personForName(state.person) || state.persons.find((item) => item.name.toLocaleLowerCase() === String(state.person || '').toLocaleLowerCase());
  if (!person) return `<article class="document"><h2>Person not found</h2><p class="status">No person matching “${escapeHtml(state.person || '')}” is generated from data/names.md and data/places.md.</p></article>`;
  const mentions = personMentions(person);
  const heading = `<article class="document person-document-heading"><div class="document-heading"><div><h2>${escapeHtml(person.name)}</h2><p class="person-variants">${person.names.map(escapeHtml).join(' · ')}</p></div><small>${mentions.length} mention${mentions.length === 1 ? '' : 's'}</small></div></article>`;
  const content = mentions.map(({ doc, path, entry, index }) => `<article class="document person-mention" role="link" tabindex="0" data-document-href="${escapeHtml(documentNavigationUrl(path, index))}"><p class="entry-title">${markdownLinks(entry.title || documentTitle(doc, path))}</p>${entry.date ? `<p class="entry-date">${escapeHtml(formatDate(entry.date))}</p>` : ''}${entry.source ? `<p class="source">${markdownLinks(entry.source)}</p>` : ''}${entry.german || entry.latin || entry.english ? personLanguageMarkup(entry, person) : ''}${state.showFacts && entry.facts?.length ? `<ul class="facts">${entry.facts.map((fact) => `<li>${inlineMarkup(fact)}</li>`).join('')}</ul>` : ''}</article>`).join('');
  return `${heading}${content || '<article class="document"><p class="status">No mentions found.</p></article>'}`;
}

function setupPersonNavigation() {
  document.querySelectorAll('.person-mention[data-document-href]').forEach((frame) => {
    const navigate = () => { window.location.href = frame.dataset.documentHref; };
    frame.addEventListener('click', (event) => {
      if (event.target.closest('a.place-link, a.person-link')) return;
      navigate();
    });
    frame.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); navigate(); }
    });
  });
}

function renderTabs() {
  const tabs = [...state.manifest.books, ...(state.manifest.notes ? [{ path: 'data/notes.json', label: 'Notes' }] : []), { path: 'letters', label: 'Letters' }];
  $('#tabs').innerHTML = tabs.map((tab) => `<button class="tab ${state.active === tab.path ? 'active' : ''}" data-path="${escapeHtml(tab.path)}">${escapeHtml(tab.label)}</button>`).join('');
  document.querySelectorAll('.tab').forEach((button) => button.addEventListener('click', () => { state.active = button.dataset.path; state.place = null; state.person = null; savePreferences(); renderTabs(); renderActive(); }));
}

function languageMarkup(entry) {
  const available = ['english', 'german', 'latin'].filter((language) => String(entry[language] || '').trim());
  if (!available.length) return '';

  const original = ['german', 'latin'].find((language) => available.includes(language));
  const languages = state.language === 'original'
    ? ['english', original].filter(Boolean).filter((language) => available.includes(language))
    : ['english'].filter((language) => available.includes(language));
  const displayedLanguages = languages.length ? languages : available.slice(0, 1);
  return `<div class="text-grid ${displayedLanguages.length === 1 ? 'single' : ''}">${displayedLanguages.map((language) => `<div class="language"><div class="text">${markdownMarkup(entry[language])}</div></div>`).join('')}</div>`;
}

function renderEntry(entry, { title = true, date = true, source = true, path = '', index = null } = {}) {
  const entryDate = date && entry.date ? `<p class="entry-date">${escapeHtml(formatDate(entry.date))}</p>` : '';
  const anchor = path && index !== null ? ` id="${entryAnchor(path, index)}"` : '';
  return `<article class="entry"${anchor}>${title && entry.title ? `<p class="entry-title">${markdownLinks(entry.title)}</p>` : ''}${entryDate}${source && entry.source ? `<p class="source">${markdownLinks(entry.source)}</p>` : ''}${entry.url ? urlMarkup(entry.url) : ''}${entry.german || entry.latin || entry.english ? languageMarkup(entry) : ''}${entry.img ? imageMarkup(entry.img, { path, index }) : ''}${entry.diagram ? diagramMarkup(entry.diagram) : ''}${state.showFacts && entry.facts?.length ? `<ul class="facts">${entry.facts.map((fact) => `<li>${inlineMarkup(fact)}</li>`).join('')}</ul>` : ''}</article>`;
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

function renderYearSidebar(paths) {
  const years = [...new Set(paths.map((path) => documentYear(state.documents.get(path))).filter(Boolean))]
    .sort((left, right) => Number(left) - Number(right));
  if (!years.length) return '';

  const links = years.map((year) => {
    const index = paths.findIndex((path) => documentYear(state.documents.get(path)) === year);
    return `<a href="#" data-path="${escapeHtml(paths[index])}">${year}</a>`;
  }).join('');
  return `<aside class="year-sidebar" aria-label="Letters by year"><nav>${links}</nav></aside>`;
}

function setupYearHighlight(paths) {
  state.yearHighlightCleanup?.();
  state.yearHighlightCleanup = null;
  const links = [...document.querySelectorAll('.year-sidebar a')];
  const targets = paths
    .map((path, index) => ({ path, element: document.querySelector(`#year-${documentYear(state.documents.get(path))}-${index}`) }))
    .filter(({ element }) => element);
  if (!links.length || !targets.length) return;
  let selectedLink = null;

  links.forEach((link) => link.addEventListener('click', (event) => {
    event.preventDefault();
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
    links.forEach((link) => {
      const active = link.textContent === year;
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
    setupPersonNavigation();
    return;
  }
  if (state.place) {
    $('#content').innerHTML = renderPlacePage();
    setupPlaceNavigation();
    return;
  }
  const paths = state.active === 'letters' ? state.manifest.letters : [state.active];
  const selectedYear = documentYear(state.documents.get(state.letter));
  const shouldRestoreLetter = state.active === 'letters'
    && selectedYear
    && (state.lastRenderedLettersYear === null || selectedYear !== state.lastRenderedLettersYear);
  $('#status').textContent = '';
  state.yearHighlightCleanup?.();
  state.yearHighlightCleanup = null;
  if (state.active === 'letters') {
    $('#content').innerHTML = `<div class="letters-layout">${renderYearSidebar(paths)}<div class="letters-list">${paths.map((path, index) => renderDocument(state.documents.get(path), path, index)).join('')}</div></div>`;
  } else {
    $('#content').innerHTML = paths.map((path, index) => renderDocument(state.documents.get(path), path, index)).join('');
  }
  setupSealAnnotations();
  const diagrams = $('#content').querySelectorAll('.mermaid');
  if (diagrams.length) await mermaid.run({ nodes: diagrams });
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
  if (state.active !== 'letters' && !paths.includes(state.active)) state.active = manifest.books[0]?.path || 'letters';
  savePreferences();
  renderTabs(); await renderActive();
}

async function refreshIfChanged() {
  try {
    const files = await getRepositoryFiles();
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
