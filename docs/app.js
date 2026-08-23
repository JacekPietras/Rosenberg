const PREFERENCES_KEY = 'rosenberg-viewer-preferences';
const VALID_LANGUAGES = new Set(['english', 'german', 'both']);

function loadPreferences() {
  try {
    const preferences = JSON.parse(localStorage.getItem(PREFERENCES_KEY) || '{}');
    return {
      active: typeof preferences.active === 'string' ? preferences.active : null,
      letter: typeof preferences.letter === 'string' ? preferences.letter : null,
      language: VALID_LANGUAGES.has(preferences.language) ? preferences.language : 'english',
      showFacts: preferences.showFacts !== false,
      darkMode: preferences.darkMode !== false,
    };
  } catch {
    return { active: null, letter: null, language: 'english', showFacts: true, darkMode: true };
  }
}

function savePreferences() {
  try {
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify({ active: state.active, letter: state.letter, language: state.language, showFacts: state.showFacts, darkMode: state.darkMode }));
  } catch {
    // Preferences are optional; rendering should continue if storage is unavailable.
  }
}

const preferences = loadPreferences();
const state = { manifest: null, active: preferences.active, letter: preferences.letter, language: preferences.language, darkMode: preferences.darkMode, documents: new Map(), snapshot: '', yearHighlightCleanup: null, lastRenderedLettersYear: null };
const $ = (selector) => document.querySelector(selector);
const REFRESH_INTERVAL = 30000;

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
  const label = state.language === 'both' ? 'Both languages' : state.language === 'english' ? 'English' : 'German';
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

function inlineMarkup(value = '') {
  return escapeHtml(value)
    .replace(/\[\[([^\]]+)\]\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
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
  return inlineMarkup(value);
}

function diagramMarkup(value = '') {
  const source = String(value).replace(/^\s*```mermaid\s*\n?/, '').replace(/\n?\s*```\s*$/, '').trim();
  return source ? `<div class="diagram mermaid">${escapeHtml(source)}</div>` : '';
}

function imageMarkup(value = '') {
  const fileName = String(value).trim();
  if (!fileName || fileName.includes('/') || fileName.includes('\\') || !/\.(?:svg|png|jpe?g|gif|webp)$/i.test(fileName)) return '';
  const source = `../data/images/${encodeURIComponent(fileName)}`;
  return `<figure class="entry-image"><img src="${source}" alt="${escapeHtml(fileName)}" loading="lazy"></figure>`;
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
    .filter((item) => item.type === 'blob' && /^data\/(books|letters)\/.*\.json$/.test(item.path))
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

function renderTabs() {
  const tabs = [...state.manifest.books, { path: 'letters', label: 'Letters' }];
  $('#tabs').innerHTML = tabs.map((tab) => `<button class="tab ${state.active === tab.path ? 'active' : ''}" data-path="${escapeHtml(tab.path)}">${escapeHtml(tab.label)}</button>`).join('');
  document.querySelectorAll('.tab').forEach((button) => button.addEventListener('click', () => { state.active = button.dataset.path; savePreferences(); renderTabs(); renderActive(); }));
}

function languageMarkup(entry) {
  const languages = state.language === 'both' ? ['german', 'english'] : [state.language];
  return `<div class="text-grid ${languages.length === 1 ? 'single' : ''}">${languages.map((language) => `<div class="language"><div class="text">${markdownMarkup(entry[language] || '—')}</div></div>`).join('')}</div>`;
}

function renderDocument(doc, path, index) {
  const entries = (doc.entries || []).map((entry) => `<article class="entry">${entry.title ? `<p class="entry-title">${markdownLinks(entry.title)}</p>` : ''}${entry.source ? `<p class="source">${markdownLinks(entry.source)}</p>` : ''}${entry.url ? urlMarkup(entry.url) : ''}${entry.german || entry.english ? languageMarkup(entry) : ''}${entry.img ? imageMarkup(entry.img) : ''}${entry.diagram ? diagramMarkup(entry.diagram) : ''}${state.showFacts && entry.facts?.length ? `<ul class="facts">${entry.facts.map((fact) => `<li>${escapeHtml(fact)}</li>`).join('')}</ul>` : ''}</article>`).join('');
  const title = documentTitle(doc, path);
  const date = doc.date && formatDate(doc.date) !== title ? `<small>${escapeHtml(formatDate(doc.date))}</small>` : '';
  const url = doc.url ? urlMarkup(doc.url) : '';
  const year = documentYear(doc);
  const anchor = year ? ` id="year-${year}-${index}"` : '';
  return `<article class="document"${anchor}><div class="document-heading"><div><h2>${escapeHtml(title)}</h2>${url}</div>${date}</div>${entries}</article>`;
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

async function renderActive() {
  const paths = state.active === 'letters' ? state.manifest.letters : [state.active];
  const selectedYear = documentYear(state.documents.get(state.letter));
  const shouldRestoreLetter = state.active === 'letters'
    && selectedYear
    && state.lastRenderedLettersYear !== null
    && selectedYear !== state.lastRenderedLettersYear;
  $('#status').textContent = '';
  state.yearHighlightCleanup?.();
  state.yearHighlightCleanup = null;
  if (state.active === 'letters') {
    $('#content').innerHTML = `<div class="letters-layout">${renderYearSidebar(paths)}<div class="letters-list">${paths.map((path, index) => renderDocument(state.documents.get(path), path, index)).join('')}</div></div>`;
  } else {
    $('#content').innerHTML = paths.map((path, index) => renderDocument(state.documents.get(path), path, index)).join('');
  }
  const diagrams = $('#content').querySelectorAll('.mermaid');
  if (diagrams.length) await mermaid.run({ nodes: diagrams });
  if (state.active === 'letters') {
    if (shouldRestoreLetter) restoreLetter(paths);
    setupYearHighlight(paths);
    state.lastRenderedLettersYear = documentYear(state.documents.get(state.letter));
  }
}

async function loadAll() {
  const files = await getRepositoryFiles();
  const paths = files.map((file) => typeof file === 'string' ? file : file.path);
  const snapshot = JSON.stringify(files);
  const documents = new Map(await Promise.all(paths.map(async (path) => [path, await getJson(path)])));
  const bookPaths = paths.filter((path) => path.startsWith('data/books/'));
  const letterPaths = paths.filter((path) => path.startsWith('data/letters/'));
  const manifest = { books: bookPaths.map((path) => ({ path, label: documents.get(path)?.book || path })), letters: letterPaths };
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
const languages = ['english', 'german', 'both'];
updateLanguageControl();
updateFactsControl();
languageToggle.addEventListener('click', () => {
  state.language = languages[(languages.indexOf(state.language) + 1) % languages.length];
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
loadAll().catch((error) => {
  $('#status').textContent = `Could not load data: ${error.message}`;
  $('#status').classList.add('error');
});

setInterval(refreshIfChanged, REFRESH_INTERVAL);
