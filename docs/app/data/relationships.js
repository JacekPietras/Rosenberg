// Generated evidence is accepted only after verifying the complete build input.
const sourcePath = /^data\/(books|documents|notes|images)\/.*\.json$/;

export function registryIdentities(people) {
  return people.map((person) => Object.fromEntries(['id', 'name'].filter((key) => Object.hasOwn(person, key)).map((key) => [key, person[key]])));
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

export function expandEvidenceGraph(graph) {
  if (!graph?.sources) return graph;
  const source = (index) => {
    if (!Number.isInteger(index) || index < 0 || index >= graph.sources.length) throw new Error('Invalid reconstructed source index');
    return graph.sources[index];
  };
  return { nodes: graph.nodes.map((node) => ({ ...node,
    mentions: node.mentions.map((mention) => ({ ...mention, source: source(mention.source) })),
    identitySources: node.identitySources.map(source) })),
  relationships: graph.relationships.map((edge) => ({ ...edge,
    derivations: edge.derivations.map((d) => ({ ...d, sources: d.sources.map(source) })) })),
  comparisons: (graph.comparisons || []).map((comparison) => ({ ...comparison, sources: comparison.sources.map(source) })) };
}



function treeMetadata(value) {
  return value && value.schema === undefined && value.views === undefined ? { ...value, views: ['with-guesses'] } : value;
}

export async function verifyFamilyGraph(people, documents, repository, paths = [...documents.keys()], tree) {
  const metadata = treeMetadata(tree === undefined ? people[0]?.familyGraph : tree);
  if (!metadata) return { valid: false, reason: 'Generated build metadata is absent.' };
  try {
    const version = metadata.schema === undefined || metadata.schema === 1 && metadata.engine === '1' && metadata.policy === '1'
      || metadata.schema === 2 && metadata.engine === '2' && metadata.policy === '2'
      || metadata.schema === 3 && metadata.engine === '3' && metadata.policy === '2'
      || metadata.schema === 4 && metadata.engine === '4' && metadata.policy === '3'
      || metadata.schema === 4 && metadata.engine === '5' && metadata.policy === '4'
      || metadata.schema === 4 && metadata.engine === '6' && metadata.policy === '4';
    if (!version
      || !['facts', 'with-guesses', 'facts,with-guesses'].includes(metadata.views?.join(','))
      || !Number.isInteger(metadata.configuration?.searchLimit) || metadata.configuration.searchLimit < 1
      || !['data/people.json', 'data/places.json', 'data/names.md'].every((path) => Object.hasOwn(metadata.inputs || {}, path))
      || !metadata.inputs || metadata.fingerprint !== await evidenceFingerprint(metadata.inputs)) throw new Error('Invalid build metadata');
    if (tree !== undefined && people.some((person) => !person.id || Object.keys(person).some((key) => !['id', 'name'].includes(key)))) throw new Error('Confirmed people support only id and name');
    if (Object.hasOwn(metadata.inputs, 'data/tree.json')) throw new Error('Generated tree cannot be its own input');
    const sources = Object.keys(metadata.inputs).filter((path) => sourcePath.test(path)).sort();
    if (JSON.stringify(sources) !== JSON.stringify(paths.filter((path) => sourcePath.test(path)).sort())) throw new Error('The source file set changed');
    await Promise.all(Object.entries(metadata.inputs).map(async ([path, expected]) => {
      if (path.split('/').includes('..') || !/^data\/.*\.(json|md)$/.test(path)) throw new Error('Invalid build input path');
      const value = path === 'data/people.json' ? registryIdentities(people)
        : documents.has(path) ? documents.get(path)
          : path.endsWith('.json') ? await repository.getJson(path) : await repository.getText(path);
      if (await evidenceFingerprint(value) !== expected) throw new Error(`Build input changed: ${path}`);
    }));
    let settings;
    if ((metadata.schema === undefined || metadata.schema >= 4)) {
      if (!Object.hasOwn(metadata.inputs, 'data/matching.json')) throw new Error('Missing global probability configuration');
      settings = await repository.getJson('data/matching.json');
      if (await evidenceFingerprint(settings) !== metadata.inputs['data/matching.json']) throw new Error('Probability parameters changed');
      if (!['weighted-log-odds-v1', 'weighted-log-odds-v2', 'weighted-log-odds-v3', 'weighted-log-odds-v4'].includes(settings?.model) || settings.calibrated !== false
        || !(settings.priorProbability > 0 && settings.priorProbability < settings.mergeProbability && settings.mergeProbability < 1)
        || !(settings.guessWeight > 0 && settings.guessWeight < 1)
        || Object.keys(settings.sourceWeights || {}).length !== 4
        || Object.entries({ documents: 1, images: 1, books: .5, notes: .5 }).some(([key, value]) => settings.sourceWeights?.[key] !== value)) throw new Error('Invalid probability parameters');
    }
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
    if ((metadata.schema === undefined || metadata.schema >= 2)) {
      if (!metadata.evidence || JSON.stringify(Object.keys(metadata.evidence).sort()) !== JSON.stringify([...metadata.views].sort())) throw new Error('Missing reconstructed evidence views');
      const checked = new Map();
      const sourceFact = async (source, view) => {
        if (!sourcePath.test(source.path) || !Object.hasOwn(metadata.inputs, source.path)
          || !/\/(facts|guesses)\/[0-9]+$/.test(source.pointer)
          || view === 'facts' && source.pointer.includes('/guesses/')) throw new Error('Invalid reconstructed source');
        const key = JSON.stringify(source);
        if (!checked.has(key)) {
          const assertion = resolveEvidencePointer(documents.get(source.path), source.pointer);
          if (await evidenceFingerprint(assertion) !== source.fingerprint) throw new Error('Reconstructed source changed');
          checked.set(key, assertion);
        }
        return checked.get(key);
      };
      for (const [view, stored] of Object.entries(metadata.evidence)) {
        if ((metadata.schema === undefined || metadata.engine === '5')) {
          const background = metadata.matchingBackground?.[view];
          if (!background || !background.counts || typeof background.counts !== 'object' || Array.isArray(background.counts)
            || !Number.isFinite(background.total) || background.total < 0
            || Object.values(background.counts).some((count) => !Number.isFinite(count) || count <= 0)
            || Math.abs(Object.values(background.counts).reduce((sum, count) => sum + count, 0) - background.total) > 1e-6) throw new Error('Invalid name-frequency background');
        }
        const graph = expandEvidenceGraph(stored);
        const membership = new Map();
        for (const node of graph.nodes) {
          if ((metadata.schema === undefined || metadata.schema >= 4) && (!Number.isFinite(node.identityProbability) || node.identityProbability < 0 || node.identityProbability > 1)) throw new Error('Invalid source identity probability');
          let named = !!node.registry && people.some((person) => person.id === node.registry && person.name === node.name);
          for (const mention of node.mentions) {
            const fact = await sourceFact(mention.source, view);
            if (!fact || !['person', 'of'].includes(mention.field) || typeof fact[mention.field] !== 'string') throw new Error('Invalid reconstructed participant');
            const reference = fact[mention.field];
            if (people.some((person) => person.id && person.id === reference) && node.key !== reference) throw new Error('Reconstructed occurrence overrides a fixed anchor');
            named ||= reference === node.name;
            const key = JSON.stringify([mention.source.path, mention.source.pointer, mention.field, mention.reference || '']);
            if (membership.has(key)) throw new Error('Occurrence assigned to two people');
            membership.set(key, node.key);
          }
          if (!named) throw new Error('Reconstructed name lacks a source or confirmed registry name');
          for (const source of node.identitySources || []) await sourceFact(source, view);
        }
        for (const edge of graph.relationships) {
          for (const derivation of edge.derivations) {
            if ((metadata.schema === undefined || metadata.schema >= 4) && (!Number.isFinite(derivation.assertionWeight) || derivation.assertionWeight <= 0 || derivation.assertionWeight > 1
              || derivation.endpointProbability !== null && (!Number.isFinite(derivation.endpointProbability) || derivation.endpointProbability < 0 || derivation.endpointProbability > 1))) throw new Error('Invalid relationship evidence weights');
            let supported = false;
            for (const source of derivation.sources) {
              const fact = await sourceFact(source, view);
              if (fact.type !== edge.type || (fact.term || '') !== (edge.term || '')) continue;
              const endpoints = ['person', 'of'].map((field) => membership.get(JSON.stringify([source.path, source.pointer, field, ''])));
              const expected = [edge.person, edge.of];
              if (edge.type !== 'parent') { endpoints.sort(); expected.sort(); }
              supported ||= JSON.stringify(endpoints) === JSON.stringify(expected);
            }
            if (!supported) throw new Error('Reconstructed relationship lacks its source participants');
          }
        }
        if ((metadata.schema === undefined || metadata.schema >= 4)) {
          if (!Array.isArray(graph.comparisons)) throw new Error('Missing probability comparisons');
          const keys = new Set(graph.nodes.map((node) => node.key));
          const prior = settings.priorProbability;
          for (const comparison of graph.comparisons) {
            if (!keys.has(comparison.person) || !keys.has(comparison.candidate)
              || !['merged', 'below-threshold', 'ambiguous', 'incompatible', 'superseded'].includes(comparison.status)
              || !Number.isFinite(comparison.probability) || comparison.probability < 0 || comparison.probability > 1
              || !Number.isFinite(comparison.logOdds) || !Array.isArray(comparison.features)
              || comparison.features.some((feature) => typeof feature.name !== 'string' || !Number.isFinite(feature.contribution))
              || typeof comparison.usesGuesses !== 'boolean' || view === 'facts' && comparison.usesGuesses
              || !comparison.sources?.length) throw new Error('Invalid probability comparison');
            const expected = 1 / (1 + Math.exp(-comparison.logOdds));
            const total = Math.log(prior / (1 - prior)) + comparison.features.reduce((sum, feature) => sum + feature.contribution, 0);
            if (Math.abs(expected - comparison.probability) > 1e-7 || Math.abs(total - comparison.logOdds) > 1e-6) throw new Error('Invalid probability calculation');
            for (const source of comparison.sources) {
              await sourceFact(source, view);
              if (source.pointer.includes('/guesses/') && !comparison.usesGuesses) throw new Error('Unmarked probability guess dependency');
            }
          }
        }
      }
    }
    for (const view of metadata.views) {
      const graph = buildRelationshipGraph(people, { tree, view, verification: { valid: true } });
      if (!graph.valid) throw new Error(graph.reason);
    }
    return { valid: true, reason: '' };
  } catch (error) {
    return { valid: false, reason: `${error.message}. Rebuild family relationships to verify the evidence.` };
  }
}

export function buildRelationshipGraph(people, { tree, view, verification } = {}) {
  const ids = new Set(people.filter((person) => person.id).map((person) => person.id));
  const records = people.map((person, index) => {
    let key = person.id || `@registry/${index}`;
    if (!person.id) while (ids.has(key)) key += '~';
    return { ...person, _treeKey: key };
  });
  const generated = tree !== undefined || people.some((person) => Object.hasOwn(person, 'relationships') || person.familyGraph);
  const metadata = treeMetadata(tree === undefined ? people[0]?.familyGraph : tree);
  const views = generated ? Array.isArray(metadata?.views) ? metadata.views : [] : ['facts'];
  const requestedView = view || (metadata && (metadata.schema === undefined || metadata.schema >= 4) ? 'with-guesses' : 'facts');
  const selectedView = views.includes(requestedView) ? requestedView : 'facts';
  let evidence;
  try { evidence = expandEvidenceGraph(metadata?.evidence?.[selectedView]); }
  catch (error) { return { records, edges: [], reverse: new Map(), generated, views, view: selectedView, valid: false, reason: error.message, metadata }; }
  const result = { records, edges: [], comparisons: evidence?.comparisons || [], reverse: new Map(), generated, views, view: selectedView,
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
      sourceIdentity: derivations.some((d) => d.identity === 'source'),
      inferred: derivations.length > 0 && derivations.every((d) => d.identity === 'inferred'),
      usesGuesses: derivations.length > 0 && derivations.every((d) => d.usesGuesses) });
  };
  try {
    if (evidence) {
      const byKey = new Map(records.map((person) => [person._treeKey, person]));
      const seenNodes = new Set();
      for (const node of evidence.nodes) {
        if (!node.key || seenNodes.has(node.key) || !node.name || !['source', 'contextual', 'anchored'].includes(node.status) || !node.mentions?.length) throw new Error('Invalid reconstructed person');
        seenNodes.add(node.key);
        if (node.registry) {
          if (node.registry !== node.key || !byKey.has(node.key)) throw new Error('Invalid reconstructed registry anchor');
          Object.assign(byKey.get(node.key), { reconstruction: node, titles: node.titles });
        } else {
          if (!node.key.startsWith('@evidence/') || byKey.has(node.key)) throw new Error('Invalid source person handle');
          const record = { name: node.name, titles: node.titles, _treeKey: node.key, _evidence: true, reconstruction: node };
          records.push(record); byKey.set(node.key, record);
        }
      }
      for (const edge of evidence.relationships) {
        if (!['parent', 'spouse', 'sibling', 'kin'].includes(edge.type) || edge.type === 'kin' && !edge.term?.trim() || !edge.derivations?.length) throw new Error('Invalid reconstructed relationship');
        const derivations = edge.derivations.map((d) => ({ ...d, view: selectedView }));
        for (const d of derivations) {
          if (!['anchored', 'reviewed', 'inferred', 'source'].includes(d.identity) || typeof d.usesGuesses !== 'boolean'
            || !d.sources?.length || selectedView === 'facts' && d.usesGuesses
            || d.sources.some((source) => source.pointer.includes('/guesses/') && !d.usesGuesses)) throw new Error('Invalid reconstructed derivation');
        }
        add(byKey.get(edge.person), byKey.get(edge.of), edge.type, derivations, edge.term || '');
      }
    } else for (const person of records) {
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
    if (evidence) {
      result.components = familyComponents(records, result.edges);
      result.defaultFocus = (result.components.find((component) => component.anchored) || result.components[0])?.key;
    }
  } catch (error) {
    result.valid = false; result.reason = error.message; result.edges = []; result.reverse.clear();
  }
  return result;
}

