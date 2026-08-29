const SEAL_TYPES = new Set(['contrepalle', 'swans', 'helm', 'full']);
const sealTypeFilters = [
  ['contrepalle', 'contrepalle'],
  ['swans', 'swans'],
  ['helm', 'helm'],
  ['full', 'full'],
  ['unknown', 'unknown'],
];

export function createSealScreen({
  state,
  formatDate,
  escapeHtml,
  urlMarkup,
  markdownLinks,
  imageMarkup,
  letterForSource,
  sourceCitations,
  entryAnchor,
  getDocuments,
  savePreferences,
  rerender,
}) {
  function sealTypeForSeal(seal) {
    return SEAL_TYPES.has(seal?.type) ? seal.type : null;
  }

  function letterSealEntries() {
    const sealEntries = [];
    state.manifest.letters.forEach((path) => {
      const document = getDocuments().get(path);
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
    const params = new URLSearchParams({ tab: 'letters', letter: match.path, source: sourceCitations(source)[0] });
    return `<a href="?${params.toString()}#${entryAnchor(match.path, match.entryIndex)}">${markdownLinks(source)}</a>`;
  }

  function sealLetterUrlMarkup(source) {
    const match = letterForSource(source);
    if (!match) return '';
    const url = match.entry.url || getDocuments().get(match.path)?.url;
    return url ? urlMarkup(url) : '';
  }

  function renderSealSidebar(entries) {
    const labels = new Map();
    entries.forEach((entry) => {
      const label = String(entry.title || '').trim();
      if (/[+/]/.test(label) || /\szu\s/i.test(label) || /\s(?:elder|knight|nobleman)$/i.test(label)) return;
      const key = label.includes('?') ? 'unknown' : label.toLocaleLowerCase();
      if (label && !labels.has(key)) labels.set(key, { label });
    });
    const links = [...labels.values()]
      .map((item) => item.label.includes('?') ? { ...item, label: 'unknown', key: 'unknown' } : { ...item, key: item.label.toLocaleLowerCase() })
      .sort((left, right) => left.key === 'unknown' ? -1 : right.key === 'unknown' ? 1 : left.label.localeCompare(right.label, undefined, { sensitivity: 'base' }))
      .map(({ label, key }) => `<a href="#" class="${state.sealNames.includes(key) ? 'selected' : ''}" data-seal-name="${escapeHtml(key)}">${escapeHtml(label)}</a>`)
      .join('');
    const hasUnknownTypes = entries.some((entry) => !entry.type);
    const typeLinks = sealTypeFilters
      .filter(([type]) => type !== 'unknown' || hasUnknownTypes)
      .map(([type, label]) => {
        const detail = type === 'unknown' ? `(${entries.filter((entry) => !entry.type).length})` : sealTypeYearSpan(entries, type);
        return `<a href="#" class="${state.sealType === type ? 'selected' : ''}" data-seal-type="${type}"><span>${label}</span>${detail ? `<small>${detail}</small>` : ''}</a>`;
      }).join('');
    const nameSidebar = links ? `<aside class="seal-sidebar seal-name-sidebar" aria-label="Seals by name"><nav>${links}</nav></aside>` : '';
    const typeSidebar = typeLinks ? `<aside class="seal-sidebar seal-type-sidebar" aria-label="Seals by type"><nav>${typeLinks}</nav></aside>` : '';
    return `${nameSidebar}${typeSidebar}`;
  }

  function sealSortYear(entry) {
    const years = String(entry?.date || '').match(/\d{4}/g);
    return years?.length ? Math.min(...years.map(Number)) : Infinity;
  }

  function renderSealsPage() {
    const allEntries = letterSealEntries().sort((left, right) => sealSortYear(left) - sealSortYear(right) || left.title.localeCompare(right.title));
    const selected = new Set(state.sealNames);
    const entries = allEntries.filter((entry) => (!selected.size || sealMatchesSelected(entry.title, selected)) && sealMatchesType(entry, state.sealType));
    const content = entries.map((entry, index) => {
      const titleMarkup = entry.title ? `<h3>${escapeHtml(entry.title)}</h3>` : '';
      const dateMarkup = entry.date ? `<small>${escapeHtml(formatDate(entry.date))}</small>` : '';
      const sourceMarkup = entry.source ? `<p class="source">${sealSourceMarkup(entry.source)}</p>` : '';
      const letterUrl = entry.source ? sealLetterUrlMarkup(entry.source) || urlMarkup(entry.url) : urlMarkup(entry.url);
      const imageContext = { path: entry.sourcePath, index: entry.sourceIndex, imageIndex: entry.sourceImageIndex, crop: entry.crop, sealScreen: true };
      return `<article class="entry seal-entry" id="seal-${index}"><div class="seal-entry-meta">${titleMarkup}${dateMarkup}${sourceMarkup}${letterUrl}</div><div class="seal-entry-media">${imageMarkup(entry.img, entry.seals, imageContext)}</div></article>`;
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
      rerender();
    }));
    const update = () => {
      const marker = window.scrollY + 160;
      let current = 0;
      targets.forEach((target, index) => {
        if (target.getBoundingClientRect().top + window.scrollY <= marker) current = index;
      });
      const title = entries[current]?.title?.trim() || '';
      const name = title.includes('?') ? 'unknown' : title.toLocaleLowerCase();
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

  return { letterSealEntries, sealMatchesType, sealMatchesSelected, sealSortYear, renderSealsPage, setupSealHighlight, normalizeSealFilter };
}
