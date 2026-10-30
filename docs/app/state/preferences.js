const PREFERENCES_KEY = 'rosenberg-viewer-preferences';
const VALID_DISPLAY_MODES = new Set(['english', 'original']);

function normalizeDisplayMode(value) {
  if (VALID_DISPLAY_MODES.has(value)) return value;
  return value === 'both' || value === 'german' || value === 'latin' ? 'original' : 'english';
}

export function loadPreferences(storage) {
  const normalizePath = (path) => typeof path === 'string' ? path.replace(/^data\/letters\//, 'data/documents/').replace(/^letters$/, 'documents') : null;
  try {
    const raw = JSON.parse((storage || window.localStorage).getItem(PREFERENCES_KEY) || '{}');
    return {
      active: normalizePath(raw.active),
      place: typeof raw.place === 'string' ? raw.place : null,
      person: typeof raw.person === 'string' ? raw.person : null,
      record: normalizePath(raw.record || raw.letter),
      recordLabels: Array.isArray(raw.recordLabels) ? raw.recordLabels : (Array.isArray(raw.letterLabels) ? raw.letterLabels : []),
      hiddenRecordLabels: Array.isArray(raw.hiddenRecordLabels) ? raw.hiddenRecordLabels : (Array.isArray(raw.hiddenLetterLabels) ? raw.hiddenLetterLabels : null),
      sealNames: Array.isArray(raw.sealNames) ? raw.sealNames : [],
      sealType: ['contrepalle', 'swans', 'helm', 'full', 'unknown'].includes(raw.sealType) ? raw.sealType : null,
      imageRegions: Array.isArray(raw.imageRegions) ? raw.imageRegions : [],
      language: normalizeDisplayMode(raw.language),
      showFacts: raw.showFacts !== false,
      familyView: raw.familyView === 'with-guesses' ? 'with-guesses' : 'facts',
      familyFocus: typeof raw.familyFocus === 'string' ? raw.familyFocus : null,
      showKins: raw.showKins === true,
      darkMode: raw.darkMode !== false,
    };
  } catch {
    return {
      active: null, place: null, person: null, record: null,
      recordLabels: [], hiddenRecordLabels: null, sealNames: [], sealType: null, imageRegions: [],
      language: 'english', showFacts: true, darkMode: true, familyView: 'facts', showKins: false,
    };
  }
}

export function savePreferences(preferences, storage) {
  try {
    (storage || window.localStorage).setItem(PREFERENCES_KEY, JSON.stringify(preferences));
  } catch {
    // Preferences are optional; rendering should continue if storage is unavailable.
  }
}
