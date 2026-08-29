export function createTabs({ state, escapeHtml, clearScreenCaches, savePreferences, rerender }) {
  function render() {
    const tabs = [
      { path: 'books', label: 'Books' },
      ...(state.manifest.notes ? [{ path: 'data/notes/notes.json', label: 'Notes' }] : []),
      { path: 'letters', label: 'Letters' },
      { path: 'seals', label: 'Seals' },
      { path: 'map', label: 'Map' },
      { path: 'tree', label: 'Tree' },
    ];
    const bookIsActive = state.active === 'books' || state.manifest.books.some((book) => book.path === state.active);
    const tabsElement = document.querySelector('#tabs');
    const bookTabsElement = document.querySelector('#book-tabs');
    tabsElement.innerHTML = tabs.map((tab) => `<button class="tab ${(tab.path === 'books' ? bookIsActive : state.active === tab.path) ? 'active' : ''}" data-path="${escapeHtml(tab.path)}">${escapeHtml(tab.label)}</button>`).join('');
    bookTabsElement.innerHTML = bookIsActive
      ? state.manifest.books.map((book) => `<button class="subtab ${state.active === book.path ? 'active' : ''}" data-path="${escapeHtml(book.path)}">${escapeHtml(book.label)}</button>`).join('')
      : '';
    document.querySelectorAll('.tab, .subtab').forEach((button) => button.addEventListener('click', () => {
      const requestedPath = button.dataset.path;
      const nextActive = requestedPath === 'books'
        ? (state.manifest.books.some((book) => book.path === state.active) ? state.active : state.manifest.books[0]?.path || 'letters')
        : requestedPath;
      if (nextActive !== state.active) clearScreenCaches();
      if (nextActive !== 'letters') {
        state.letterSource = null;
        state.navigationLetterSource = null;
      }
      const nextUrl = new URL(location.href);
      nextUrl.search = '';
      nextUrl.hash = '';
      if (requestedPath === 'books' || ['letters', 'seals', 'map', 'tree'].includes(nextActive)) nextUrl.searchParams.set('tab', requestedPath === 'books' ? 'books' : nextActive);
      else nextUrl.searchParams.set('document', nextActive);
      history.replaceState(null, '', `${nextUrl.pathname}${nextUrl.search}`);
      state.active = nextActive;
      state.place = null;
      state.person = null;
      savePreferences();
      render();
      rerender();
    }));
  }

  return { render };
}
