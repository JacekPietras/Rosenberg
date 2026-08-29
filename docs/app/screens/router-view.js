export async function renderActiveScreen({
  state,
  content,
  status,
  leafletMap,
  destroyMap,
  renderPersonPage,
  renderPlacePage,
  renderSealsPage,
  letterSealEntries,
  sealSortYear,
  sealMatchesSelected,
  sealMatchesType,
  renderPeopleTree,
  renderMapPage,
  setupMap,
  visibleLetterPaths,
  documentYear,
  renderYearSidebar,
  renderDocument,
  setupSealAnnotations,
  setupSealHighlight,
  restoreLetter,
  setupYearHighlight,
  scrollToEntryHash,
  setupMentionNavigation,
  mermaid,
}) {
  status.textContent = '';
  status.classList.remove('error');
  state.sealMarkerCleanup?.();
  state.sealMarkerCleanup = null;
  if (leafletMap && state.active !== 'map') destroyMap();
  if (state.person) {
    content.innerHTML = renderPersonPage();
    setupMentionNavigation('person-mention', 'a.place-link, a.person-link');
    return;
  }
  if (state.place) {
    content.innerHTML = renderPlacePage();
    setupMentionNavigation('place-mention', 'a.place-link');
    return;
  }
  state.sealHighlightCleanup?.();
  state.sealHighlightCleanup = null;
  if (state.active === 'seals') {
    content.innerHTML = renderSealsPage();
    const allEntries = letterSealEntries().sort((left, right) => sealSortYear(left) - sealSortYear(right) || left.title.localeCompare(right.title));
    const selectedNames = new Set(state.sealNames);
    const entries = allEntries.filter((entry) => (!selectedNames.size || sealMatchesSelected(entry.title, selectedNames)) && sealMatchesType(entry, state.sealType));
    setupSealHighlight(entries);
    setupSealAnnotations();
    return;
  }
  if (state.active === 'tree') {
    content.innerHTML = renderPeopleTree(state.personRecords);
    return;
  }
  if (state.active === 'map') {
    content.innerHTML = renderMapPage();
    setupMap();
    return;
  }
  const allLetterPaths = state.manifest.letters;
  const paths = state.active === 'letters' ? visibleLetterPaths(allLetterPaths) : [state.active];
  const selectedYear = documentYear(state.documents.get(state.letter));
  const shouldRestoreLetter = state.active === 'letters'
    && selectedYear
    && (state.lastRenderedLettersYear === null || selectedYear !== state.lastRenderedLettersYear);
  state.yearHighlightCleanup?.();
  state.yearHighlightCleanup = null;
  if (state.active === 'letters') {
    content.innerHTML = `<div class="letters-layout">${renderYearSidebar(paths, state.letterSource ? paths : allLetterPaths)}<div class="letters-list">${paths.map((path, index) => renderDocument(state.documents.get(path), path, index)).join('')}</div></div>`;
  } else {
    content.innerHTML = paths.map((path, index) => renderDocument(state.documents.get(path), path, index)).join('');
  }
  setupSealAnnotations();
  const diagrams = content.querySelectorAll('.mermaid');
  if (diagrams.length && mermaid) await mermaid.run({ nodes: diagrams });
  if (state.active === 'letters') {
    if (shouldRestoreLetter) restoreLetter(paths);
    setupYearHighlight(paths);
    state.lastRenderedLettersYear = documentYear(state.documents.get(state.letter));
  }
  scrollToEntryHash();
}
