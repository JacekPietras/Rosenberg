import { renderFactText } from '../rendering/facts.js?v=4';
import { formatDate } from '../rendering/dates.js';
import { escapeHtml } from '../rendering/html.js';

export function renderFactsView(facts, { people = [], inlineMarkup, itemClass = () => '', defaultDate = '' }) {
  return `<ul class="facts facts-view">${facts.map((fact, index) => {
    const date = fact?.date || defaultDate;
    const showDate = index === 0 || date !== (facts[index - 1]?.date || defaultDate);
    const dateMarkup = showDate && date
      ? `<time class="fact-date" datetime="${escapeHtml(date)}">${escapeHtml(formatDate(date))}</time>`
      : showDate ? '<span class="fact-date">Undated</span>' : '<span class="fact-date" aria-hidden="true"></span>';
    return `<li${itemClass(fact, index)}>${dateMarkup}<span class="fact-text">${renderFactText(fact, { people, inlineMarkup })}</span></li>`;
  }).join('')}</ul>`;
}
