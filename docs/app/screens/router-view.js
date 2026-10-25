export async function renderActiveScreen({
  state,
  content,
  status,
  leafletMap,
  destroyMap,
  renderPersonPage,
  renderPlacePage,
  renderSealsPage,
  recordSealEntries,
  sealSortYear,
  sealMatchesSelected,
  sealMatchesType,
  renderPeopleTree,
  setupPeopleTreeZoom,
  renderMapPage,
  setupMap,
  render3dPage,
  renderImagesPage,
  setupImageFilters,
  visibleRecordPaths,
  documentYear,
  renderYearSidebar,
  renderDocument,
  setupSealAnnotations,
  setupSealHighlight,
  restoreRecord,
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
    const allEntries = recordSealEntries().sort((left, right) => sealSortYear(left) - sealSortYear(right) || left.title.localeCompare(right.title));
    const selectedNames = new Set(state.sealNames);
    const entries = allEntries.filter((entry) => (!selectedNames.size || sealMatchesSelected(entry.title, selectedNames)) && sealMatchesType(entry, state.sealType));
    setupSealHighlight(entries);
    setupSealAnnotations();
    return;
  }
  if (state.active === 'tree') {
    content.innerHTML = renderPeopleTree(state.personRecords, state.documents);
    setupPeopleTreeZoom(content);
    return;
  }
  if (state.active === 'map') {
    content.innerHTML = renderMapPage();
    setupMap();
    return;
  }
  if (state.active === 'images/all') {
    content.innerHTML = renderImagesPage();
    setupImageFilters();
    setupSealAnnotations();
    return;
  }
  const allRecordPaths = state.manifest.documents;
  const paths = state.active === 'documents' ? visibleRecordPaths(allRecordPaths) : [state.active];
  const selectedYear = documentYear(state.documents.get(state.record));
  const shouldRestoreRecord = state.active === 'documents'
    && selectedYear
    && (state.lastRenderedDocumentsYear === null || selectedYear !== state.lastRenderedDocumentsYear);
  state.yearHighlightCleanup?.();
  state.yearHighlightCleanup = null;
  if (state.active === 'documents') {
    content.innerHTML = `<div class="documents-layout">${renderYearSidebar(paths, state.recordSource ? paths : allRecordPaths)}<div class="documents-list">${paths.map((path, index) => renderDocument(state.documents.get(path), path, index)).join('')}</div></div>`;
  } else {
    content.innerHTML = paths.map((path, index) => renderDocument(state.documents.get(path), path, index)).join('');
  }
  setupSealAnnotations();
  const diagrams = content.querySelectorAll('.mermaid');
  if (diagrams.length && mermaid) await mermaid.run({ nodes: diagrams });
  if (state.active === 'documents') {
    if (shouldRestoreRecord) restoreRecord(paths);
    setupYearHighlight(paths);
    state.lastRenderedDocumentsYear = documentYear(state.documents.get(state.record));
  }
  scrollToEntryHash();
}
