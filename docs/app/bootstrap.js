import { createStore } from './state/store.js';
import { loadPreferences, savePreferences } from './state/preferences.js';
import { createRepository } from './data/repository.js';
import { parseRoute } from './state/route.js';
import { startViewer } from './viewer.js?v=56';

/**
 * Composition root for the browser viewer.
 *
 * The composition root owns startup dependencies; feature modules receive
 * them explicitly through the viewer entry point.
 */
export function startApplication() {
  const preferences = loadPreferences();
  const store = createStore({
    preferences,
    route: parseRoute(window.location),
  });
  const repository = createRepository();

  return startViewer({
    store,
    repository,
    preferences,
    savePreferences: (nextPreferences) => savePreferences(nextPreferences),
  });
}