function familyComponents(records, edges) {
  const adjacency = new Map(records.map((person) => [person._treeKey, new Set()]));
  edges.forEach((edge) => { adjacency.get(edge.person).add(edge.of); adjacency.get(edge.of).add(edge.person); });
  const byKey = new Map(records.map((person) => [person._treeKey, person]));
  const unseen = new Set(adjacency.keys()), components = [];
  while (unseen.size) {
    const stack = [unseen.values().next().value], members = new Set();
    while (stack.length) {
      const key = stack.pop();
      if (members.has(key)) continue;
      members.add(key); unseen.delete(key);
      stack.push(...[...adjacency.get(key)].filter((other) => !members.has(other)));
    }
    const ordered = [...members].sort((a, b) => Number(!!byKey.get(b).id) - Number(!!byKey.get(a).id)
      || adjacency.get(b).size - adjacency.get(a).size || a.localeCompare(b));
    const anchors = ordered.filter((key) => byKey.get(key).id);
    const relatives = ordered.map((key) => byKey.get(key).name).filter((name, index, values) => values.indexOf(name) === index);
    const years = [...members].flatMap((key) => (byKey.get(key).reconstruction?.dates || []).flatMap((date) => date.match(/\d{4}/g) || [])).sort();
    components.push({ key: [...(anchors.length ? anchors : members)].sort()[0], members: [...members],
      label: `${relatives.slice(0, 2).join(' / ')} · ${members.size} people${years.length ? ` · ${years[0]}${years.at(-1) !== years[0] ? `–${years.at(-1)}` : ''}` : ''}`, anchored: anchors.length > 0 });
  }
  return components.sort((a, b) => b.members.length - a.members.length || a.key.localeCompare(b.key));
}

