import { imageLabels } from '../image-labels.js';
import { buildRelationshipGraph, verifyFamilyGraph, remapSourcePerson } from './relationships.js?v=10';

export function createDataLoader({
  repository,
  state,
  parsePlaces,
  parsePeople,
  buildPlacePattern,
  buildPersonPattern,
  bookSortYear,
  recordHasMissingSourceOrUrl,
  missingRecordLabel,
  greyRecordLabels,
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
    const worker = new Worker(new URL('./verification-worker.js?v=4', import.meta.url), { type: 'module' });
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

  async function loadSnapshot({ autoRebuild = true, familyOnly = false } = {}) {
    const files = await repository.getRepositoryFiles();
    const paths = files.map((file) => typeof file === 'string' ? file : file.path)
      .filter((path) => /^data\/(books|documents|notes|images)\/.*\.json$/.test(path));
    const snapshot = JSON.stringify(files);
    // Books can be displayed independently of the document collection. Load them
    // first so hundreds of unrelated requests do not delay the first page.
    const bookPathsForStartup = paths.filter((path) => path.startsWith('data/books/'));
    const showBookEarly = !familyOnly && bookPathsForStartup.length > 0;
    let earlyBooks;
    if (showBookEarly) {
      const [placesText, peopleText, entries] = await Promise.all([
        repository.getText('data/places.json'), repository.getText('data/people.json'),
        Promise.all(bookPathsForStartup.map(async (path) => [path, await repository.getJson(path)])),
      ]);
      earlyBooks = new Map(entries);
      state.places = parsePlaces(placesText);
      state.personRecords = JSON.parse(peopleText);
      state.people = parsePeople(peopleText);
      state.personPattern = buildPersonPattern(state.people);
      state.placePattern = buildPlacePattern(state.places);
      const ordered = [...bookPathsForStartup].sort((left, right) => bookSortYear(earlyBooks.get(right), right) - bookSortYear(earlyBooks.get(left), left) || left.localeCompare(right));
      state.manifest = { books: ordered.map((path) => ({ path, label: earlyBooks.get(path)?.book || path })), documents: paths.filter((path) => path.startsWith('data/documents/')), notes: paths.includes('data/notes/notes.json'), images: paths.includes('data/images/images.json') ? 'data/images/images.json' : null, collections: [] };
      state.sourceLoading = true;
      state.documents = earlyBooks;
      if (state.active === 'books') state.active = ordered[0];
      renderTabs();
      await renderActive();
    }
    const [placesText, calibrationCitiesText, peopleText, particlesText, documents] = await Promise.all([
      repository.getText('data/places.json'),
      repository.getText('docs/assets/calibration-cities.json'),
      repository.getText('data/people.json'),
      repository.getText('data/nobiliary_particles.md'),
      new Map(await Promise.all(paths.map(async (path) => [path, earlyBooks?.has(path) ? earlyBooks.get(path) : await repository.getJson(path)]))),
    ]);
    state.nobiliaryParticles = particlesText.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    state.places = parsePlaces(placesText);
    state.calibrationCities = parsePlaces(calibrationCitiesText);
    state.personRecords = JSON.parse(peopleText);
    state.people = parsePeople(peopleText);
    state.personPattern = buildPersonPattern(state.people);
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
    state.familyVerification = { valid: false, reason: 'Verifying family graph…' };
    state.familyGraph = buildRelationshipGraph(state.personRecords, { tree: null, view: state.familyView, verification: state.familyVerification });
    state.canRebuildFamilyGraph = typeof repository.rebuildFamilyGraph === 'function' && await repository.isLocalServer();
    state.familyGraph.canRebuild = state.canRebuildFamilyGraph;
    state.familyRepositoryRevision = repository.revision || 0;
    state.snapshot = snapshot;
    if (!recordPaths.some((path) => recordHasMissingSourceOrUrl(path))) state.recordLabels = state.recordLabels.filter((label) => label !== missingRecordLabel);
    if (!Array.isArray(state.hiddenRecordLabels)) state.hiddenRecordLabels = [...greyRecordLabels];
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
    if (!familyOnly) await renderActive();
    const family = await loadFamilyInBackground(state.personRecords, documents, paths, state.familyView);
    state.tree = family.tree;
    if (family.tree && (family.tree.schema === undefined || family.tree.schema >= 4)) state.familyView = 'with-guesses';
    state.familyVerification = family.verification;
    state.familyGraph = family.graph;
    state.familyGraph.canRebuild = state.canRebuildFamilyGraph;
    const shouldRebuild = !state.familyGraph.valid && state.canRebuildFamilyGraph && autoRebuild && !backgroundRebuild;
    state.familyGraph.rebuilding = Boolean((autoRebuild && backgroundRebuild) || shouldRebuild);
    if (remapSourcePerson(state, lastVerifiedGraph)) onPersonReassigned();
    if (state.familyGraph.valid) lastVerifiedGraph = state.familyGraph;
    state.familyView = state.familyGraph.view;
    if (state.active === 'tree' || state.person) await renderActive();
    if (shouldRebuild) {
      onFamilyRebuild();
      backgroundRebuild = (async () => {
        try {
          await repository.rebuildFamilyGraph(rebuildOptions());
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
          if (state.familyGraph) state.familyGraph.rebuilding = false;
        }
      })();
    }
  }

  function loadAll(options) {
    if (!loading) loading = loadSnapshot(options).finally(() => { loading = null; });
    return loading;
  }

  async function rebuildFamilyGraph() {
    onFamilyRebuild();
    await repository.rebuildFamilyGraph(rebuildOptions());
    await loadAll({ autoRebuild: false });
  }

  return { loadAll, rebuildFamilyGraph, waitForFamilyRebuild: () => backgroundRebuild };
}
