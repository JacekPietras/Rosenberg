export function createCitationIndex({ state }) {
  function sourceCitations(source) {
    const values = Array.isArray(source) ? source : [source];
    return values.flatMap((value) => String(value || '').split(/\s*;\s*/)).map((value) => value.trim()).filter(Boolean);
  }
  function entryHasSource(entry, source) { return sourceCitations(entry?.source).includes(String(source || '').trim()); }
  function recordHasSource(path, source) { return (state.documents.get(path)?.entries || []).some((entry) => entryHasSource(entry, source)); }
  function recordForSource(source) {
    if (!state.manifest?.documents || !source) return null;
    const values = Array.isArray(source) ? source : [source];
    const sources = values.flatMap((value) => [value, ...String(value).split(/\s*;\s*/)]).filter((value, index, all) => value && all.indexOf(value) === index);
    return sources.reduce((match, citation) => match || state.manifest.documents.reduce((found, path) => {
      if (found) return found;
      const entries = state.documents.get(path)?.entries || [];
      const entryIndex = entries.findIndex((entry) => Array.isArray(entry.source) ? entry.source.includes(citation) : entry.source === citation);
      return entryIndex >= 0 ? { path, entry: entries[entryIndex], entryIndex } : null;
    }, null), null);
  }
  return { sourceCitations, entryHasSource, recordHasSource, recordForSource };
}