export function focusFamilyGraph(graph, focus) {
  if (!focus || focus === 'all' || !graph.components?.length) return graph;
  const component = graph.components.find((item) => item.key === focus) || graph.components.find((item) => item.key === graph.defaultFocus);
  if (!component) return graph;
  const members = new Set(component.members);
  const edges = graph.edges.filter((edge) => members.has(edge.person) && members.has(edge.of));
  return { ...graph, records: graph.records.filter((person) => members.has(person._treeKey)), edges,
    reverse: new Map([...graph.reverse].filter(([key]) => members.has(key))) };
}

export function remapSourcePerson(state, previous) {
  if (!state.familyGraph?.valid || !state.person) return false;
  if (state.familyGraph.records.some((person) => person._treeKey === state.person)) {
    state.sourcePersonChoices = null;
    return false;
  }
  const old = previous?.records.find((person) => person._evidence && person._treeKey === state.person);
  if (!old) return false;
  const occurrence = ({ source, field, reference }) => JSON.stringify([source.path, source.pointer, source.fingerprint, field, reference || '']);
  const references = new Set(old.reconstruction.mentions.map(occurrence));
  const matches = state.familyGraph.records.filter((person) => person.reconstruction?.mentions.some((mention) => references.has(occurrence(mention))));
  if (matches.length === 1) {
    state.person = matches[0].id || matches[0]._treeKey;
    state.sourcePersonChoices = null;
    return true;
  }
  state.sourcePersonChoices = { reference: state.person, name: old.name, matches };
  return false;
}
