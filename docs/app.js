const state = { manifest: null, active: null, language: 'english', documents: new Map() };
const $ = (selector) => document.querySelector(selector);

function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
}

function markdownLinks(value = '') {
  return escapeHtml(value).replace(/\[\[([^\]]+)\]\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
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
  const parts = location.pathname.split('/').filter(Boolean);
  const owner = location.hostname.split('.')[0];
  const repository = parts[0];
  if (!owner || !repository) throw new Error('The viewer must be opened from a GitHub Pages project URL.');
  const response = await fetch(`https://api.github.com/repos/${owner}/${repository}/git/trees/HEAD?recursive=1`);
  if (!response.ok) throw new Error(`GitHub repository tree: ${response.status}`);
  const tree = await response.json();
  return tree.tree.filter((item) => item.type === 'blob' && /^data\/(books|letters)\/.*\.json$/.test(item.path)).map((item) => item.path).sort();
}

function documentTitle(doc, path) { return doc.book || doc.date || path.split('/').pop().replace(/\.json$/, ''); }

function renderTabs() {
  const tabs = [...state.manifest.books, { path: 'letters', label: 'Letters' }];
  $('#tabs').innerHTML = tabs.map((tab) => `<button class="tab ${state.active === tab.path ? 'active' : ''}" data-path="${escapeHtml(tab.path)}">${escapeHtml(tab.label)}</button>`).join('');
  document.querySelectorAll('.tab').forEach((button) => button.addEventListener('click', () => { state.active = button.dataset.path; renderTabs(); renderActive(); }));
}

function languageMarkup(entry) {
  const languages = state.language === 'both' ? ['german', 'english'] : [state.language];
  return `<div class="text-grid ${languages.length === 1 ? 'single' : ''}">${languages.map((language) => `<div class="language"><p class="language-label">${language}</p><p class="text">${markdownLinks(entry[language] || '—')}</p></div>`).join('')}</div>`;
}

function renderDocument(doc, path) {
  const entries = (doc.entries || []).map((entry) => `<article class="entry">${entry.title ? `<p class="entry-title">${markdownLinks(entry.title)}</p>` : ''}${entry.source ? `<p class="source">${markdownLinks(entry.source)}</p>` : ''}${languageMarkup(entry)}${entry.facts?.length ? `<ul class="facts">${entry.facts.map((fact) => `<li>${escapeHtml(fact)}</li>`).join('')}</ul>` : ''}</article>`).join('');
  return `<article class="document"><div class="document-heading"><h2>${escapeHtml(documentTitle(doc, path))}</h2><small>${doc.date ? escapeHtml(doc.date) : `${doc.entries?.length || 0} entries`}</small></div>${entries}</article>`;
}

async function renderActive() {
  const paths = state.active === 'letters' ? state.manifest.letters : [state.active];
  $('#status').textContent = state.active === 'letters' ? `${paths.length} letters` : `${paths.length ? state.documents.get(paths[0])?.entries?.length || 0 : 0} entries`;
  $('#content').innerHTML = paths.map((path) => renderDocument(state.documents.get(path), path)).join('');
}

async function loadAll() {
  const paths = await getRepositoryFiles();
  const documents = new Map(await Promise.all(paths.map(async (path) => [path, await getJson(path)])));
  const bookPaths = paths.filter((path) => path.startsWith('data/books/'));
  const letterPaths = paths.filter((path) => path.startsWith('data/letters/'));
  const manifest = { books: bookPaths.map((path) => ({ path, label: documents.get(path)?.book || path })), letters: letterPaths };
  state.manifest = manifest; state.documents = documents; state.active ||= manifest.books[0]?.path || 'letters';
  renderTabs(); await renderActive();
}

async function loadLocalFolder(files) {
  const documents = new Map();
  for (const file of files) {
    if (!file.name.endsWith('.json')) continue;
    const relative = file.webkitRelativePath.replace(/^.*?\/(books|letters)\//, 'data/$1/');
    if (!relative.startsWith('data/books/') && !relative.startsWith('data/letters/')) continue;
    documents.set(relative, JSON.parse(await file.text()));
  }
  const books = [...documents.keys()].filter((path) => path.startsWith('data/books/')).sort();
  const letters = [...documents.keys()].filter((path) => path.startsWith('data/letters/')).sort();
  state.manifest = { books: books.map((path) => ({ path, label: documents.get(path).book || path })), letters };
  state.documents = documents; state.active ||= books[0] || 'letters';
  renderTabs(); await renderActive();
  $('#status').textContent = `${books.length} books · ${letters.length} letters loaded locally`;
  $('#status').classList.remove('error');
}

document.querySelectorAll('input[name="language"]').forEach((input) => input.addEventListener('change', (event) => { state.language = event.target.value; renderActive(); }));
$('#choose-folder').addEventListener('click', () => $('#folder-input').click());
$('#folder-input').addEventListener('change', (event) => loadLocalFolder(event.target.files).catch((error) => {
  $('#status').textContent = `Could not read folder: ${error.message}`;
  $('#status').classList.add('error');
}));
loadAll().catch((error) => {
  $('#status').textContent = `Could not load data: ${error.message}`;
  $('#status').classList.add('error');
  $('#choose-folder').classList.add('visible');
});
