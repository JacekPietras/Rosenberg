import { renderFactText, factDate } from '../rendering/facts.js?v=5';
import { formatDate } from '../rendering/dates.js';
import { escapeHtml } from '../rendering/html.js';

export function renderFactsView(facts, { people = [], inlineMarkup, itemClass = () => '', defaultDate = '', listClass = '' }) {
  const classes = ['facts', 'facts-view', listClass].filter(Boolean).join(' ');
  const label = listClass === 'guesses-view' ? ' aria-label="Guesses"' : '';
  return `<ul class="${classes}"${label}>${facts.map((fact, index) => {
    const date = factDate(fact, defaultDate);
    const showDate = index === 0 || date !== factDate(facts[index - 1], defaultDate);
    const dateMarkup = showDate && date
      ? `<time class="fact-date" datetime="${escapeHtml(date)}">${escapeHtml(formatDate(date))}</time>`
      : showDate ? '<span class="fact-date">Undated</span>' : '<span class="fact-date" aria-hidden="true"></span>';
    return `<li${itemClass(fact, index)}>${dateMarkup}<span class="fact-text">${renderFactText(fact, { people, inlineMarkup })}</span></li>`;
  }).join('')}</ul>`;
}
