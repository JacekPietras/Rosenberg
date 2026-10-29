// Generated evidence is accepted only after verifying the complete build input.
const sourcePath = /^data\/(books|documents|notes|images)\/.*\.json$/;
const generatedFields = new Set(['wife', 'children', 'relationships', 'familyGraph']);

export function registryIdentities(people) {
  return people.map((person) => Object.fromEntries(Object.entries(person).filter(([key]) => !generatedFields.has(key))));
}

export function resolvePerson(people, reference) {
  const exact = people.filter((person) => person.id && person.id === reference);
  if (exact.length === 1) return { person: exact[0], matches: exact, ambiguous: false };
  const matches = people.filter((person) => person.name?.toLocaleLowerCase() === String(reference).toLocaleLowerCase());
  return { person: matches.length === 1 ? matches[0] : undefined, matches, ambiguous: matches.length > 1 };
}

export function canonicalEvidence(value) {
  const encode = (item) => {
    if (Array.isArray(item)) return ['array', item.map(encode)];
    if (item && typeof item === 'object') return ['object', Object.keys(item).sort().map((key) => [key, encode(item[key])])];
    if (typeof item === 'number') {
      if (!Number.isFinite(item)) throw new Error('Non-finite evidence number');
      const bytes = new Uint8Array(8);
      new DataView(bytes.buffer).setFloat64(0, item || 0, false);
      return ['number', [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('')];
    }
    return item;
  };
  return JSON.stringify(encode(value)).replace(/[\u007f-\uffff]/g, (character) => `\\u${character.charCodeAt(0).toString(16).padStart(4, '0')}`);
}

export async function evidenceFingerprint(value) {
  const bytes = new TextEncoder().encode(canonicalEvidence(value));
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  return `sha256:${[...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('')}`;
}

export function resolveEvidencePointer(document, pointer) {
  if (!pointer.startsWith('/')) throw new Error('Invalid JSON Pointer');
  return pointer.slice(1).split('/').reduce((value, token) => {
    const key = token.replaceAll('~1', '/').replaceAll('~0', '~');
    if (value == null || !Object.hasOwn(value, key)) throw new Error('Stale source pointer');
    return value[key];
  }, document);
}

export async function verifyFamilyGraph(people, documents, repository, paths = [...documents.keys()]) {
  const metadata = people[0]?.familyGraph;
  if (!metadata) return { valid: false, reason: 'Generated build metadata is absent.' };
  try {
    if (metadata.schema !== 1 || metadata.engine !== '1' || metadata.policy !== '1'
      || !['facts', 'facts,with-guesses'].includes(metadata.views?.join(','))
      || !Number.isInteger(metadata.configuration?.searchLimit) || metadata.configuration.searchLimit < 1
      || !['data/people.json', 'data/places.json', 'data/names.md'].every((path) => Object.hasOwn(metadata.inputs || {}, path))
      || !metadata.inputs || metadata.fingerprint !== await evidenceFingerprint(metadata.inputs)) throw new Error('Invalid build metadata');
    const sources = Object.keys(metadata.inputs).filter((path) => sourcePath.test(path)).sort();
    if (JSON.stringify(sources) !== JSON.stringify(paths.filter((path) => sourcePath.test(path)).sort())) throw new Error('The source file set changed');
    await Promise.all(Object.entries(metadata.inputs).map(async ([path, expected]) => {
      if (path.split('/').includes('..') || !/^(data|scripts)\//.test(path)) throw new Error('Invalid build input path');
      const value = path === 'data/people.json' ? registryIdentities(people)
        : documents.has(path) ? documents.get(path)
          : path.endsWith('.json') ? await repository.getJson(path) : await repository.getText(path);
      if (await evidenceFingerprint(value) !== expected) throw new Error(`Build input changed: ${path}`);
    }));
    for (const person of people) {
      for (const edge of person.relationships || []) {
        for (const derivation of edge.derivations || []) {
          let supportingRelationship = false;
          for (const source of derivation.sources || []) {
            if (!sourcePath.test(source.path) || !Object.hasOwn(metadata.inputs, source.path)
              || !/\/(facts|guesses)\/[0-9]+$/.test(source.pointer)) throw new Error('Invalid evidence source');
            const assertion = resolveEvidencePointer(documents.get(source.path), source.pointer);
            if (await evidenceFingerprint(assertion) !== source.fingerprint) throw new Error('Source assertion changed');
            supportingRelationship ||= assertion.type === edge.type;
          }
          if (!supportingRelationship) throw new Error('Missing relationship assertion');
        }
      }
    }
    for (const view of metadata.views) {
      const graph = buildRelationshipGraph(people, { view, verification: { valid: true } });
      if (!graph.valid) throw new Error(graph.reason);
    }
    return { valid: true, reason: '' };
  } catch (error) {
    return { valid: false, reason: `${error.message}. Rebuild family relationships to verify the evidence.` };
  }
}

export function buildRelationshipGraph(people, { view = 'facts', verification } = {}) {
  const ids = new Set(people.filter((person) => person.id).map((person) => person.id));
  const records = people.map((person, index) => {
    let key = person.id || `@registry/${index}`;
    if (!person.id) while (ids.has(key)) key += '~';
    return { ...person, _treeKey: key };
  });
  const generated = people.some((person) => Object.hasOwn(person, 'relationships') || person.familyGraph);
  const metadata = people[0]?.familyGraph;
  const views = generated ? metadata?.views || [] : ['facts'];
  const selectedView = views.includes(view) ? view : 'facts';
  const result = { records, edges: [], reverse: new Map(), generated, views, view: selectedView,
    valid: !generated || verification?.valid === true, reason: generated && !verification?.valid ? verification?.reason || 'Evidence has not been verified.' : '', metadata };
  if (!result.valid) return result;
  const resolve = (reference) => {
    const exact = records.filter((person) => person.id && person.id === reference);
    if (exact.length === 1) return exact[0];
    const matches = records.filter((person) => person.name === reference);
    return matches.length === 1 ? matches[0] : undefined;
  };
  const seen = new Set();
  const add = (person, target, type, derivations = [], term = '') => {
    if (!target || person._treeKey === target._treeKey) throw new Error('Invalid or ambiguous relationship endpoint');
    let left = person._treeKey, right = target._treeKey;
    if (type !== 'parent' && left > right) [left, right] = [right, left];
    const key = JSON.stringify([left, right, type, term]);
    if (seen.has(key)) {
      if (generated) throw new Error('Duplicate generated relationship');
      return;
    }
    seen.add(key);
    result.edges.push({ person: left, of: right, type, term, derivations,
      inferred: derivations.length > 0 && derivations.every((d) => d.identity === 'inferred'),
      usesGuesses: derivations.length > 0 && derivations.every((d) => d.usesGuesses) });
  };
  try {
    for (const person of records) {
      if (generated) {
        if (!Array.isArray(person.relationships) || Object.hasOwn(person, 'wife') || Object.hasOwn(person, 'children')) throw new Error('Incomplete generated registry');
        for (const edge of person.relationships) {
          if (!['parent', 'spouse', 'sibling', 'kin'].includes(edge.type)
            || (edge.type === 'kin' && !edge.term?.trim()) || !edge.derivations?.length) throw new Error('Invalid generated relationship');
          const derivations = edge.derivations.filter((d) => d.view === selectedView);
          for (const d of edge.derivations) {
            if (!views.includes(d.view) || !['anchored', 'reviewed', 'inferred'].includes(d.identity)
              || typeof d.usesGuesses !== 'boolean' || d.view === 'facts' && d.usesGuesses || !d.sources?.length
              || d.sources.some((source) => source.pointer.includes('/guesses/') && !d.usesGuesses)) throw new Error('Invalid derivation');
          }
          if (derivations.length) add(person, resolve(edge.of), edge.type, derivations, edge.term || '');
        }
      } else {
        for (const reference of person.children || []) {
          const target = resolve(reference);
          if (target && target._treeKey !== person._treeKey) add(person, target, 'parent');
        }
        const spouse = resolve(person.wife);
        if (spouse && spouse._treeKey !== person._treeKey) add(person, spouse, 'spouse');
      }
    }
    if (generated) {
      const active = new Set(), complete = new Set();
      const children = new Map(records.map((person) => [person._treeKey, []]));
      result.edges.filter((edge) => edge.type === 'parent').forEach((edge) => children.get(edge.person).push(edge.of));
      const visit = (key) => {
        if (active.has(key)) throw new Error('Generated parentage cycle');
        if (complete.has(key)) return;
        active.add(key); children.get(key).forEach(visit); active.delete(key); complete.add(key);
      };
      records.forEach((person) => visit(person._treeKey));
    }
    result.edges.forEach((edge) => [edge.person, edge.of].forEach((key) => {
      if (!result.reverse.has(key)) result.reverse.set(key, []);
      result.reverse.get(key).push(edge);
    }));
  } catch (error) {
    result.valid = false; result.reason = error.message; result.edges = []; result.reverse.clear();
  }
  return result;
}
