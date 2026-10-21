function svgEscape(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
}

export function renderPeopleTree(people = []) {
  const records = Array.isArray(people)
    ? people.filter((person) => person && person.name).map((person) => ({ ...person, _treeKey: person.id || person.name }))
    : [];
  if (!records.length) return '<div class="people-tree"><p class="status">No people found.</p></div>';

  const nodeWidth = 220;
  const nodeHeight = 72;
  const horizontalGap = 36;
  const verticalGap = 88;
  const padding = 28;
  const byId = new Map();
  records.forEach((person) => {
    byId.set(person._treeKey, person._treeKey);
    if (person.name) byId.set(person.name, person._treeKey);
    if (person.id) byId.set(person.id, person._treeKey);
  });
  const groupParent = new Map(records.map((person) => [person._treeKey, person._treeKey]));
  const groupFor = (id) => {
    let root = groupParent.get(id);
    while (root && groupParent.get(root) !== root) root = groupParent.get(root);
    if (root) groupParent.set(id, root);
    return root;
  };
  const joinGroups = (left, right) => {
    const leftRoot = groupFor(left);
    const rightRoot = groupFor(right);
    if (leftRoot && rightRoot && leftRoot !== rightRoot) groupParent.set(rightRoot, leftRoot);
  };
  records.forEach((person) => {
    const wifeKey = byId.get(person.wife);
    if (wifeKey) joinGroups(person._treeKey, wifeKey);
  });

  const groupParents = new Map();
  records.forEach((person) => {
    const parentGroup = groupFor(person._treeKey);
    (Array.isArray(person.children) ? person.children : []).forEach((childRef) => {
      const childKey = byId.get(childRef);
      if (!childKey) return;
      const childGroup = groupFor(childKey);
      if (parentGroup !== childGroup) {
        if (!groupParents.has(childGroup)) groupParents.set(childGroup, new Set());
        groupParents.get(childGroup).add(parentGroup);
      }
    });
  });

  const groupDepths = new Map();
  const depthForGroup = (group, visiting = new Set()) => {
    if (groupDepths.has(group)) return groupDepths.get(group);
    if (visiting.has(group)) return 0;
    visiting.add(group);
    const parents = groupParents.get(group) || [];
    const depth = parents.size
      ? Math.max(...[...parents].map((parent) => depthForGroup(parent, new Set(visiting)))) + 1
      : 0;
    groupDepths.set(group, depth);
    return depth;
  };
  records.forEach((person) => depthForGroup(groupFor(person._treeKey)));
  const depths = new Map(records.map((person) => [person._treeKey, groupDepths.get(groupFor(person._treeKey)) || 0]));
  const layers = new Map();
  records.forEach((person) => {
    const depth = depths.get(person._treeKey) || 0;
    if (!layers.has(depth)) layers.set(depth, []);
    layers.get(depth).push(person);
  });
  const groupMembers = new Map();
  records.forEach((person) => {
    const group = groupFor(person._treeKey);
    if (!groupMembers.has(group)) groupMembers.set(group, []);
    groupMembers.get(group).push(person);
  });
  groupMembers.forEach((members) => members.sort((left, right) => left.name.localeCompare(right.name)));

  const maxDepth = Math.max(...layers.keys());
  const maxLayerSize = Math.max(...[...layers.values()].map((layer) => layer.length));
  const width = Math.max(2 * padding + nodeWidth, 2 * padding + maxLayerSize * nodeWidth + (maxLayerSize - 1) * horizontalGap);
  const height = 2 * padding + (maxDepth + 1) * nodeHeight + maxDepth * verticalGap;
  const positions = new Map();
  layers.forEach((layer, depth) => {
    const groups = [...new Set(layer.map((person) => groupFor(person._treeKey)))].map((group) => {
      const members = groupMembers.get(group) || [];
      const parents = [...(groupParents.get(group) || [])];
      const parentCenters = parents.flatMap((parent) => (groupMembers.get(parent) || [])
        .map((person) => positions.get(person._treeKey)?.x + nodeWidth / 2)
        .filter(Number.isFinite));
      const target = parentCenters.length
        ? parentCenters.reduce((sum, center) => sum + center, 0) / parentCenters.length
        : null;
      return { group, members, target, name: members[0]?.name || '' };
    }).sort((left, right) => {
      if (left.target !== null && right.target !== null && left.target !== right.target) return left.target - right.target;
      if (left.target !== null && right.target === null) return -1;
      if (left.target === null && right.target !== null) return 1;
      return left.name.localeCompare(right.name);
    });
    const totalWidth = layer.length * nodeWidth + (layer.length - 1) * horizontalGap;
    let cursor = groups.some(({ target }) => target !== null)
      ? padding
      : Math.max(padding, (width - totalWidth) / 2);
    groups.forEach(({ members, target }) => {
      const groupWidth = members.length * nodeWidth + (members.length - 1) * horizontalGap;
      const desiredX = target === null ? cursor : target - groupWidth / 2;
      const x = Math.max(cursor, desiredX);
      members.forEach((person, index) => positions.set(person._treeKey, {
        x: x + index * (nodeWidth + horizontalGap),
        y: padding + depth * (nodeHeight + verticalGap),
      }));
      cursor = x + groupWidth + horizontalGap;
    });
  });

  const personLines = (person) => [
    person.name,
    Array.isArray(person.titles) && person.titles.length ? person.titles.join(', ') : '',
    person.born || person.died ? `${person.born || '?'}–${person.died || '?'}` : '',
  ].filter(Boolean);
  const edges = [];
  const spousePairs = new Set();
  records.forEach((person) => {
    const from = positions.get(person._treeKey);
    if (!from) return;
    const wifeKey = byId.get(person.wife);
    const wife = positions.get(wifeKey);
    const spousePair = [person._treeKey, wifeKey].sort().join('\u0000');
    if (wife && !spousePairs.has(spousePair)) {
      spousePairs.add(spousePair);
      const left = from.x < wife.x ? from : wife;
      const right = from.x < wife.x ? wife : from;
      edges.push(`<line class="people-tree-spouse" x1="${left.x + nodeWidth}" y1="${left.y + nodeHeight / 2}" x2="${right.x}" y2="${right.y + nodeHeight / 2}"/><text class="people-tree-edge-label" x="${(left.x + nodeWidth + right.x) / 2}" y="${left.y + nodeHeight / 2 - 8}">wife</text>`);
    }
    (Array.isArray(person.children) ? person.children : []).forEach((childRef) => {
      const child = positions.get(byId.get(childRef));
      if (child) {
        const startX = from.x + nodeWidth / 2;
        const startY = from.y + nodeHeight;
        const endX = child.x + nodeWidth / 2;
        const endY = child.y;
        const cornerY = (startY + endY) / 2;
        edges.push(`<path class="people-tree-parent" fill="none" d="M${startX} ${startY} V${cornerY} H${endX} V${endY}"/>`);
      }
    });
  });
  const nodes = records.map((person) => {
    const position = positions.get(person._treeKey);
    const text = personLines(person).map((line, index) => `<tspan class="${index ? 'people-tree-detail' : 'people-tree-name'}" x="${position.x + nodeWidth / 2}" dy="${index ? 18 : 0}">${svgEscape(line)}</tspan>`).join('');
    const href = `?person=${encodeURIComponent(person.id || person.name)}`;
    return `<a class="people-tree-person-link" href="${svgEscape(href)}" aria-label="View ${svgEscape(person.name)}"><g class="people-tree-node"><rect x="${position.x}" y="${position.y}" width="${nodeWidth}" height="${nodeHeight}" rx="8"/><text x="${position.x + nodeWidth / 2}" y="${position.y + 25}" text-anchor="middle">${text}</text></g></a>`;
  }).join('');
  return `<div class="people-tree"><svg viewBox="0 0 ${width} ${height}" role="group" aria-label="Family tree">${edges.join('')}${nodes}</svg></div>`;
}
