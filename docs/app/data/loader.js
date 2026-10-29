import { imageLabels } from '../image-labels.js';
import { buildRelationshipGraph, verifyFamilyGraph } from './relationships.js';

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
}) {
  async function loadAll() {
    const files = await repository.getRepositoryFiles();
    const paths = files.map((file) => typeof file === 'string' ? file : file.path)
      .filter((path) => /^data\/(books|documents|notes|images)\/.*\.json$/.test(path));
    const snapshot = JSON.stringify(files);
    const [placesText, calibrationCitiesText, peopleText, particlesText, documents] = await Promise.all([
      repository.getText('data/places.json'),
      repository.getText('docs/assets/calibration-cities.json'),
      repository.getText('data/people.json'),
      repository.getText('data/nobiliary_particles.md'),
      new Map(await Promise.all(paths.map(async (path) => [path, await repository.getJson(path)]))),
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
    state.familyVerification = await verifyFamilyGraph(state.personRecords, documents, repository, paths);
    state.familyGraph = buildRelationshipGraph(state.personRecords, { view: state.familyView, verification: state.familyVerification });
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
    renderTabs();
    await renderActive();
  }

  return { loadAll };
}
