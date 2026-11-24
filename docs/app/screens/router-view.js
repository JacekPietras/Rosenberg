export async function renderActiveScreen({
  state,
  content,
  status,
  leafletMap,
  destroyMap,
  renderPersonPage,
  renderEntityFactsWithLinks,
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
  renderDocumentWithPersonLinks,
  renderReviewNameLabels,
  setupSealAnnotations,
  setupSealHighlight,
  restoreRecord,
  setupYearHighlight,
  scrollToEntryHash,
  setupMentionNavigation,
  mermaid,
}) {
  const documentRenderTimings = {};
  const renderPhaseStart = performance.now();
  state.documentPersonLinkObserver?.disconnect();
  state.documentReviewLabelObserver?.disconnect();
  status.textContent = '';
  status.classList.remove('error');
  if (state.active !== 'tree' && state.sourceLoading && (state.person || state.place || !state.manifest.books.some((book) => book.path === state.active))) {
    content.textContent = 'Loading sources…';
    return;
  }
  state.sealMarkerCleanup?.();
  state.sealMarkerCleanup = null;
  if (leafletMap && state.active !== 'map') destroyMap();
  const setupDeferredEntityFacts = () => {
    const targets = content.querySelectorAll('[data-deferred-entity-facts]');
    if (!targets.length) return;
    const hydrate = (target) => {
      if (!target.isConnected) return;
      target.innerHTML = renderEntityFactsWithLinks();
      target.removeAttribute('data-deferred-entity-facts');
    };
    const schedule = (target) => {
      const run = () => hydrate(target);
      if (typeof requestIdleCallback === 'function') requestIdleCallback(run, { timeout: 1000 });
      else setTimeout(run, 0);
    };
    if (typeof IntersectionObserver !== 'undefined') {
      state.documentPersonLinkObserver = new IntersectionObserver((entries) => entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        state.documentPersonLinkObserver.unobserve(entry.target);
        schedule(entry.target);
      }), { rootMargin: '250px 0px' });
      targets.forEach((target) => state.documentPersonLinkObserver.observe(target));
    } else targets.forEach(schedule);
  };
  if (state.person) {
    content.innerHTML = renderPersonPage();
    setupDeferredEntityFacts();
    setupFamilyControls();
    setupSealAnnotations();
    setupPersonMap(state.person);
    setupMentionNavigation('person-mention', 'a.place-link, a.person-link');
    return;
  }
  if (state.place) {
    content.innerHTML = renderPlacePage();
    setupDeferredEntityFacts();
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
    content.innerHTML = renderPeopleTree(state.personRecords, state.documents, { graph: state.familyGraph, focus });
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
  const allRecordPaths = state.manifest.documents.filter((path) => state.documents.get(path)?.deleted !== true);
  const filterStart = performance.now();
  const paths = state.active === 'documents' ? visibleRecordPaths(allRecordPaths) : [state.active];
  documentRenderTimings.filterMs = Math.round((performance.now() - filterStart) * 10) / 10;
  const selectedYear = documentYear(state.documents.get(state.record));
  const shouldRestoreRecord = state.active === 'documents'
    && selectedYear
    && (state.lastRenderedDocumentsYear === null || selectedYear !== state.lastRenderedDocumentsYear);
  state.yearHighlightCleanup?.();
  state.yearHighlightCleanup = null;
  const previousDeferredPersonRecognition = state.deferPersonNameRecognition;
  const previousDeferredDocumentLinks = state.deferDocumentMarkupLinks;
  if (state.active === 'documents') state.deferPersonNameRecognition = true;
  const htmlStart = performance.now();
  if (state.active === 'documents') {
    const sidebarStart = performance.now();
    const sidebarHtml = renderYearSidebar(paths, state.recordSource ? paths : allRecordPaths);
    documentRenderTimings.sidebarMs = Math.round((performance.now() - sidebarStart) * 10) / 10;
    const documentHtmlParts = [];
    let documentHtmlLength = 0;
    const slowDocuments = [];
    for (let index = 0; index < paths.length; index++) {
      const path = paths[index];
      state.deferDocumentMarkupLinks = path.startsWith('data/documents/');
      const documentStart = performance.now();
      const html = renderDocument(state.documents.get(path), path, index);
      const duration = performance.now() - documentStart;
      documentHtmlLength += html.length;
      documentHtmlParts.push(html);
      slowDocuments.push({ path, ms: Math.round(duration * 10) / 10, chars: html.length });
    }
    const documentHtml = documentHtmlParts.join('');
    documentRenderTimings.documentHtmlMs = Math.round((performance.now() - htmlStart - documentRenderTimings.sidebarMs) * 10) / 10;
    documentRenderTimings.documentHtmlChars = documentHtmlLength;
    documentRenderTimings.slowestDocuments = slowDocuments.sort((left, right) => right.ms - left.ms).slice(0, 5);
    const domStart = performance.now();
    content.innerHTML = `<div class="documents-layout">${sidebarHtml}<div class="documents-list">${documentHtml}</div></div>`;
    documentRenderTimings.domInsertMs = Math.round((performance.now() - domStart) * 10) / 10;
  } else {
    const documentHtml = paths.map((path, index) => renderDocument(state.documents.get(path), path, index)).join('');
    documentRenderTimings.documentHtmlMs = Math.round((performance.now() - htmlStart) * 10) / 10;
    const domStart = performance.now();
    content.innerHTML = documentHtml;
    documentRenderTimings.domInsertMs = Math.round((performance.now() - domStart) * 10) / 10;
  }
  state.deferPersonNameRecognition = previousDeferredPersonRecognition;
  state.deferDocumentMarkupLinks = previousDeferredDocumentLinks;
  function observeReviewLabelTargets(root) {
    const targets = [
      ...(root.matches?.('[data-review-label-path]') ? [root] : []),
      ...root.querySelectorAll('[data-review-label-path]'),
    ];
    if (!targets.length) return;
    targets.forEach((target) => {
      const path = target.dataset.reviewLabelPath;
      const doc = state.documents.get(path);
      const placeholder = target.querySelector('[data-review-name-labels]');
      if (doc && placeholder) renderReviewNameLabels(doc, path).then((html) => {
        if (!placeholder.isConnected) return;
        if (html) {
          placeholder.outerHTML = html;
        } else placeholder.remove();
        target.querySelector('[data-show-review-labels]')?.remove();
      });
    });
  }
  if (state.active !== 'documents') observeReviewLabelTargets(content);
  const personLinkTargets = content.querySelectorAll('[data-person-links-path]');
  const hydratePersonLinks = (article) => {
    if (!article.isConnected) return;
    const path = article.dataset.personLinksPath;
    const index = Number(article.dataset.personLinksIndex);
    const doc = state.documents.get(path);
    if (!doc) return;
    const template = document.createElement('template');
    template.innerHTML = renderDocumentWithPersonLinks(doc, path, index);
    const renderedArticle = template.content.firstElementChild;
    if (!renderedArticle) return;
    article.innerHTML = renderedArticle.innerHTML;
    article.removeAttribute('data-person-links-path');
    article.removeAttribute('data-person-links-index');
    observeReviewLabelTargets(article);
    const diagrams = article.querySelectorAll('.mermaid');
    if (diagrams.length && mermaid) mermaid.run({ nodes: diagrams });
    if (article.querySelector('.annotated-image img, .seal-crop img, img[data-focus-x]')) setupSealAnnotations();
  };
  if (personLinkTargets.length && typeof IntersectionObserver !== 'undefined') {
    state.documentPersonLinkObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const article = entry.target;
        state.documentPersonLinkObserver.unobserve(article);
        const renderWhenIdle = () => hydratePersonLinks(article);
        if (typeof requestIdleCallback === 'function') requestIdleCallback(renderWhenIdle, { timeout: 1000 });
        else setTimeout(renderWhenIdle, 0);
      });
    }, { rootMargin: '250px 0px' });
    personLinkTargets.forEach((target) => state.documentPersonLinkObserver.observe(target));
  } else if (personLinkTargets.length) {
    personLinkTargets.forEach((article) => {
      const schedule = window.requestIdleCallback || ((callback) => setTimeout(callback, 0));
      schedule(() => hydratePersonLinks(article));
    });
  }
  const setupStart = performance.now();
  setupSealAnnotations();
  const diagrams = content.querySelectorAll('.mermaid');
  if (diagrams.length && mermaid) await mermaid.run({ nodes: diagrams });
  if (state.active === 'documents') {
    if (shouldRestoreRecord) restoreRecord(paths);
    setupYearHighlight(paths);
    state.lastRenderedDocumentsYear = documentYear(state.documents.get(state.record));
  }
  scrollToEntryHash();
  documentRenderTimings.postRenderMs = Math.round((performance.now() - setupStart) * 10) / 10;
  documentRenderTimings.totalMs = Math.round((performance.now() - renderPhaseStart) * 10) / 10;
  if (state.active === 'documents') state.lastDocumentRenderDiagnostics = documentRenderTimings;

  function setupFamilyControls() {
    content.querySelector('[data-family-focus]')?.addEventListener('change', async (event) => {
      await state.changeFamilyFocus?.(event.target.value);
    });
    content.querySelector('[data-family-rebuild]')?.addEventListener('click', async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        await state.rebuildFamilyGraph?.();
      } catch (error) {
        const message = content.querySelector('[data-family-rebuild-status]');
        if (message) message.textContent = `Could not rebuild relationships. ${error.message}`;
        button.disabled = false;
      }
    });
    content.querySelector('[data-family-view]')?.addEventListener('change', async (event) => {
      if (!state.familyGraph?.views.includes(event.target.value)) return;
      state.familyView = event.target.value;
      await state.changeFamilyView?.(state.familyView);
    });
  }
}
