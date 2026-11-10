export function markSavedSnapshot(state, path, version) {
  if (!state.snapshot) return;
  try {
    const files = JSON.parse(state.snapshot);
    const file = files.find((item) => (typeof item === 'string' ? item : item.path) === path);
    if (!file) return;
    if (typeof file === 'string') {
      // Local repository listings include versions; leave legacy listings alone.
      return;
    }
    file.version = version;
    state.snapshot = JSON.stringify(files);
  } catch {
    // An unavailable snapshot will be refreshed by the next poll.
  }
}
