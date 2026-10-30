import { buildRelationshipGraph, focusFamilyGraph } from '../data/relationships.js?v=4';
import { relationshipControls, relationshipPanel } from '../rendering/relationships.js?v=3';
import { layoutFamilyGraph } from '../rendering/family-layout.js?v=1';

function svgEscape(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
}

function regexEscape(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function renderPeopleTree(people = [], documents = [], { graph, focus } = {}) {
  graph ||= buildRelationshipGraph(Array.isArray(people) ? people : []);
  graph = focusFamilyGraph(graph, focus);
  const records = graph.records.filter((person) => person?.name);
  if (!records.length) return '<div class="people-tree"><p class="status">No people found.</p></div>';

  const documentRecords = documents instanceof Map ? [...documents.entries()] : Array.isArray(documents) ? documents.map((doc) => ['', doc]) : [];
  const mentionedYears = new Map(records.map((person) => {
    const years = new Set();
    if (person.reconstruction) {
      person.reconstruction.dates.forEach((date) => (date.match(/\d{4}/g) || []).forEach((year) => years.add(year)));
      return [person._treeKey, [...years].sort()];
    }
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
    person._evidence ? person.reconstruction.status === 'contextual' ? 'contextual identity · inferred' : 'source person · identity open' : '',
    ...(Array.isArray(person.titles) ? person.titles : []),
    person.born || person.died ? `${person.born || '?'}–${person.died || '?'}` : '',
    mentionedYears.get(person._treeKey)?.length
      ? `mentioned: [${mentionedYears.get(person._treeKey)[0]}${mentionedYears.get(person._treeKey).length > 1 ? `-${mentionedYears.get(person._treeKey).at(-1)}` : ''}]`
      : '',
  ].filter(Boolean).flatMap((line, index) => {
    const lines = [''];
    for (const word of line.split(/\s+/)) {
      if (lines.at(-1) && lines.at(-1).length + word.length + 1 > (index ? 31 : 24)) lines.push(word);
      else lines[lines.length - 1] += `${lines.at(-1) ? ' ' : ''}${word}`;
    }
    return lines.map((text) => ({ text, name: index === 0 }));
  });
  const nodeHeightFor = (person) => Math.max(44, 25 + (personLines(person).length - 1) * 18 + 10);
  const nodeWidth = 220;
  const { cards, connectors, width, height } = layoutFamilyGraph(records, graph.edges, {
    nodeWidth, nodeHeight: nodeHeightFor,
  });
  const edges = connectors.map(({ edge, points, label }) => {
    const path = points.map(([x, y], index) => !index ? `M${x} ${y}`
      : points[index - 1][1] === y ? `H${x}` : `V${y}`).join(' ');
    const title = `${records.find((person) => person._treeKey === edge.person).name} · ${edge.type} · ${records.find((person) => person._treeKey === edge.of).name}`;
    return `<path class="people-tree-${edge.type}" data-person="${svgEscape(edge.person)}" data-of="${svgEscape(edge.of)}" data-identity="${edge.inferred ? 'inferred' : 'anchored'}" fill="none" d="${path}"><title>${svgEscape(title)}</title></path>${label ? `<text class="people-tree-edge-label" x="${label[0]}" y="${label[1]}">${graph.generated ? 'spouse' : 'wife'}</text>` : ''}`;
  });
  const nodes = cards.map(({ person, x, y }) => {
    const nodeHeight = nodeHeightFor(person);
    const text = personLines(person).map((line, index) => `<tspan class="${line.name ? 'people-tree-name' : 'people-tree-detail'}" x="${x + nodeWidth / 2}" dy="${index ? 18 : 0}">${svgEscape(line.text)}</tspan>`).join('');
    const href = `?person=${encodeURIComponent(person.id || (person._evidence ? person._treeKey : person.name))}`;
    return `<a class="people-tree-person-link" href="${svgEscape(href)}" aria-label="View ${svgEscape(person.name)}"><g class="people-tree-node"><rect x="${x}" y="${y}" width="${nodeWidth}" height="${nodeHeight}" rx="8"/><text x="${x + nodeWidth / 2}" y="${y + 25}" text-anchor="middle">${text}</text></g></a>`;
  }).join('');
  return `${relationshipControls(graph, { focus })}<section class="people-tree-wrap" aria-label="Family tree viewer"><div class="people-tree"><svg viewBox="0 0 ${width} ${height}" role="group" aria-label="Family tree">${edges.join('')}${nodes}</svg></div></section>${relationshipPanel(graph)}`;
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
