function svgEscape(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
}

export function renderPeopleTree(people = []) {
  const records = Array.isArray(people) ? people.filter((person) => person && person.id && person.name) : [];
  if (!records.length) return '<div class="people-tree"><p class="status">No people found.</p></div>';

  const nodeWidth = 220;
  const nodeHeight = 72;
  const horizontalGap = 36;
  const verticalGap = 88;
  const padding = 28;
  const byId = new Map(records.map((person) => [person.id, person]));
  const groupParent = new Map(records.map((person) => [person.id, person.id]));
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
    if (byId.has(person.wife)) joinGroups(person.id, person.wife);
  });

  const groupParents = new Map();
  records.forEach((person) => {
    const parentGroup = groupFor(person.id);
    (Array.isArray(person.children) ? person.children : []).forEach((childId) => {
      if (!byId.has(childId)) return;
      const childGroup = groupFor(childId);
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
  records.forEach((person) => depthForGroup(groupFor(person.id)));
  const depths = new Map(records.map((person) => [person.id, groupDepths.get(groupFor(person.id)) || 0]));
  const layers = new Map();
  records.forEach((person) => {
    const depth = depths.get(person.id) || 0;
    if (!layers.has(depth)) layers.set(depth, []);
    layers.get(depth).push(person);
  });
  [...layers.values()].forEach((layer) => layer.sort((left, right) => left.name.localeCompare(right.name)));

  const maxDepth = Math.max(...layers.keys());
  const maxLayerSize = Math.max(...[...layers.values()].map((layer) => layer.length));
  const width = Math.max(2 * padding + nodeWidth, 2 * padding + maxLayerSize * nodeWidth + (maxLayerSize - 1) * horizontalGap);
  const height = 2 * padding + (maxDepth + 1) * nodeHeight + maxDepth * verticalGap;
  const positions = new Map();
  layers.forEach((layer, depth) => {
    const layerWidth = layer.length * nodeWidth + (layer.length - 1) * horizontalGap;
    const startX = (width - layerWidth) / 2;
    layer.forEach((person, index) => positions.set(person.id, {
      x: startX + index * (nodeWidth + horizontalGap),
      y: padding + depth * (nodeHeight + verticalGap),
    }));
  });

  const personLines = (person) => [
    person.name,
    Array.isArray(person.titles) && person.titles.length ? person.titles.join(', ') : '',
    person.born || person.died ? `${person.born || '?'}–${person.died || '?'}` : '',
  ].filter(Boolean);
  const edges = [];
  records.forEach((person) => {
    const from = positions.get(person.id);
    if (!from) return;
    const wife = positions.get(person.wife);
    if (wife && person.id.localeCompare(person.wife) < 0) {
      const left = from.x < wife.x ? from : wife;
      const right = from.x < wife.x ? wife : from;
      edges.push(`<line class="people-tree-spouse" x1="${left.x + nodeWidth}" y1="${left.y + nodeHeight / 2}" x2="${right.x}" y2="${right.y + nodeHeight / 2}"/><text class="people-tree-edge-label" x="${(left.x + nodeWidth + right.x) / 2}" y="${left.y + nodeHeight / 2 - 8}">wife</text>`);
    }
    (Array.isArray(person.children) ? person.children : []).forEach((childId) => {
      const child = positions.get(childId);
      if (child) edges.push(`<line class="people-tree-parent" x1="${from.x + nodeWidth / 2}" y1="${from.y + nodeHeight}" x2="${child.x + nodeWidth / 2}" y2="${child.y}"/>`);
    });
  });
  const nodes = records.map((person) => {
    const position = positions.get(person.id);
    const text = personLines(person).map((line, index) => `<tspan class="${index ? 'people-tree-detail' : 'people-tree-name'}" x="${position.x + nodeWidth / 2}" dy="${index ? 18 : 0}">${svgEscape(line)}</tspan>`).join('');
    return `<g class="people-tree-node"><rect x="${position.x}" y="${position.y}" width="${nodeWidth}" height="${nodeHeight}" rx="8"/><text x="${position.x + nodeWidth / 2}" y="${position.y + 25}" text-anchor="middle">${text}</text></g>`;
  }).join('');
  return `<div class="people-tree"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Family tree">${edges.join('')}${nodes}</svg></div>`;
}
