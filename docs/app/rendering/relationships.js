import { escapeHtml } from './html.js';
import { documentNavigationUrl } from './navigation.js';

export function relationshipControls(graph) {
  if (!graph?.generated) return '';
  const coverage = graph.metadata?.coverage?.[graph.view];
  return `<div class="family-graph-controls">${graph.views.length > 1 ? `<label>Evidence <select data-family-view>${graph.views.map((view) => `<option value="${view}"${view === graph.view ? ' selected' : ''}>${view === 'facts' ? 'Facts only' : 'Include guesses'}</option>`).join('')}</select></label>` : '<span>Facts only</span>'}${coverage ? `<span>${coverage.unresolvedMentions} unresolved mentions · ${coverage.omittedRelationships} relationships omitted · ${coverage.conflicts} conflicts</span>` : ''}${!graph.valid ? `<p class="status error">${escapeHtml(graph.reason)}</p>` : '<small>Inferred identities and guess-dependent relationships are marked separately.</small>'}</div>`;
}

export function relationshipPanel(graph, key = null) {
  if (!graph?.generated || !graph.valid) return '';
  const records = new Map(graph.records.map((person) => [person._treeKey, person]));
  const link = (key) => {
    const person = records.get(key);
    return `<a class="person-link" href="?person=${encodeURIComponent(person.id || person.name)}">${escapeHtml(person.name)}</a>`;
  };
  const edges = key ? graph.reverse.get(key) || [] : graph.edges;
  if (!edges.length) return '<section class="entity-relationships"><h3>Reconstructed relationships</h3><p>No resolved relationships in this evidence view.</p></section>';
  return `<section class="entity-relationships"><h3>Reconstructed relationships</h3><ul>${edges.map((edge) => `<li><details><summary>${link(edge.person)} ${edge.type === 'parent' ? 'is parent of' : edge.type === 'spouse' ? 'is spouse of' : edge.type === 'sibling' ? 'is sibling of' : 'is kin of'} ${link(edge.of)}${edge.term ? ` (${escapeHtml(edge.term)})` : ''}${edge.inferred ? ' <span class="relationship-uncertainty">inferred identity</span>' : ''}${edge.usesGuesses ? ' <span class="relationship-uncertainty">depends on guesses</span>' : ''}</summary>${edge.derivations.map((d) => `<p>${escapeHtml(d.identity)} identity · ${d.usesGuesses ? 'uses guesses' : 'facts support'}</p><ul>${d.sources.map((source) => {
    const index = Number(source.pointer.match(/\/entries\/(\d+)/)?.[1] || 0);
    return `<li><a href="${escapeHtml(documentNavigationUrl(source.path, index))}">${escapeHtml(source.path)}#${escapeHtml(source.pointer)}</a></li>`;
  }).join('')}</ul>`).join('')}</details></li>`).join('')}</ul></section>`;
}
