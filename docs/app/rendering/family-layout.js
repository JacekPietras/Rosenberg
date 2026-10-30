// Lay out identities, never cloned branch occurrences. Marriage affects
// placement only; every connector still represents one recorded relationship.
// Name hints choose a visible stem only; they never supply identity or ancestry.
function fatherForDisplay(pair) {
  const masculine = /^(?:albrecht|albert|anselm|arnold|arnolt|conrad|conradus|cunz|diether|dieter|eberhard|eberhart|eckhard|engelhard|engelhart|georg|gerhard|gotfried|gottfried|götz|hans|heinemann|heinrich|henrich|johann|johannes|konrad|kraft|kunz|nicolaus|niklaus|raban|reinhard|rudolf|ruprecht|thomas|ulrich|wilhelm|wiprecht|zeisolf)$/iu;
  const feminine = /^(?:adelheid|agnes|anna|anne|barbara|christina|christine|dorothea|eilse|elisabeth|els|elsbet|elsbeth|else|elspeth|eva|gertrud|guda|gute|gutta|irmtraut|irmendrut|jutta|katharina|kunigunde|magdalena|margaretha|margarethe|maria|mechthild|sophia|sophie|ursula)$/iu;
  const first = (person) => person.name.trim().split(/\s+/)[0];
  const father = pair.find((person) => masculine.test(first(person)));
  const mother = pair.find((person) => feminine.test(first(person)));
  if (father && mother && father !== mother) return father._treeKey;
  // Retain support for the older viewer's explicit husband/wife records.
  return pair.find((person) => person.wife && pair.some((other) => other !== person && [other.id, other.name].includes(person.wife)))?._treeKey;
}

