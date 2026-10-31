import { buildRelationshipGraph, focusFamilyGraph, resolveEvidencePointer } from '../data/relationships.js?v=10';
import { relationshipControls } from '../rendering/relationships.js?v=10';
import { factText, factPersonMatch, factDate } from '../rendering/facts.js?v=8';
import { renderFactsView } from '../components/facts_view.js?v=8';
import { createMarkupRenderer } from '../rendering/markup.js';
import { documentNavigationUrl } from '../rendering/navigation.js';
import { dateSortValue } from '../rendering/dates.js';
import { layoutFamilyGraph } from '../rendering/family-layout.js?v=4';

function svgEscape(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
}

function regexEscape(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function personFacts(person, documentRecords, people) {
  const facts = [];
  const add = (fact, date, path, pointer) => {
    if (fact == null) return;
    const text = factText(fact, people).trim();
    if (text) facts.push({ ...(typeof fact === 'object' ? fact : { text: fact }), isGuess: pointer.includes('/guesses/'), date: factDate(fact, date), sourceHref: path ? documentNavigationUrl(path, Number(pointer.match(/\/entries\/(\d+)/)?.[1] || 0)) : '' });
  };
  if (person.reconstruction) {
    const documents = new Map(documentRecords);
    const seen = new Set();
    for (const { source, date } of person.reconstruction.mentions) {
      const key = `${source.path}#${source.pointer}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const doc = documents.get(source.path);
      if (doc) add(resolveEvidencePointer(doc, source.pointer), date, source.path, source.pointer);
    }
  } else {
    for (const [path, doc] of documentRecords) {
      const explicit = /^data\/(books|notes)\//.test(path) || !!doc?.book;
      const visit = (value, inherited = '', pointer = '') => {
        if (!value || typeof value !== 'object') return;
        const date = explicit ? '' : Object.hasOwn(value, 'date') ? value.date : inherited;
        Object.entries(value).forEach(([key, child]) => {
          const next = `${pointer}/${key.replaceAll('~', '~0').replaceAll('/', '~1')}`;
          if (key === 'facts' || key === 'guesses') {
            (Array.isArray(child) ? child : []).forEach((fact, index) => {
              if (factPersonMatch(fact, person.id || person.name, people) === 'direct') add(fact, date, path, `${next}/${index}`);
            });
          } else visit(child, date, next);
        });
      };
      visit(doc);
    }
  }
  return facts.sort((a, b) => dateSortValue(a.date) - dateSortValue(b.date));
}

export function renderPeopleTree(people = [], documents = [], { graph, focus, inlineMarkup = createMarkupRenderer({ state: { people } }).inlineMarkup } = {}) {
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
    person.reconstruction?.status === 'contextual' && person.reconstruction.identityProbability < 1 ? `identity estimate: ${(person.reconstruction.identityProbability * 100).toFixed(1)}%` : '',
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
    nodeWidth, nodeHeight: nodeHeightFor, simplifyParents: true,
  });
  const edges = connectors.map(({ edge, points, label, hidden }) => {
    const path = points.map(([x, y], index) => !index ? `M${x} ${y}`
      : points[index - 1][1] === y ? `H${x}` : `V${y}`).join(' ');
    const title = `${records.find((person) => person._treeKey === edge.person).name} · ${edge.type} · ${records.find((person) => person._treeKey === edge.of).name}`;
    const labelText = edge.type === 'kin' ? edge.term || 'kin' : edge.type === 'spouse' && !graph.generated ? 'wife' : edge.type;
    return `<g class="people-tree-edge"${hidden || !['parent', 'spouse'].includes(edge.type) ? ' data-tree-hover-only="true"' : ''} data-person="${svgEscape(edge.person)}" data-of="${svgEscape(edge.of)}"><path class="people-tree-${edge.type}" data-person="${svgEscape(edge.person)}" data-of="${svgEscape(edge.of)}" data-identity="${edge.inferred ? 'inferred' : 'anchored'}" fill="none" d="${path}"><title>${svgEscape(title)}${edge.term ? ` (${svgEscape(edge.term)})` : ''}</title></path>${label ? `<text class="people-tree-edge-label" x="${label[0]}" y="${label[1]}">${svgEscape(labelText)}</text>` : ''}</g>`;
  });
  const factsTemplates = [];
  const nodes = cards.map(({ person, x, y }, index) => {
    const facts = personFacts(person, documentRecords, people);
    const evidence = [false, true].map((isGuess) => {
      const items = facts.filter((fact) => fact.isGuess === isGuess);
      return items.length ? renderFactsView(items, { people, personNames: graph.records.map((person) => person.name), inlineMarkup, listClass: isGuess ? 'guesses-view' : '', sourceHref: (fact) => fact.sourceHref }) : '';
    }).join('');
    factsTemplates.push(`<template data-tree-facts="${index}">${evidence || '<p class="status">No recorded facts or guesses for this person.</p>'}</template>`);
    const nodeHeight = nodeHeightFor(person);
    const text = personLines(person).map((line, index) => `<tspan class="${line.name ? 'people-tree-name' : 'people-tree-detail'}" x="${x + nodeWidth / 2}" dy="${index ? 18 : 0}">${svgEscape(line.text)}</tspan>`).join('');
    const href = `?person=${encodeURIComponent(person.id || (person._evidence ? person._treeKey : person.name))}`;
    return `<a class="people-tree-person-link" data-person="${svgEscape(person._treeKey)}" data-tree-facts="${index}" href="${svgEscape(href)}" aria-label="View ${svgEscape(person.name)}"><g class="people-tree-node"><rect x="${x}" y="${y}" width="${nodeWidth}" height="${nodeHeight}" rx="8"/><text x="${x + nodeWidth / 2}" y="${y + 25}" text-anchor="middle">${text}</text></g></a>`;
  }).join('');
  return `${relationshipControls(graph, { focus })}<section class="people-tree-wrap" aria-label="Family tree viewer"><div class="people-tree"><svg viewBox="0 0 ${width} ${height}" role="group" aria-label="Family tree">${edges.join('')}${nodes}</svg></div><aside class="people-tree-facts" id="people-tree-facts" aria-label="Person facts" hidden></aside>${factsTemplates.join('')}</section>`;
}

export function setupPeopleTreeZoom(root = document) {
  const wrapper = root.querySelector('.people-tree-wrap');
  const svg = wrapper?.querySelector('.people-tree svg');
  if (!wrapper || !svg) return;
  const nodes = [...svg.querySelectorAll('.people-tree-person-link')];
  const edges = [...svg.querySelectorAll('.people-tree-edge')];
  const highlightPerson = (node) => {
    svg.classList.toggle('people-tree-highlighting', !!node);
    nodes.forEach((item) => item.classList.toggle('people-tree-highlighted', item === node));
    edges.forEach((edge) => edge.classList.toggle('people-tree-highlighted', !!node && (edge.dataset.person === node.dataset.person || edge.dataset.of === node.dataset.person)));
  };
  const panel = wrapper.querySelector('.people-tree-facts');
  const templates = [...wrapper.querySelectorAll('template[data-tree-facts]')];
  let activeNode = null;
  const hideFacts = () => {
    activeNode?.removeAttribute('aria-describedby');
    activeNode = null;
    panel.hidden = true;
    highlightPerson(null);
  };
  const showFacts = (node) => {
    highlightPerson(node);
    if (node === activeNode) return;
    activeNode?.removeAttribute('aria-describedby');
    activeNode = node;
    panel.replaceChildren(templates.find((template) => template.dataset.treeFacts === node.dataset.treeFacts).content.cloneNode(true));
    panel.hidden = false;
    panel.scrollTop = 0;
    node.setAttribute('aria-describedby', panel.id);
  };
  svg.addEventListener('pointerover', (event) => {
    const node = event.target.closest('.people-tree-person-link');
    if (node) showFacts(node);
  });
  svg.addEventListener('pointerout', (event) => {
    const node = event.target.closest('.people-tree-person-link');
    if (node && !node.contains(event.relatedTarget)) highlightPerson(null);
  });
  svg.addEventListener('focusout', (event) => {
    const node = event.target.closest('.people-tree-person-link');
    if (node && !node.contains(event.relatedTarget)) highlightPerson(null);
  });
  svg.addEventListener('focusin', (event) => {
    const node = event.target.closest('.people-tree-person-link');
    if (node) showFacts(node);
  });
  wrapper.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hideFacts();
  });
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
