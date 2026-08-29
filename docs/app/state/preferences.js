const PREFERENCES_KEY = 'rosenberg-viewer-preferences';
const VALID_DISPLAY_MODES = new Set(['english', 'original']);

function normalizeDisplayMode(value) {
  if (VALID_DISPLAY_MODES.has(value)) return value;
  return value === 'both' || value === 'german' || value === 'latin' ? 'original' : 'english';
}

export function loadPreferences(storage) {
  try {
    const raw = JSON.parse((storage || window.localStorage).getItem(PREFERENCES_KEY) || '{}');
    return {
      active: typeof raw.active === 'string' ? raw.active : null,
      place: typeof raw.place === 'string' ? raw.place : null,
      person: typeof raw.person === 'string' ? raw.person : null,
      letter: typeof raw.letter === 'string' ? raw.letter : null,
      letterLabels: Array.isArray(raw.letterLabels) ? raw.letterLabels : [],
      hiddenLetterLabels: Array.isArray(raw.hiddenLetterLabels) ? raw.hiddenLetterLabels : null,
      sealNames: Array.isArray(raw.sealNames) ? raw.sealNames : [],
      sealType: ['contrepalle', 'swans', 'helm', 'full', 'unknown'].includes(raw.sealType) ? raw.sealType : null,
      language: normalizeDisplayMode(raw.language),
      showFacts: raw.showFacts !== false,
      darkMode: raw.darkMode !== false,
    };
  } catch {
    return {
      active: null, place: null, person: null, letter: null,
      letterLabels: [], hiddenLetterLabels: null, sealNames: [], sealType: null,
      language: 'english', showFacts: true, darkMode: true,
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