export function layoutFamilyGraph(records, relationships, { nodeWidth = 220, nodeHeight, horizontalGap = 52, simplifyParents = false } = {}) {
  const byKey = new Map(records.map((person) => [person._treeKey, person]));
  const compare = (a, b) => byKey.get(a).name.localeCompare(byKey.get(b).name) || a.localeCompare(b);
  const edges = relationships.filter((edge) => ['parent', 'spouse', 'sibling', 'kin'].includes(edge.type)
    && byKey.has(edge.person) && byKey.has(edge.of) && edge.person !== edge.of);
  const adjacent = new Map(records.map((person) => [person._treeKey, new Set()]));
  edges.forEach(({ person, of }) => { adjacent.get(person).add(of); adjacent.get(of).add(person); });
  const unseen = new Set([...byKey.keys()].sort(compare));
  const components = [];
  while (unseen.size) {
    const stack = [unseen.values().next().value], keys = new Set();
    while (stack.length) {
      const key = stack.pop();
      if (keys.has(key)) continue;
      keys.add(key); unseen.delete(key);
      stack.push(...adjacent.get(key));
    }
    components.push(layoutComponent([...keys].sort(compare), edges.filter((edge) => keys.has(edge.person))));
  }

  const padding = 28, gap = 72;
  const targetWidth = Math.max(0, ...components.map((component) => component.width), Math.sqrt(
    components.reduce((area, component) => area + (component.width + gap) * (component.height + gap), 0) * 1.6));
  let x = padding, y = padding, rowHeight = 0, width = 0;
  const cards = [], connectors = [];
  for (const component of components) {
    if (x > padding && x + component.width > padding + targetWidth) {
      x = padding; y += rowHeight + gap; rowHeight = 0;
    }
    cards.push(...component.cards.map((card) => ({ ...card, x: card.x + x, y: card.y + y })));
    connectors.push(...component.connectors.map((connector) => ({ ...connector,
      points: connector.points.map(([px, py]) => [px + x, py + y]),
      label: connector.label && [connector.label[0] + x, connector.label[1] + y] })));
    width = Math.max(width, x + component.width + padding);
    x += component.width + gap;
    rowHeight = Math.max(rowHeight, component.height);
  }
  return { cards, connectors, width, height: y + rowHeight + padding };

  function layoutComponent(keys, componentEdges) {
    const parents = componentEdges.filter((edge) => edge.type === 'parent');
    const spouses = componentEdges.filter((edge) => edge.type === 'spouse');
    const parentSets = new Map(keys.map((key) => [key, parents.filter((edge) => edge.of === key).map((edge) => edge.person).sort()]));
    const hiddenParents = new Set();
    if (simplifyParents) for (const [child, pair] of parentSets) {
      if (pair.length !== 2 || !spouses.some((edge) => pair.includes(edge.person) && pair.includes(edge.of))) continue;
      const father = fatherForDisplay(pair.map((key) => byKey.get(key)));
      if (father) parents.filter((edge) => edge.of === child && edge.person !== father).forEach((edge) => hiddenParents.add(edge));
    }
    const roots = new Map(keys.map((key) => [key, key]));
    const find = (key) => {
      while (roots.get(key) !== key) key = roots.get(key);
      return key;
    };
    spouses.forEach(({ person, of }) => roots.set(find(of), find(person)));
    const grouped = new Map();
    keys.forEach((key) => {
      const root = find(key);
      if (!grouped.has(root)) grouped.set(root, []);
      grouped.get(root).push(key);
    });
    let units = [...grouped.values()];
    let membership, ranks;
    // Spouses can share a generation unless that contraction conflicts with
    // recorded ancestry. Split conflicting units rather than duplicating people
    // or changing parentage. Legacy cyclic input also terminates here.
    while (true) {
      membership = new Map(units.flatMap((unit, index) => unit.map((key) => [key, index])));
      const children = units.map(() => new Set()), indegrees = units.map(() => 0), conflicts = new Set();
      for (const edge of parents) {
        const left = membership.get(edge.person), right = membership.get(edge.of);
        if (left === right) conflicts.add(left);
        else if (!children[left].has(right)) { children[left].add(right); indegrees[right]++; }
      }
      ranks = units.map(() => 0);
      const queue = indegrees.flatMap((degree, index) => degree ? [] : [index]);
      for (let i = 0; i < queue.length; i++) {
        const left = queue[i];
        for (const right of children[left]) {
          ranks[right] = Math.max(ranks[right], ranks[left] + 1);
          if (!--indegrees[right]) queue.push(right);
        }
      }
      indegrees.forEach((degree, index) => { if (degree) conflicts.add(index); });
      if (![...conflicts].some((index) => units[index].length > 1)) break;
      units = units.flatMap((unit, index) => conflicts.has(index) ? unit.map((key) => [key]) : [unit]);
    }
    const layers = Array.from({ length: Math.max(...ranks) + 1 }, () => []);
    units.forEach((unit, index) => { unit.sort(compare); layers[ranks[index]].push(index); });
    const familyKey = (index) => {
      const known = units[index].map((key) => parentSets.get(key)).filter((set) => set.length);
      const signatures = new Set(known.map((set) => JSON.stringify(set)));
      return signatures.size === 1 ? `parents:${[...signatures][0]}` : `unit:${index}`;
    };
    const positions = new Map();
    const updatePositions = () => layers.forEach((layer) => {
      const total = layer.reduce((sum, index) => sum + units[index].length, 0);
      let start = 0;
      layer.forEach((index) => { positions.set(index, (start + units[index].length / 2) / total); start += units[index].length; });
    });
    updatePositions();
    // Barycentric sweeps keep shared descendants near their parents while
    // retaining a single location for every identity.
    for (let pass = 0; pass < 6; pass++) {
      const down = pass % 2 === 0;
      for (const layer of down ? layers : [...layers].reverse()) {
        const scores = new Map(layer.map((index) => {
          const neighbors = parents.filter((edge) => membership.get(down ? edge.of : edge.person) === index)
            .map((edge) => membership.get(down ? edge.person : edge.of)).filter((other) => other !== index);
          return [index, neighbors.length ? neighbors.reduce((sum, other) => sum + positions.get(other), 0) / neighbors.length : positions.get(index)];
        }));
        // Keep children of the same recorded parents in one block, including
        // their spouses. Different known parent sets never share a sibling bus.
        const blocks = new Map();
        layer.forEach((index) => {
          const key = familyKey(index);
          if (!blocks.has(key)) blocks.set(key, []);
          blocks.get(key).push(index);
        });
        const score = (block) => block.reduce((sum, index) => sum + scores.get(index), 0) / block.length;
        const ordered = [...blocks.values()].sort((a, b) => score(a) - score(b) || compare(units[a[0]][0], units[b[0]][0]));
        layer.splice(0, layer.length, ...ordered.flatMap((block) => block.sort((a, b) => scores.get(a) - scores.get(b) || compare(units[a][0], units[b][0]))));
        updatePositions();
      }
    }
    const rowKeys = layers.map((layer) => layer.flatMap((index) => units[index]));
    const rowWidth = (row) => row.length * nodeWidth + Math.max(0, row.length - 1) * horizontalGap;
    const cardWidth = Math.max(...rowKeys.map(rowWidth));
    const cards = new Map();
    rowKeys.forEach((row, rank) => row.forEach((key, index) => cards.set(key, {
      person: byKey.get(key), rank, x: (cardWidth - rowWidth(row)) / 2 + index * (nodeWidth + horizontalGap),
      height: nodeHeight(byKey.get(key)),
    })));
    const slots = layers.map(() => 0), outer = { left: 0, right: 0 };
    const allocate = (rank) => slots[rank]++;
    const familySlots = new Map();
    const routes = componentEdges.filter((edge) => !hiddenParents.has(edge)).map((edge) => {
      const a = cards.get(edge.person), b = cards.get(edge.of);
      if (edge.type === 'parent' && b.rank === a.rank + 1) {
        // Children with precisely the same recorded parents can share a bus.
        // Marriage alone never supplies an additional stem or child edge.
        const family = JSON.stringify([b.rank, parentSets.get(edge.of)]);
        if (!familySlots.has(family)) familySlots.set(family, allocate(b.rank));
        return { edge, kind: 'parent', slot: familySlots.get(family) };
      }
      if (edge.type !== 'parent' && a.rank === b.rank) {
        const label = edge.type === 'kin' ? edge.term || 'kin' : edge.type;
        if (Math.abs(a.x - b.x) === nodeWidth + horizontalGap && label.length * 6 < horizontalGap - 4) return { edge, kind: 'adjacent' };
        return { edge, kind: 'above', slot: allocate(a.rank) };
      }
      const side = a.x + b.x + nodeWidth < cardWidth ? 'left' : 'right';
      const downward = edge.type === 'parent' && b.rank > a.rank;
      return { edge, kind: 'outer', side, lane: outer[side]++, downward,
        startRank: downward ? a.rank + 1 : a.rank, endRank: b.rank,
        startSlot: allocate(downward ? a.rank + 1 : a.rank), endSlot: allocate(b.rank) };
    });
    const rowHeights = rowKeys.map((row) => Math.max(...row.map((key) => cards.get(key).height)));
    const rowY = [];
    rowHeights.forEach((height, rank) => {
      rowY[rank] = rank ? rowY[rank - 1] + rowHeights[rank - 1] + 60 + slots[rank] * 12 : 32 + slots[rank] * 12;
    });
    const channelY = (rank, slot) => rowY[rank] - 20 - slot * 12;
    const leftSpace = outer.left ? 18 + outer.left * 14 : 0;
    const rightSpace = outer.right ? 18 + outer.right * 14 : 0;
    for (const card of cards.values()) card.y = rowY[card.rank];
    const connectors = routes.map((route) => {
      const { edge } = route, a = cards.get(edge.person), b = cards.get(edge.of);
      let points, label;
      if (route.kind === 'parent') {
        const ay = a.y + a.height, by = b.y, y = channelY(b.rank, route.slot);
        points = [[a.x + nodeWidth / 2, ay], [a.x + nodeWidth / 2, y], [b.x + nodeWidth / 2, y], [b.x + nodeWidth / 2, by]];
      } else if (route.kind === 'adjacent') {
        const [left, right] = a.x < b.x ? [a, b] : [b, a], y = a.y + Math.min(a.height, b.height) / 2;
        points = [[left.x + nodeWidth, y], [right.x, y]];
        label = [(left.x + nodeWidth + right.x) / 2, y - 8];
      } else if (route.kind === 'above') {
        const [left, right] = a.x < b.x ? [a, b] : [b, a], y = channelY(a.rank, route.slot);
        points = [[left.x + nodeWidth * .75, left.y], [left.x + nodeWidth * .75, y],
          [right.x + nodeWidth * .25, y], [right.x + nodeWidth * .25, right.y]];
        label = [(left.x + right.x + nodeWidth) / 2, y - 6];
      } else {
        const x = route.side === 'left' ? -18 - route.lane * 14 : cardWidth + 18 + route.lane * 14;
        const startY = channelY(route.startRank, route.startSlot), endY = channelY(route.endRank, route.endSlot);
        const port = route.side === 'left' ? .25 : .75;
        const startX = a.x + nodeWidth * (route.downward ? .5 : port), endX = b.x + nodeWidth * (route.downward ? .5 : port);
        points = [[startX, route.downward ? a.y + a.height : a.y], [startX, startY], [x, startY],
          [x, endY], [endX, endY], [endX, b.y]];
        if (edge.type !== 'parent') label = [(x + startX) / 2, startY - 6];
      }
      return { edge, points: points.map(([x, y]) => [x + leftSpace, y]), label: label && [label[0] + leftSpace, label[1]] };
    });
    return { cards: [...cards.values()].map((card) => ({ ...card, x: card.x + leftSpace })), connectors,
      width: cardWidth + leftSpace + rightSpace, height: rowY.at(-1) + rowHeights.at(-1) + 16 };
  }
}
