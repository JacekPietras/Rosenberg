import { imageLabels } from '../image-labels.js';
import { buildSourcePersonPattern } from './person-name-recognition.js?v=3';
import { buildRelationshipGraph, verifyFamilyGraph, remapSourcePerson } from './relationships.js?v=11';

export function createDataLoader({
  repository,
  state,
  parsePlaces,
  parsePeople,
  buildPlacePattern,
  buildPersonPattern,
  bookSortYear,
  recordHasMissingSource,
  recordHasMissingUrl,
  distinctFamilies,
  savePreferences,
  renderTabs,
  renderActive,
  onFamilyRebuild = () => {},
  onPersonReassigned = () => {},
}) {
  let loading;
  async function loadFamilyInBackground(people, documents, paths, view) {
    if (typeof Worker === 'undefined') {
      const tree = typeof repository.getFamilyTree === 'function' ? await repository.getFamilyTree() : undefined;
      let verification = await verifyFamilyGraph(people, documents, repository, paths, tree);
      if (tree?.schema >= 4 && !tree.views?.includes('with-guesses')) verification = { valid: false, reason: 'The normal tree requires weighted guesses.' };
      return { tree, verification, graph: buildRelationshipGraph(people, { tree, view: tree && (tree.schema === undefined || tree.schema >= 4) ? 'with-guesses' : view, verification }) };
    }
    const worker = new Worker(new URL('./verification-worker.js?v=5', import.meta.url), { type: 'module' });
    try {
      return await new Promise((resolve, reject) => {
        worker.onmessage = (event) => event.data.error ? reject(new Error(event.data.error)) : resolve(event.data.result);
        worker.onerror = (event) => reject(new Error(event.message || 'Family verification worker failed'));
        worker.postMessage({ people, documents, paths, view, location: { hostname: window.location.hostname, pathname: window.location.pathname, href: window.location.href } });
      });
    } finally { worker.terminate(); }
  }
  let lastVerifiedGraph;
  let backgroundRebuild;
  function rebuildOptions() {
    const metadata = state.tree ?? state.personRecords[0]?.familyGraph;
    const limit = metadata?.configuration?.searchLimit;
    return { searchLimit: Number.isSafeInteger(limit) && limit > 0 ? limit : 10000 };
  }
  async function reportRebuildProgress(stage) {
    if (!state.familyGraph?.rebuilding) return;
    state.familyGraph.rebuildStage = stage;
    if (state.active === 'tree') await renderActive();
  }

  async function loadSnapshot({ autoRebuild = true, familyOnly = false } = {}) {
    const loadStarted = performance.now();
    const timings = {};
    const mark = (name) => { timings[name] = performance.now(); };
    const elapsed = (start, end) => Math.round((timings[end] - timings[start]) * 10) / 10;
    if (state.active === 'tree' && !state.person && !state.place) state.treeLoading = false;
    mark('filesStart');
    const files = await repository.getRepositoryFiles();
    mark('filesEnd');
    const paths = files.map((file) => typeof file === 'string' ? file : file.path)
      .filter((path) => /^data\/(books|documents|notes|images)\/.*\.json$/.test(path));
    const snapshot = JSON.stringify(files);
    // Books can be displayed independently of the document collection. Load them
    // first so hundreds of unrelated requests do not delay the first page.
    const bookPathsForStartup = paths.filter((path) => path.startsWith('data/books/'));
    const showBookEarly = !familyOnly && bookPathsForStartup.length > 0;
    let earlyBooks;
    if (showBookEarly) {
      const [placesText, peopleText, namesText, particlesText, personNameTitlesText, entries] = await Promise.all([
        repository.getText('data/places.json'), repository.getText('data/people.json'),
        repository.getText('data/names.md'), repository.getText('data/nobiliary_particles.md'),
        Promise.all(['data/titles-age.md', 'data/titles-office.md'].map((path) => repository.getText(path))).then((texts) => texts.join('\n')),
        Promise.all(bookPathsForStartup.map(async (path) => [path, await repository.getJson(path)])),
      ]);
      earlyBooks = new Map(entries);
      state.places = parsePlaces(placesText);
      state.personRecords = JSON.parse(peopleText);
      state.people = parsePeople(peopleText);
      state.personPattern = buildPersonPattern(state.people);
      state.personNameTitlesText = personNameTitlesText;
      state.sourcePersonPattern = buildSourcePersonPattern(namesText, particlesText, state.places, personNameTitlesText);
      state.buildingPattern = buildPlacePattern(state.places.filter((place) => ['castle', 'church'].includes(place.category)));
      state.placePattern = buildPlacePattern(state.places);
      const ordered = [...bookPathsForStartup].sort((left, right) => bookSortYear(earlyBooks.get(right), right) - bookSortYear(earlyBooks.get(left), left) || left.localeCompare(right));
      state.manifest = { books: ordered.map((path) => ({ path, label: earlyBooks.get(path)?.book || path })), documents: paths.filter((path) => path.startsWith('data/documents/')), notes: paths.includes('data/notes/notes.json'), images: paths.includes('data/images/images.json') ? 'data/images/images.json' : null, collections: [] };
      state.sourceLoading = true;
      state.documents = earlyBooks;
      if (state.active === 'books') state.active = ordered[0];
      renderTabs();
      await renderActive();
    }
    mark('sourcesStart');
    const [placesText, calibrationCitiesText, peopleText, particlesText, namesText, personNameTitlesText, distinctFamiliesText, documents] = await Promise.all([
      repository.getText('data/places.json'),
      repository.getText('docs/assets/calibration-cities.json'),
      repository.getText('data/people.json'),
      repository.getText('data/nobiliary_particles.md'),
      repository.getText('data/names.md'),
      Promise.all(['data/titles-age.md', 'data/titles-office.md'].map((path) => repository.getText(path))).then((texts) => texts.join('\n')),
      repository.getText('data/distinctFamilies.md'),
      new Map(await Promise.all(paths.map(async (path) => [path, earlyBooks?.has(path) ? earlyBooks.get(path) : await repository.getJson(path)]))),
    ]);
    mark('sourcesEnd');
    mark('prepareStart');
    distinctFamilies.clear();
    distinctFamiliesText.split(/\r?\n/).map((line) => line.replace(/#.*/, '').trim().toLocaleLowerCase()).filter(Boolean).forEach((label) => distinctFamilies.add(label));
    if (Array.isArray(state.hiddenRecordLabels)) {
      const excludedDistinct = state.hiddenRecordLabels.some((label) => distinctFamilies.has(label));
      state.hiddenRecordLabels = state.hiddenRecordLabels.filter((label) => !distinctFamilies.has(label));
      if (excludedDistinct && !state.hiddenRecordLabels.includes('distinct')) state.hiddenRecordLabels.push('distinct');
    }
    const selectedDistinct = state.recordLabels.some((label) => distinctFamilies.has(label));
    state.recordLabels = state.recordLabels.filter((label) => !distinctFamilies.has(label));
    if (selectedDistinct && !state.recordLabels.includes('distinct')) state.recordLabels.push('distinct');
    state.nobiliaryParticles = particlesText.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    state.places = parsePlaces(placesText);
    state.calibrationCities = parsePlaces(calibrationCitiesText);
    state.personRecords = JSON.parse(peopleText);
    state.people = parsePeople(peopleText);
    state.personPattern = buildPersonPattern(state.people);
    state.personNameTitlesText = personNameTitlesText;
    state.sourcePersonPattern = buildSourcePersonPattern(namesText, particlesText, state.places, personNameTitlesText);
    state.buildingPattern = buildPlacePattern(state.places.filter((place) => ['castle', 'church'].includes(place.category)));
    state.placePattern = buildPlacePattern(state.places);
    const bookPaths = paths
      .filter((path) => path.startsWith('data/books/'))
      .sort((left, right) => bookSortYear(documents.get(right), right) - bookSortYear(documents.get(left), left) || left.localeCompare(right));
    const recordPaths = paths.filter((path) => path.startsWith('data/documents/'));
    state.manifest = {
      books: bookPaths.map((path) => ({ path, label: documents.get(path)?.book || path })),
      notes: paths.includes('data/notes/notes.json'),
      documents: recordPaths,
      images: paths.find((path) => path === 'data/images/images.json') || null,
      collections: (documents.get('data/images/images.json')?.entries || []).filter((item) => imageLabels(item).includes('effigy')),
    };
    state.documents = documents;
    state.sourceLoading = false;
    if (state.familyGraph?.valid) lastVerifiedGraph = state.familyGraph;
    if (!state.familyGraph) {
      state.familyVerification = { valid: false, reason: 'Open the family tree to verify its saved graph.' };
      state.familyGraph = buildRelationshipGraph(state.personRecords, { tree: null, view: state.familyView, verification: state.familyVerification });
    }
    state.canRebuildFamilyGraph = typeof repository.rebuildFamilyGraph === 'function' && await repository.isLocalServer();
    state.familyGraph.canRebuild = state.canRebuildFamilyGraph;
    state.familyRepositoryRevision = repository.revision || 0;
    state.snapshot = snapshot;
    if (state.person) {
      const tree = await repository.getFamilyTree();
      const verification = tree ? { valid: true, reason: '' } : { valid: false, reason: 'Saved family tree is unavailable.' };
      state.tree = tree;
      state.familyVerification = verification;
      state.familyGraph = buildRelationshipGraph(state.personRecords, { tree, view: state.familyView, verification });
      state.familyView = state.familyGraph.view;
      if (remapSourcePerson(state, lastVerifiedGraph)) onPersonReassigned();
    }
    const hasMissingSource = recordPaths.some(recordHasMissingSource);
    const hasMissingUrl = recordPaths.some(recordHasMissingUrl);
    state.recordLabels = state.recordLabels.flatMap((label) => label === 'missing'
      ? ['missing source', 'missing url']
      : label === 'missing source' && !hasMissingSource || label === 'missing url' && !hasMissingUrl ? [] : [label]);
    if (!Array.isArray(state.hiddenRecordLabels)) state.hiddenRecordLabels = ['distinct'];
    state.sealNames = [...new Set(state.sealNames.map((label) => label.includes('?') ? 'unknown' : label.toLocaleLowerCase()).filter(Boolean))];
    state.imageRegions = [...new Set((state.imageRegions || []).map((name) => {
      const value = String(name).trim().toLocaleLowerCase();
      return value === 'unknown' ? '__no_region__' : value;
    }).filter(Boolean))];
    if (state.active === 'books') state.active = state.manifest.books[0]?.path || 'documents';
    if (state.active === 'images' || state.active === 'armorials' || state.active === 'images/armorials' || state.active === 'images/effigies') state.active = 'images/all';
    const reserved = ['documents', 'seals', 'tree', 'map', 'images/all'];
    if (!reserved.includes(state.active) && !paths.includes(state.active)) state.active = state.manifest.books[0]?.path || 'documents';
    savePreferences();
    if (!familyOnly) renderTabs();
    if (!familyOnly) {
      mark('prepareEnd');
      mark('renderStart');
      await renderActive();
      mark('renderEnd');
    }
    if (!familyOnly && state.active === 'documents' && !state.person && !state.place && typeof repository.isLocalServer === 'function' && await repository.isLocalServer()) {
      const report = `Documents page load: total=${Math.round(performance.now() - loadStarted)}ms; file-list=${elapsed('filesStart', 'filesEnd')}ms; sources=${elapsed('sourcesStart', 'sourcesEnd')}ms (${paths.length} files); prepare=${elapsed('prepareStart', 'prepareEnd')}ms; render=${elapsed('renderStart', 'renderEnd')}ms`;
      fetch('/api/heartbeat-diagnostics', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: report }), keepalive: true,
      }).catch(() => {});
    }
    const treeScreenVisible = state.active === 'tree' && !state.person && !state.place;
    if (treeScreenVisible) {
      // Put the saved graph on screen before fingerprint verification. The
      // verification below can then run while the user sees the current tree.
      const savedTree = await repository.getFamilyTree();
      state.tree = savedTree;
      state.familyVerification = { valid: Boolean(savedTree), reason: 'Checking saved graph inputs.' };
      state.familyGraph = buildRelationshipGraph(state.personRecords, { tree: savedTree, view: state.familyView, verification: state.familyVerification });
      state.familyGraph.canRebuild = state.canRebuildFamilyGraph;
      state.familyGraph.checking = true;
      state.familyGraph.rebuildStage = '';
      state.treeLoading = false;
      state.familyView = state.familyGraph.view;
      await renderActive();
      const family = await loadFamilyInBackground(state.personRecords, documents, paths, state.familyView);
      state.tree = family.tree;
      if (family.tree && (family.tree.schema === undefined || family.tree.schema >= 4)) state.familyView = 'with-guesses';
      state.familyVerification = family.verification;
      state.familyGraph = family.graph;
      state.familyGraph.checking = false;
      state.familyGraph.canRebuild = state.canRebuildFamilyGraph;
      const shouldRebuild = !state.familyGraph.valid && state.canRebuildFamilyGraph && autoRebuild && !backgroundRebuild;
      if (shouldRebuild && family.tree) {
        // Keep displaying the saved graph while its replacement is calculated.
        // Verification still controls whether we start the rebuild; it should
        // not blank a usable saved tree during that work.
        state.familyGraph = buildRelationshipGraph(state.personRecords, {
          tree: family.tree,
          view: state.familyView,
          verification: { valid: true, reason: '' },
        });
        state.familyGraph.canRebuild = state.canRebuildFamilyGraph;
      }
      state.familyGraph.rebuilding = Boolean((autoRebuild && backgroundRebuild) || shouldRebuild);
      state.treeLoading = false;
      if (remapSourcePerson(state, lastVerifiedGraph)) onPersonReassigned();
      if (state.familyGraph.valid) lastVerifiedGraph = state.familyGraph;
      state.familyView = state.familyGraph.view;
      await renderActive();
      if (shouldRebuild) {
        state.familyGraph.rebuildStage = 'Rebuilding relationships; this can take several minutes';
        await renderActive();
        onFamilyRebuild();
        backgroundRebuild = (async () => {
          try {
            await repository.rebuildFamilyGraph(rebuildOptions(), reportRebuildProgress);
            // A refresh may already be loading when the rebuild finishes.
            await new Promise((resolve) => setTimeout(resolve, 0));
            if (loading) await loading;
            await loadAll({ autoRebuild: false, familyOnly: true });
          } catch (error) {
            state.familyGraph.rebuilding = false;
            state.familyGraph.rebuildError = error.message;
            if (state.active === 'tree') await renderActive();
          } finally {
            backgroundRebuild = null;
            if (state.familyGraph) {
              state.familyGraph.rebuilding = false;
              state.familyGraph.rebuildStage = '';
            }
          }
        })();
      }
    } else if (state.person) {
      await renderActive();
    }
  }

  function loadAll(options) {
    if (!loading) loading = loadSnapshot(options).catch((error) => {
      state.treeLoading = false;
      throw error;
    }).finally(() => { loading = null; });
    return loading;
  }

  async function rebuildFamilyGraph() {
    onFamilyRebuild();
    if (state.familyGraph) {
      state.familyGraph.rebuilding = true;
      state.familyGraph.rebuildStage = 'Rebuilding relationships; this can take several minutes';
      await renderActive();
    }
    try {
      await repository.rebuildFamilyGraph(rebuildOptions(), reportRebuildProgress);
    } catch (error) {
      if (state.familyGraph) {
        state.familyGraph.rebuilding = false;
        state.familyGraph.rebuildError = error.message;
      }
      await renderActive();
      throw error;
    }
    await loadAll({ autoRebuild: false });
  }

  return { loadAll, rebuildFamilyGraph, waitForFamilyRebuild: () => backgroundRebuild };
}
