import { imageLabels } from '../image-labels.js';
import { buildRelationshipGraph, verifyFamilyGraph, remapSourcePerson } from './relationships.js?v=7';

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
  let lastVerifiedGraph;
  let backgroundRebuild;
  function rebuildOptions() {
    const metadata = state.tree ?? state.personRecords[0]?.familyGraph;
    const limit = metadata?.configuration?.searchLimit;
    return { includeGuesses: true,
      searchLimit: Number.isSafeInteger(limit) && limit > 0 ? limit : 10000 };
  }

  async function loadSnapshot({ autoRebuild = true, familyOnly = false } = {}) {
    const files = await repository.getRepositoryFiles();
    const paths = files.map((file) => typeof file === 'string' ? file : file.path)
      .filter((path) => /^data\/(books|documents|notes|images)\/.*\.json$/.test(path));
    const snapshot = JSON.stringify(files);
    const [placesText, calibrationCitiesText, peopleText, particlesText, documents, tree] = await Promise.all([
      repository.getText('data/places.json'),
      repository.getText('docs/assets/calibration-cities.json'),
      repository.getText('data/people.json'),
      repository.getText('data/nobiliary_particles.md'),
      new Map(await Promise.all(paths.map(async (path) => [path, await repository.getJson(path)]))),
      typeof repository.getFamilyTree === 'function' ? repository.getFamilyTree() : undefined,
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
    state.tree = tree;
    if (tree?.schema >= 4) state.familyView = 'with-guesses';
    if (state.familyGraph?.valid) lastVerifiedGraph = state.familyGraph;
    state.familyVerification = await verifyFamilyGraph(state.personRecords, documents, repository, paths, tree);
    if (tree?.schema >= 4 && !tree.views?.includes('with-guesses')) state.familyVerification = { valid: false, reason: 'The normal tree requires weighted guesses.' };
    state.familyGraph = buildRelationshipGraph(state.personRecords, { tree, view: state.familyView, verification: state.familyVerification });
    state.canRebuildFamilyGraph = typeof repository.rebuildFamilyGraph === 'function' && await repository.isLocalServer();
    state.familyGraph.canRebuild = state.canRebuildFamilyGraph;
    const shouldRebuild = !state.familyGraph.valid && state.canRebuildFamilyGraph && autoRebuild && !backgroundRebuild;
    state.familyGraph.rebuilding = Boolean((autoRebuild && backgroundRebuild) || shouldRebuild);
    if (remapSourcePerson(state, lastVerifiedGraph)) onPersonReassigned();
    if (state.familyGraph.valid) lastVerifiedGraph = state.familyGraph;
    state.familyView = state.familyGraph.view;
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
    if (!familyOnly || state.active === 'tree' || state.person) await renderActive();
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
