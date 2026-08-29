import { escapeHtml } from './html.js';

export function createMarkupRenderer({ state }) {
  function linkedMarkup(value = '', linkEntities = true) {
    if (!linkEntities) return String(value);
    const tokens = []; const token = (markup) => { const key = `\u0000${tokens.length}\u0000`; tokens.push(markup); return key; };
    let text = String(value);
    for (const { pattern, people } of state.personPattern || []) text = text.replace(pattern, (match) => {
      const person = people.find((item) => item.name.toLocaleLowerCase() === match.toLocaleLowerCase());
      return person ? token(`<a class="person-link" href="?person=${encodeURIComponent(person.name)}">${match}</a>`) : match;
    });
    if (state.placePattern) text = text.replace(state.placePattern, (match) => {
      const place = state.places.find((item) => item.name.toLocaleLowerCase() === match.toLocaleLowerCase());
      return place ? token(`<a class="place-link" href="?place=${encodeURIComponent(place.name)}">${match}</a>`) : match;
    });
    return text.replace(/\u0000(\d+)\u0000/g, (match, index) => tokens[Number(index)] ?? match);
  }

  function inlineMarkup(value = '', linkEntities = true) {
    const tokens = []; const token = (markup) => { const key = `\u0000${tokens.length}\u0000`; tokens.push(markup); return key; };
    let text = escapeHtml(value).replace(/\[\[([^\]]+)\]\]\((https?:\/\/[^)]+)\)/g, (_, label, url) => token(`<a href="${url}" target="_blank" rel="noreferrer">${linkedMarkup(label, linkEntities)}</a>`));
    text = linkedMarkup(text, linkEntities).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    return text.replace(/\u0000(\d+)\u0000/g, (match, index) => tokens[Number(index)] ?? match);
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

  return {
    linkedMarkup,
    inlineMarkup,
    markdownMarkup,
    markdownLinks: (value = '') => Array.isArray(value) ? value.map((item) => `<span class="source-line">${inlineMarkup(item)}</span>`).join('') : inlineMarkup(value),
    diagramMarkup: (value = '') => { const source = String(value).replace(/^\s*```mermaid\s*\n?/, '').replace(/\n?\s*```\s*$/, '').trim(); return source ? `<div class="diagram mermaid">${escapeHtml(source)}</div>` : ''; },
  };
}
