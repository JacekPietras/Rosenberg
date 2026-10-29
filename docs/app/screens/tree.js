import { buildRelationshipGraph } from '../data/relationships.js';
import { relationshipControls, relationshipPanel } from '../rendering/relationships.js';

function svgEscape(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
}

function regexEscape(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function renderPeopleTree(people = [], documents = [], { graph } = {}) {
  graph ||= buildRelationshipGraph(Array.isArray(people) ? people : []);
  const records = graph.records.filter((person) => person?.name).map((person) => ({ ...person,
    children: graph.edges.filter((edge) => edge.type === 'parent' && edge.person === person._treeKey).map((edge) => edge.of),
    wife: graph.generated ? null : person.wife }));
  if (!records.length) return '<div class="people-tree"><p class="status">No people found.</p></div>';

  const documentRecords = documents instanceof Map ? [...documents.entries()] : Array.isArray(documents) ? documents.map((doc) => ['', doc]) : [];
  const mentionedYears = new Map(records.map((person) => {
    const years = new Set();
    documentRecords.forEach(([path, document]) => {
      const explicit = /^data\/(books|notes)\//.test(path) || !!document?.book;
      const visit = (value, inherited = '') => {
        if (Array.isArray(value)) { value.forEach((child) => visit(child, inherited)); return; }
        if (!value || typeof value !== 'object') return;
        const date = explicit ? '' : Object.hasOwn(value, 'date') ? value.date : inherited;
        Object.entries(value).forEach(([key, child]) => {
          if (key === 'facts' || key === 'guesses') {
            if (key === 'guesses' && graph.view !== 'with-guesses') return;
            (Array.isArray(child) ? child : []).forEach((fact) => {
              const historical = Object.hasOwn(fact || {}, 'date') ? fact.date : date;
              const direct = fact?.type && person.id && [fact.person, fact.of].includes(person.id);
              if (direct) (String(historical || '').match(/\d{4}/g) || []).forEach((year) => years.add(year));
            });
          } else visit(child, date);
        });
      };
      visit(document);
    });
    const imageEntries = documents instanceof Map ? documents.get('data/images/images.json')?.entries || [] : [];
    imageEntries.forEach((entry) => {
      const title = String(entry.title || '');
      const titleMentionsPerson = person.id
        ? new RegExp(`\\[${regexEscape(person.id)}\\]`).test(title)
        : new RegExp(`(?<![\\p{L}\\p{N}])${regexEscape(person.name)}(?![\\p{L}\\p{N}])`, 'iu').test(title);
      if (!titleMentionsPerson) return;
      (String(entry.date || '').match(/\d{4}/g) || []).forEach((year) => years.add(year));
    });
    return [person._treeKey, [...years].sort()];
  }));
  const personLines = (person) => [
    person.name,
    person._treeRepeated ? 'shown in multiple branches' : '',
    ...(Array.isArray(person.titles) ? person.titles : []),
    person.born || person.died ? `${person.born || '?'}–${person.died || '?'}` : '',
    mentionedYears.get(person._treeKey)?.length
      ? `mentioned: [${mentionedYears.get(person._treeKey)[0]}${mentionedYears.get(person._treeKey).length > 1 ? `-${mentionedYears.get(person._treeKey).at(-1)}` : ''}]`
      : '',
  ].filter(Boolean);
  const nodeHeightFor = (person) => Math.max(44, 25 + (personLines(person).length - 1) * 18 + 10);
  const nodeWidth = 220;
  const horizontalGap = 36;
  const verticalGap = 88;
  const padding = 28;
  const byId = new Map();
  records.forEach((person) => {
    byId.set(person._treeKey, person._treeKey);
    if (records.filter((item) => item.name === person.name).length === 1) byId.set(person.name, person._treeKey);
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

  const groupMembers = new Map();
  records.forEach((person) => {
    const group = groupFor(person._treeKey);
    if (!groupMembers.has(group)) groupMembers.set(group, []);
    groupMembers.get(group).push(person);
  });
  const comparePeople = (left, right) => left.name.localeCompare(right.name)
    || left._treeKey.localeCompare(right._treeKey);
  groupMembers.forEach((members) => members.sort(comparePeople));
  const childrenFor = (person) => [...new Set((Array.isArray(person.children) ? person.children : [])
    .map((reference) => byId.get(reference)).filter(Boolean))];
  const parentGroups = new Set();
  records.forEach((person) => childrenFor(person).forEach((key) => parentGroups.add(groupFor(key))));

  // Reserve space for complete descendant branches before placing any cards.
  // A shared descendant gets another occurrence, rather than an edge crossing
  // another family's branch. References still open the same person record.
  const covered = new Set();
  const makeBranch = (group, ancestors = new Set()) => {
    covered.add(group);
    const branch = { group, members: groupMembers.get(group).map((person) => ({ ...person })), families: [] };
    if (ancestors.has(group)) return branch;
    const nextAncestors = new Set([...ancestors, group]);
    const families = new Map();
    branch.members.forEach((person) => {
      const children = childrenFor(person).sort((left, right) => comparePeople(
        recordsByKey.get(left), recordsByKey.get(right)));
      // Parents listing the same children share one sibling bus. Different
      // child lists keep their own space, preserving the recorded parentage.
      const signature = JSON.stringify(children);
      if (!families.has(signature)) families.set(signature, { parents: [], children });
      families.get(signature).parents.push(person);
    });
    branch.families = [...families.values()].map((family) => ({
      parents: family.parents,
      children: family.children.map((key) => ({ key, branch: makeBranch(groupFor(key), nextAncestors) })),
    }));
    return branch;
  };
  const recordsByKey = new Map(records.map((person) => [person._treeKey, person]));
  const groups = [...groupMembers.keys()].sort((left, right) => comparePeople(
    groupMembers.get(left)[0], groupMembers.get(right)[0]));
  let roots = groups.filter((group) => !parentGroups.has(group)).map((group) => makeBranch(group));
  // Retain components with cyclic/inconsistent ancestry, stopping expansion
  // at an already visited group on the current path.
  groups.forEach((group) => {
    if (!covered.has(group)) roots.push(makeBranch(group));
  });
  if (graph.generated) {
    const parentEndpoints = new Set(graph.edges.filter((edge) => edge.type === 'parent').flatMap((edge) => [edge.person, edge.of]));
    const marriages = graph.edges.filter((edge) => edge.type === 'spouse');
    const married = new Set(marriages.flatMap((edge) => [edge.person, edge.of]));
    roots = roots.filter((branch) => branch.members.length !== 1 || !married.has(branch.members[0]._treeKey) || parentEndpoints.has(branch.members[0]._treeKey));
    // A marriage gets its own pair of occurrences, without children attached.
    // Several marriages therefore cannot create a shared parental unit.
    marriages.forEach((edge) => roots.push({
      group: `@marriage/${edge.person}/${edge.of}`,
      members: [{ ...recordsByKey.get(edge.person), wife: edge.of }, { ...recordsByKey.get(edge.of), wife: null }],
      families: [],
    }));
  }
  const occurrences = [];
  const collectOccurrences = (branch) => {
    occurrences.push(branch);
    branch.families.forEach((family) => family.children.forEach((child) => collectOccurrences(child.branch)));
  };
  roots.forEach(collectOccurrences);
  const occurrenceCounts = new Map();
  occurrences.forEach(({ members }) => members.forEach((person) => occurrenceCounts.set(
    person._treeKey, (occurrenceCounts.get(person._treeKey) || 0) + 1)));
  occurrences.forEach(({ members }) => members.forEach((person) => {
    person._treeRepeated = occurrenceCounts.get(person._treeKey) > 1;
  }));

  const rowWidth = (count) => count * nodeWidth + Math.max(0, count - 1) * horizontalGap;
  const measure = (branch) => {
    branch.levels = 1;
    if (!branch.families.length) {
      branch.width = rowWidth(branch.members.length);
      return branch.width;
    }
    branch.families.forEach((family) => {
      family.childrenWidth = family.children.reduce((sum, child) => sum + measure(child.branch), 0)
        + Math.max(0, family.children.length - 1) * horizontalGap;
      family.children.forEach((child) => { branch.levels = Math.max(branch.levels, child.branch.levels + 1); });
      family.width = Math.max(rowWidth(family.parents.length), family.childrenWidth);
    });
    branch.width = branch.families.reduce((sum, family) => sum + family.width, 0)
      + Math.max(0, branch.families.length - 1) * horizontalGap;
    return branch.width;
  };
  roots.forEach(measure);
  const layerHeights = [];
  const collectHeights = (branch, depth) => {
    layerHeights[depth] = Math.max(layerHeights[depth] || 0, ...branch.members.map(nodeHeightFor));
    branch.families.forEach((family) => family.children.forEach((child) => collectHeights(child.branch, depth + 1)));
  };
  roots.forEach((branch) => collectHeights(branch, 0));
  const layerOffsets = [];
  let height = padding;
  layerHeights.forEach((layerHeight, depth) => {
    layerOffsets[depth] = height;
    height += layerHeight + verticalGap;
  });
  // Pack disconnected families into rows so small independent trees do not
  // make the complete diagram unnecessarily wide when fitted to the viewport.
  roots.forEach((branch) => {
    const lastLayer = branch.levels - 1;
    branch.height = layerOffsets[lastLayer] + layerHeights[lastLayer] - padding;
  });
  const componentGap = horizontalGap * 2;
  const targetWidth = Math.max(...roots.map((branch) => branch.width), Math.sqrt(
    roots.reduce((area, branch) => area + (branch.width + componentGap) * (branch.height + componentGap), 0) * 1.6));
  let rootX = padding;
  let rootY = 0;
  let rowHeight = 0;
  let width = 0;
  roots.forEach((branch) => {
    if (rootX > padding && rootX + branch.width > padding + targetWidth) {
      rootX = padding;
      rootY += rowHeight + componentGap;
      rowHeight = 0;
    }
    branch.x = rootX;
    branch.y = rootY;
    rootX += branch.width + componentGap;
    rowHeight = Math.max(rowHeight, branch.height);
    width = Math.max(width, branch.x + branch.width + padding);
  });
  height = rootY + rowHeight + 2 * padding;
  const cards = [];
  const edges = [];
  const place = (branch, x, depth, offsetY) => {
    branch.positions = new Map();
    const y = offsetY + layerOffsets[depth];
    const placeParents = (parents, start) => parents.forEach((person, index) => {
      const position = { x: start + index * (nodeWidth + horizontalGap), y };
      branch.positions.set(person._treeKey, position);
      cards.push({ person, ...position });
    });
    if (!branch.families.length) placeParents(branch.members, x);
    let familyX = x;
    branch.families.forEach((family) => {
      let childX = familyX + (family.width - family.childrenWidth) / 2;
      family.children.forEach((child) => {
        place(child.branch, childX, depth + 1, offsetY);
        childX += child.branch.width + horizontalGap;
      });
      const childCenters = family.children.map((child) => child.branch.positions.get(child.key).x + nodeWidth / 2);
      const parentWidth = rowWidth(family.parents.length);
      const target = childCenters.length
        ? (Math.min(...childCenters) + Math.max(...childCenters)) / 2
        : familyX + family.width / 2;
      const parentX = Math.max(familyX, Math.min(familyX + family.width - parentWidth, target - parentWidth / 2));
      placeParents(family.parents, parentX);
      if (family.children.length) {
        const busY = y + layerHeights[depth] + verticalGap / 2;
        const parentCenters = family.parents.map((person) => branch.positions.get(person._treeKey).x + nodeWidth / 2);
        const centers = [...parentCenters, ...childCenters];
        // Draw each segment once: one sibling bus, one drop per child, and
        // one stem per recorded parent. Nothing runs through another branch.
        const segments = [`M${Math.min(...centers)} ${busY} H${Math.max(...centers)}`];
        family.parents.forEach((person, index) => {
          segments.push(`M${parentCenters[index]} ${y + nodeHeightFor(person)} V${busY}`);
        });
        childCenters.forEach((center) => segments.push(`M${center} ${busY} V${offsetY + layerOffsets[depth + 1]}`));
        const support = graph.edges.filter((edge) => edge.type === 'parent' && family.parents.some((parent) => parent._treeKey === edge.person) && family.children.some((child) => child.key === edge.of));
        edges.push(`<path class="people-tree-parent" data-identity="${support.some((edge) => edge.inferred) ? 'inferred' : 'anchored'}" fill="none" d="${segments.join(' ')}"/>`);
      }
      familyX += family.width + horizontalGap;
    });
    const spousePairs = new Set();
    branch.members.forEach((person) => {
      const wifeKey = byId.get(person.wife);
      if (!wifeKey || wifeKey === person._treeKey) return;
      const pair = [person._treeKey, wifeKey].sort().join('\u0000');
      if (spousePairs.has(pair)) return;
      spousePairs.add(pair);
      const from = branch.positions.get(person._treeKey);
      const to = branch.positions.get(wifeKey);
      const left = from.x < to.x ? from : to;
      const right = from.x < to.x ? to : from;
      const edgeY = y + Math.min(...branch.members.map(nodeHeightFor)) / 2;
      const support = graph.edges.find((edge) => edge.type === 'spouse' && [edge.person, edge.of].includes(person._treeKey) && [edge.person, edge.of].includes(wifeKey));
      edges.push(`<line class="people-tree-spouse" data-identity="${support?.inferred ? 'inferred' : 'anchored'}" x1="${left.x + nodeWidth}" y1="${edgeY}" x2="${right.x}" y2="${edgeY}"/><text class="people-tree-edge-label" x="${(left.x + nodeWidth + right.x) / 2}" y="${edgeY - 8}">${graph.generated ? 'spouse' : 'wife'}</text>`);
    });
  };
  roots.forEach((branch) => place(branch, branch.x, 0, branch.y));
  const nodes = cards.map(({ person, x, y }) => {
    const nodeHeight = nodeHeightFor(person);
    const text = personLines(person).map((line, index) => `<tspan class="${index ? 'people-tree-detail' : 'people-tree-name'}" x="${x + nodeWidth / 2}" dy="${index ? 18 : 0}">${svgEscape(line)}</tspan>`).join('');
    const href = `?person=${encodeURIComponent(person.id || person.name)}`;
    return `<a class="people-tree-person-link" href="${svgEscape(href)}" aria-label="View ${svgEscape(person.name)}"><g class="people-tree-node"><rect x="${x}" y="${y}" width="${nodeWidth}" height="${nodeHeight}" rx="8"/><text x="${x + nodeWidth / 2}" y="${y + 25}" text-anchor="middle">${text}</text></g></a>`;
  }).join('');
  return `${relationshipControls(graph)}<section class="people-tree-wrap" aria-label="Family tree viewer"><div class="people-tree"><svg viewBox="0 0 ${width} ${height}" role="group" aria-label="Family tree">${edges.join('')}${nodes}</svg></div></section>${relationshipPanel(graph)}`;
}

export function setupPeopleTreeZoom(root = document) {
  const wrapper = root.querySelector('.people-tree-wrap');
  const svg = wrapper?.querySelector('.people-tree svg');
  if (!wrapper || !svg) return;
  const [viewWidth, viewHeight] = svg.getAttribute('viewBox').split(/\s+/).slice(2).map(Number);
  const viewport = wrapper.querySelector('.people-tree');
  let scale = 1;
  const minScale = .025;
  const maxScale = 2;
  const applyScale = () => {
    svg.style.width = `${viewWidth * scale}px`;
    svg.style.height = `${viewHeight * scale}px`;
  };
  const fit = () => {
    scale = Math.min(1, (viewport.clientWidth - 32) / viewWidth, (viewport.clientHeight - 32) / viewHeight);
    scale = Math.max(minScale, scale);
    applyScale();
    viewport.scrollTo({ left: 0, top: 0 });
  };
  const zoomAt = (factor, clientX = viewport.getBoundingClientRect().left + viewport.clientWidth / 2, clientY = viewport.getBoundingClientRect().top + viewport.clientHeight / 2) => {
    const bounds = viewport.getBoundingClientRect();
    const x = viewport.scrollLeft + clientX - bounds.left;
    const y = viewport.scrollTop + clientY - bounds.top;
    const previousScale = scale;
    const nextScale = Math.min(maxScale, Math.max(minScale, scale * factor));
    if (nextScale === scale) return;
    scale = nextScale;
    applyScale();
    viewport.scrollLeft = x * (scale / previousScale) - (clientX - bounds.left);
    viewport.scrollTop = y * (scale / previousScale) - (clientY - bounds.top);
  };
  viewport.addEventListener('wheel', (event) => {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    zoomAt(Math.exp(-event.deltaY * .01), event.clientX, event.clientY);
  }, { passive: false });
  let gestureStartScale = scale;
  viewport.addEventListener('gesturestart', (event) => {
    event.preventDefault();
    gestureStartScale = scale;
  }, { passive: false });
  viewport.addEventListener('gesturechange', (event) => {
    event.preventDefault();
    zoomAt(gestureStartScale * event.scale / scale, event.clientX, event.clientY);
  }, { passive: false });
  let touchStartDistance = 0;
  let touchStartScale = scale;
  viewport.addEventListener('touchstart', (event) => {
    if (event.touches.length !== 2) return;
    touchStartDistance = Math.hypot(event.touches[0].clientX - event.touches[1].clientX, event.touches[0].clientY - event.touches[1].clientY);
    touchStartScale = scale;
  }, { passive: true });
  viewport.addEventListener('touchmove', (event) => {
    if (event.touches.length !== 2 || !touchStartDistance) return;
    event.preventDefault();
    const distance = Math.hypot(event.touches[0].clientX - event.touches[1].clientX, event.touches[0].clientY - event.touches[1].clientY);
    const nextScale = Math.min(maxScale, Math.max(minScale, touchStartScale * distance / touchStartDistance));
    const centerX = (event.touches[0].clientX + event.touches[1].clientX) / 2;
    const centerY = (event.touches[0].clientY + event.touches[1].clientY) / 2;
    zoomAt(nextScale / scale, centerX, centerY);
  }, { passive: false });
  viewport.addEventListener('touchend', (event) => {
    if (event.touches.length < 2) touchStartDistance = 0;
  }, { passive: true });
  fit();
}
