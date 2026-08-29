export function createDataLoader({
  repository,
  state,
  parsePlaces,
  parsePeople,
  buildPlacePattern,
  buildPersonPattern,
  bookSortYear,
  letterHasMissingSourceOrUrl,
  missingLetterLabel,
  greyLetterLabels,
  savePreferences,
  renderTabs,
  renderActive,
}) {
  async function loadAll() {
    const files = await repository.getRepositoryFiles();
    const paths = files.map((file) => typeof file === 'string' ? file : file.path);
    const snapshot = JSON.stringify(files);
    const [placesText, calibrationCitiesText, peopleText, documents] = await Promise.all([
      repository.getText('data/places.json'),
      repository.getText('docs/assets/calibration-cities.json'),
      repository.getText('data/people.json'),
      new Map(await Promise.all(paths.map(async (path) => [path, await repository.getJson(path)]))),
    ]);
    state.places = parsePlaces(placesText);
    state.calibrationCities = parsePlaces(calibrationCitiesText);
    state.personRecords = JSON.parse(peopleText);
    state.people = parsePeople(peopleText);
    state.personPattern = buildPersonPattern(state.people);
    state.placePattern = buildPlacePattern(state.places);
    const bookPaths = paths
      .filter((path) => path.startsWith('data/books/'))
      .sort((left, right) => bookSortYear(documents.get(right), right) - bookSortYear(documents.get(left), left) || left.localeCompare(right));
    const letterPaths = paths.filter((path) => path.startsWith('data/letters/'));
    state.manifest = {
      books: bookPaths.map((path) => ({ path, label: documents.get(path)?.book || path })),
      notes: paths.includes('data/notes/notes.json'),
      letters: letterPaths,
    };
    state.documents = documents;
    state.snapshot = snapshot;
    if (!letterPaths.some((path) => letterHasMissingSourceOrUrl(path))) state.letterLabels = state.letterLabels.filter((label) => label !== missingLetterLabel);
    if (!Array.isArray(state.hiddenLetterLabels)) state.hiddenLetterLabels = [...greyLetterLabels];
    state.sealNames = [...new Set(state.sealNames.map((label) => label.includes('?') ? 'unknown' : label.toLocaleLowerCase()).filter(Boolean))];
    if (state.active === 'books') state.active = state.manifest.books[0]?.path || 'letters';
    const reserved = ['letters', 'seals', 'tree', 'map'];
    if (!reserved.includes(state.active) && !paths.includes(state.active)) state.active = state.manifest.books[0]?.path || 'letters';
    savePreferences();
    renderTabs();
    await renderActive();
  }

  return { loadAll };
}
