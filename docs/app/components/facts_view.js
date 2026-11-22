import { renderFactText, factDate, isTypedFact } from '../rendering/facts.js?v=9';
import { personMentionClass } from '../data/person-name-recognition.js?v=27';
import { formatDate } from '../rendering/dates.js';
import { escapeHtml } from '../rendering/html.js';

export function renderFactsView(facts, { people = [], personNames = [], inlineMarkup, itemClass = () => '', defaultDate = '', listClass = '', sourceHref = () => '', mention = [], places = [], showSourceLabels = false, dimSourceLabels = new Set(), hideSourceLabels = new Set() }) {
  facts = facts.filter(isTypedFact);
  const mentionRows = renderMentionRows(mention, places);
  if (!facts.length && !mentionRows) return '';
  const knownNames = [...personNames, ...facts.filter(isTypedFact).flatMap((fact) => [fact.person, fact.of])
    .filter((value) => typeof value === 'string' && !people.some((person) => person.id === value))];
  const classes = ['facts', 'facts-view', listClass].filter(Boolean).join(' ');
  return `<ul class="${classes}">${facts.map((fact, index) => {
    const date = factDate(fact, defaultDate);
    const showDate = index === 0 || date !== factDate(facts[index - 1], defaultDate);
    const dateMarkup = showDate && date
      ? `<time class="fact-date" datetime="${escapeHtml(date)}">${escapeHtml(formatDate(date))}</time>`
      : showDate ? '<span class="fact-date">Undated</span>' : '<span class="fact-date" aria-hidden="true"></span>';
    const href = sourceHref(fact, index);
    const sourceLink = href ? `<a class="fact-source-link" href="${escapeHtml(href)}" aria-label="Open fact source" title="Open fact source"></a>` : '';
    const allSourceLabels = showSourceLabels
      ? (Array.isArray(fact.sourceLabel) ? fact.sourceLabel : [fact.sourceLabel])
        .map((label) => String(label || '').trim()).filter(Boolean)
      : [];
    const sourceLabels = allSourceLabels.filter((label) => !hideSourceLabels.has(label.toLocaleLowerCase()));
    let rowClass = itemClass(fact, index);
    if (allSourceLabels.some((label) => dimSourceLabels.has(label.toLocaleLowerCase()))) {
      rowClass = rowClass
        ? rowClass.replace(/class="([^"]*)"/, (_, classes) => `class="${classes} fact-source-dimmed"`)
        : ' class="fact-source-dimmed"';
    }
    const sourceLabelMarkup = sourceLabels.map((label) => `<span class="record-label fact-source-label">${escapeHtml(label)}</span>`).join(' ');
    return `<li${href ? ' data-fact-source' : ''}${rowClass}>${dateMarkup}<span class="fact-row-content"><span class="fact-text${fact.isGuess ? ' fact-guess' : ''}">${fact.isGuess ? '<span class="visually-hidden">Guess: </span>' : ''}${renderFactText(fact, { people, personNames: knownNames, inlineMarkup })}${sourceLink}</span>${sourceLabelMarkup ? `<span class="fact-source-labels">${sourceLabelMarkup}</span>` : ''}</span></li>`;
  }).join('')}${mentionRows}</ul>`;
}

const titleText = (value) => Array.isArray(value) ? value.filter((title) => typeof title === 'string' && title.trim()).join(', ') : '';

function renderMentionRows(mention, places) {
  if (!Array.isArray(mention) || !mention.length) return '';
  const row = (label, links) => links.length
    ? `<li class="fact-mention"><span class="fact-date" aria-hidden="true"></span><span class="fact-text">${label} ${links.join(', ')}</span></li>` : '';
  const personLinks = [...new Map(mention.filter((item) => typeof item?.person === 'string')
    .map((item) => [`${item.person}\u0000${titleText(item.personTitle)}`, item])).values()]
    .map(({ person, personTitle }) => `<a class="person-link ${personMentionClass(person)}" href="?person=${encodeURIComponent(person)}">${escapeHtml(person)}</a>${titleText(personTitle) ? `, ${escapeHtml(titleText(personTitle))}` : ''}`);
  const placeLinks = [...new Set(mention.filter((item) => typeof item?.place === 'string').map((item) => places.find((place) => place.id === item.place)?.name || item.place))]
    .map((name) => `<a class="place-link" href="?place=${encodeURIComponent(name)}">${escapeHtml(name)}</a>`);
  return row('Mentions also people:', personLinks) + row('Mentions also places:', placeLinks);
}
