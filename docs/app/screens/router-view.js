export async function renderActiveScreen({
  state,
  content,
  status,
  leafletMap,
  destroyMap,
  renderPersonPage,
  setupPersonMap,
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
  if (state.sourceLoading && (state.person || state.place || !state.manifest.books.some((book) => book.path === state.active))) {
    content.textContent = 'Loading sources…';
    return;
  }
  state.sealMarkerCleanup?.();
  state.sealMarkerCleanup = null;
  if (leafletMap && state.active !== 'map') destroyMap();
  if (state.person) {
    content.innerHTML = renderPersonPage();
    setupFamilyControls();
    setupSealAnnotations();
    setupPersonMap(state.person);
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
    const focus = state.familyFocus && (state.familyFocus === 'all' || state.familyGraph?.components?.some((c) => c.key === state.familyFocus))
      ? state.familyFocus : state.familyGraph?.defaultFocus;
    content.innerHTML = renderPeopleTree(state.personRecords, state.documents, { graph: state.familyGraph, focus, showKins: state.showKins });
    setupFamilyControls();
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

  function setupFamilyControls() {
    content.querySelector('[data-show-kins]')?.addEventListener('change', async (event) => {
      await state.changeShowKins?.(event.target.checked);
    });
    content.querySelector('[data-family-focus]')?.addEventListener('change', async (event) => {
      await state.changeFamilyFocus?.(event.target.value);
    });
    content.querySelector('[data-family-rebuild]')?.addEventListener('click', async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = 'Rebuilding…';
      try {
        await state.rebuildFamilyGraph?.();
      } catch (error) {
        const message = content.querySelector('[data-family-rebuild-status]');
        if (message) message.textContent = `Could not rebuild relationships. ${error.message}`;
        button.disabled = false;
        button.textContent = 'Retry rebuild';
      }
    });
    content.querySelector('[data-family-view]')?.addEventListener('change', async (event) => {
      if (!state.familyGraph?.views.includes(event.target.value)) return;
      state.familyView = event.target.value;
      await state.changeFamilyView?.(state.familyView);
    });
  }
}
