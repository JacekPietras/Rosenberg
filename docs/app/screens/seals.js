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
  titleMarkup,
  urlMarkup,
  markdownLinks,
  imageMarkup,
  recordForSource,
  sourceCitations,
  entryAnchor,
  getDocuments,
  savePreferences,
  rerender,
}) {
  function sealTypeForSeal(seal) {
    return SEAL_TYPES.has(seal?.type) ? seal.type : null;
  }

  function recordSealEntries() {
    const sealEntries = [];
    state.manifest.documents.forEach((path) => {
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

  function sealPersonLabel(value) {
    const label = String(value || '').trim();
    const reference = label.match(/^\[([^\]]+)\]$/);
    if (!reference) return label;
    const person = (state.personRecords || []).find((item) => item?.id === reference[1]);
    if (!person?.name) return label;
    return String(person.name).trim().split(/\s+/)[0];
  }

  function sealMatchesSelected(title, selected) {
    if (!selected.size) return true;
    const parts = sealNameParts(title);
    const selectedByPart = { before: [], after: [] };
    selected.forEach((value) => {
      const [part, ...rest] = value.split(':');
      if (part === 'before' || part === 'after') selectedByPart[part].push(rest.join(':'));
      else {
        const legacy = value.toLocaleLowerCase();
        const afterPattern = new RegExp(`(?:^|[+\\/\\s])${legacy.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\??(?=$|[+\\/\\s])`, 'iu');
        selectedByPart[afterPattern.test(parts.after) ? 'after' : 'before'].push(value);
      }
    });
    return ['before', 'after'].every((part) => {
      const keys = selectedByPart[part];
      if (!keys.length) return true;
      const label = parts[part];
      const normalized = label.toLocaleLowerCase();
      return keys.some((key) => {
        if (key === 'unknown') return label.includes('?');
        if (normalized === key) return true;
        if (key.includes(' ')) return false;
        const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const namePattern = new RegExp(`(?:^|[+\\/\\s])${escaped}\\??(?=$|[+\\/\\s])`, 'iu');
        return namePattern.test(label);
      });
    });
  }

  function sealNameParts(value) {
    const label = sealPersonLabel(value);
    const split = label.match(/^(.+?)\s+von\s+(.+)$/i);
    return split ? { before: split[1].trim(), after: split[2].trim() } : { before: label, after: '' };
  }

  function sealSourceMarkup(source) {
    const match = recordForSource(source);
    if (!match) return markdownLinks(source);
    const params = new URLSearchParams({ tab: 'documents', record: match.path, source: sourceCitations(source)[0] });
    return `<a href="?${params.toString()}#${entryAnchor(match.path, match.entryIndex)}">${markdownLinks(source)}</a>`;
  }

  function sealRecordUrlMarkup(source) {
    const match = recordForSource(source);
    if (!match) return '';
    const url = match.entry.url || getDocuments().get(match.path)?.url;
    return url ? urlMarkup(url) : '';
  }

  function renderSealSidebar(entries) {
    const labels = { before: new Map(), after: new Map() };
    entries.forEach((entry) => {
      const parts = sealNameParts(entry.title);
      for (const part of ['before', 'after']) {
        const label = parts[part];
        if (!label || /[+/]/.test(label) || /\szu\s/i.test(label) || /\s(?:elder|knight|nobleman)$/i.test(label)) continue;
        const key = label.includes('?') ? 'unknown' : label.toLocaleLowerCase();
        if (!labels[part].has(key)) labels[part].set(key, { label });
      }
    });
    const renderNames = (part, heading) => {
      const links = [...labels[part].values()]
        .map((item) => item.label.includes('?') ? { ...item, label: 'unknown', key: 'unknown' } : { ...item, key: item.label.toLocaleLowerCase() })
        .sort((left, right) => left.key === 'unknown' ? -1 : right.key === 'unknown' ? 1 : left.label.localeCompare(right.label, undefined, { sensitivity: 'base' }))
        .map(({ label, key }) => `<a href="#" class="${state.sealNames.includes(`${part}:${key}`) ? 'selected' : ''}" data-seal-name="${escapeHtml(key)}" data-seal-part="${part}">${escapeHtml(label)}</a>`)
        .join('');
      return links ? `<aside class="seal-sidebar seal-name-sidebar${part === 'after' ? ' seal-after-von-sidebar' : ''}" aria-label="Seals ${heading.toLowerCase()}"><nav>${links}</nav></aside>` : '';
    };
    const hasUnknownTypes = entries.some((entry) => !entry.type);
    const typeLinks = sealTypeFilters
      .filter(([type]) => type !== 'unknown' || hasUnknownTypes)
      .map(([type, label]) => {
        const detail = type === 'unknown' ? `(${entries.filter((entry) => !entry.type).length})` : sealTypeYearSpan(entries, type);
        return `<a href="#" class="${state.sealType === type ? 'selected' : ''}" data-seal-type="${type}"><span>${label}</span>${detail ? `<small>${detail}</small>` : ''}</a>`;
      }).join('');
    const nameSidebar = renderNames('before', 'Before von');
    const surnameSidebar = renderNames('after', 'After von');
    const typeSidebar = typeLinks ? `<aside class="seal-sidebar seal-type-sidebar" aria-label="Seals by type"><nav>${typeLinks}</nav></aside>` : '';
    const surnameAndType = surnameSidebar || typeSidebar ? `<div class="seal-surname-type-filters">${surnameSidebar}${typeSidebar}</div>` : '';
    return `${nameSidebar}${surnameAndType}`;
  }

  function sealSortYear(entry) {
    const years = String(entry?.date || '').match(/\d{4}/g);
    return years?.length ? Math.min(...years.map(Number)) : Infinity;
  }

  function renderSealsPage() {
    state.sealNames = state.sealNames.filter((value) => value.includes(':'));
    const allEntries = recordSealEntries().sort((left, right) => sealSortYear(left) - sealSortYear(right) || left.title.localeCompare(right.title));
    const selected = new Set(state.sealNames);
    const entries = allEntries.filter((entry) => (!selected.size || sealMatchesSelected(entry.title, selected)) && sealMatchesType(entry, state.sealType));
    const content = entries.map((entry, index) => {
      const title = entry.title ? `<h3>${titleMarkup(entry.title)}</h3>` : '';
      const dateMarkup = entry.date ? `<small>${escapeHtml(formatDate(entry.date))}</small>` : '';
      const sourceMarkup = entry.source ? `<p class="source">${sealSourceMarkup(entry.source)}</p>` : '';
      const recordUrl = entry.source ? sealRecordUrlMarkup(entry.source) || urlMarkup(entry.url) : urlMarkup(entry.url);
      const imageContext = { path: entry.sourcePath, index: entry.sourceIndex, imageIndex: entry.sourceImageIndex, crop: entry.crop, sealScreen: true };
      return `<article class="entry seal-entry" id="seal-${index}"><div class="seal-entry-meta">${title}${dateMarkup}${sourceMarkup}${recordUrl}</div><div class="seal-entry-media">${imageMarkup(entry.img, entry.seals, imageContext)}</div></article>`;
    }).join('');
    if (!allEntries.length) return '<article class="document"><h2>Seals</h2><p class="status">No named seals are recorded in the document images.</p></article>';
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
        state.sealNames = state.sealNames.filter((value) => value.includes(':'));
        const name = `${link.dataset.sealPart}:${link.dataset.sealName}`;
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

  return { recordSealEntries, sealMatchesType, sealMatchesSelected, sealSortYear, renderSealsPage, setupSealHighlight, normalizeSealFilter };
}
