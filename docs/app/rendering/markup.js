import { escapeHtml } from './html.js';
import { findPlaceByName } from '../data/entities.js?v=87';
import { resolvePerson } from '../data/relationships.js?v=11';

export function createMarkupRenderer({ state }) {
  const frakturUpper = [...'𝔄𝔅ℭ𝔇𝔈𝔉𝔊ℌℑ𝔍𝔎𝔏𝔐𝔑𝔒𝔓ℜ𝔖𝔗𝔘𝔙𝔚𝔛𝔜ℨ'];
  const frakturLower = [...'𝔞𝔟𝔠𝔡𝔢𝔣𝔤𝔥𝔦𝔧𝔨𝔩𝔪𝔫𝔬𝔭𝔮𝔯𝔰𝔱𝔲𝔳𝔴𝔵𝔶𝔷'];
  function frakturMarkup(value) {
    const converted = [...value].map((character) => {
      const code = character.codePointAt(0);
      if (code >= 65 && code <= 90) return frakturUpper[code - 65];
      if (code >= 97 && code <= 122) return frakturLower[code - 97];
      return character;
    }).join('');
    return `<span class="fraktur">${escapeHtml(converted)}</span>`;
  }

  function linkedMarkup(value = '', linkEntities = true) {
    if (!linkEntities) return String(value);
    const tokens = []; const token = (markup) => { const key = `\u0000${tokens.length}\u0000`; tokens.push(markup); return key; };
    let text = String(value);
    const peopleById = new Map((state.people || []).filter((person) => person.id).map((person) => [person.id, person]));
    text = text.replace(/\[([^\]]+)\]/g, (match, id) => {
      const person = peopleById.get(id);
      return person ? token(`<a class="person-link person-id-link" href="?person=${encodeURIComponent(person.id)}">${escapeHtml(person.name)}</a>`) : match;
    });
    if (state.sourcePersonPattern) text = text.replace(state.sourcePersonPattern, (match) =>
      token(`<a class="person-link" href="?person=${encodeURIComponent(match)}">${match}</a>`));
    for (const { pattern, people } of state.personPattern || []) text = text.replace(pattern, (match) => {
      const { person, ambiguous } = resolvePerson(people, match);
      // Unqualified names use the generic name route; explicit [id] tokens above stay specific.
      return person || ambiguous ? token(`<a class="person-link" href="?person=${encodeURIComponent(match)}">${match}</a>`) : match;
    });
    for (const pattern of [state.buildingPattern, state.placePattern]) {
      if (pattern) text = text.replace(pattern, (match) => {
        const place = findPlaceByName(state.places, match);
        return place ? token(`<a class="place-link" href="?place=${encodeURIComponent(place.id || place.name)}">${match}</a>`) : match;
      });
    }
    return text.replace(/\u0000(\d+)\u0000/g, (match, index) => tokens[Number(index)] ?? match);
  }

  function inlineMarkup(value = '', linkEntities = true) {
    const renderPlainText = (plainText) => {
      const tokens = []; const token = (markup) => { const key = `\u0000${tokens.length}\u0000`; tokens.push(markup); return key; };
      let text = escapeHtml(plainText).replace(/\[\[([^\]]+)\]\]\((https?:\/\/[^)]+)\)/g, (_, label, url) => token(`<a href="${url}" target="_blank" rel="noreferrer">${linkedMarkup(label, linkEntities)}</a>`));
      text = linkedMarkup(text, linkEntities).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      return text.replace(/\u0000(\d+)\u0000/g, (match, index) => tokens[Number(index)] ?? match);
    };
    return String(value).split(/(`[^`]+`)/g).map((part) =>
      part.startsWith('`') && part.endsWith('`') ? frakturMarkup(part.slice(1, -1)) : renderPlainText(part),
    ).join('');
  }

  function personMarkup(value = '') {
    const person = (state.people || []).find((item) => item.id === String(value).replace(/^\[|\]$/g, ''));
    return person ? `<a class="person-link person-id-link" href="?person=${encodeURIComponent(person.id)}">${escapeHtml(person.name)}</a>` : inlineMarkup(value);
  }

  function markdownMarkup(value = '', linkEntities = true) {
    const output = []; let listDepth = 0; let lastIndent = -1; let itemOpen = false;
    const closeLists = () => { if (itemOpen) { output.push('</li>'); itemOpen = false; } while (listDepth > 0) { output.push('</ul>'); listDepth -= 1; } lastIndent = -1; };
    String(value).split('\n').forEach((line) => {
      const match = line.match(/^(\s*)[*+-]\s+(.+)$/);
      if (!match) { closeLists(); if (line.trim()) output.push(`<p>${inlineMarkup(line.trim(), linkEntities)}</p>`); return; }
      const indent = match[1].replace(/\t/g, '  ').length;
      if (!listDepth) { output.push('<ul class="source-list">'); listDepth = 1; }
      else if (indent > lastIndent) { output.push('<ul>'); listDepth += 1; }
      else if (indent === lastIndent) { if (itemOpen) output.push('</li>'); }
      else { if (itemOpen) output.push('</li>'); while (listDepth > 1 && indent < lastIndent) { output.push('</ul></li>'); listDepth -= 1; lastIndent = Math.max(0, lastIndent - 2); } }
      output.push(`<li>${inlineMarkup(match[2], linkEntities)}`); itemOpen = true; lastIndent = indent;
    });
    closeLists(); return output.join('');
  }

  function treeMarkup(value = '', linkEntities = true) {
    const roots = [];
    const stack = [];
    let hasUnlistedText = false;
    let hasTreeItems = false;
    let hasOrdinaryItems = false;
    String(value).split('\n').forEach((line) => {
      const match = line.match(/^(\s*)([+*])\s+(.+)$/);
      if (!match) { if (line.trim()) hasUnlistedText = true; return; }
      if (match[2] === '+') hasTreeItems = true;
      else hasOrdinaryItems = true;
      const indent = match[1].replace(/\t/g, '  ').length;
      const node = { text: match[3], children: [] };
      while (stack.length && stack.at(-1).indent >= indent) stack.pop();
      if (stack.length) stack.at(-1).node.children.push(node);
      else roots.push(node);
      stack.push({ indent, node });
    });
    if (hasUnlistedText || hasOrdinaryItems || !hasTreeItems) return markdownMarkup(value, linkEntities);
    if (!roots.length) return markdownMarkup(value, linkEntities);
    const rows = [];
    const collect = (nodes, ancestors = [], rootLevel = false) => nodes.forEach((node, index) => {
      const last = index === nodes.length - 1;
      const branchClass = last ? 'tree-branch tree-branch-last' : 'tree-branch tree-branch-continues';
      const branchText = '';
      const prefix = rootLevel ? '' : `${ancestors.map((hasMore) => `<span class="${hasMore ? 'tree-continuation' : 'tree-empty'}"></span>`).join('')}<span class="${branchClass}">${branchText}</span>`;
      const prefixDepth = rootLevel ? 0 : ancestors.length + 1;
      rows.push(`<div class="tree-row" role="listitem" style="--tree-prefix-depth:${prefixDepth}"><span class="tree-prefix" aria-hidden="true">${prefix}</span><span class="tree-label">${inlineMarkup(node.text, linkEntities)}</span></div>`);
      if (node.children.length) collect(node.children, rootLevel ? [] : [...ancestors, !last]);
    });
    collect(roots, [], true);
    return `<div class="terminal-tree" role="list">${rows.join('')}</div>`;
  }

  return {
    linkedMarkup,
    inlineMarkup,
    personMarkup,
    markdownMarkup,
    treeMarkup,
    markdownLinks: (value = '') => Array.isArray(value) ? value.map((item) => `<span class="source-line">${inlineMarkup(item)}</span>`).join('') : inlineMarkup(value),
    diagramMarkup: (value = '') => { const source = String(value).replace(/^\s*```mermaid\s*\n?/, '').replace(/\n?\s*```\s*$/, '').trim(); return source ? `<div class="diagram mermaid">${escapeHtml(source)}</div>` : ''; },
  };
}
