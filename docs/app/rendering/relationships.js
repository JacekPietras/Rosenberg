import { escapeHtml } from './html.js';
import { documentNavigationUrl } from './navigation.js';

export function relationshipControls(graph, { focus } = {}) {
  if (!graph?.generated) return '';
  const coverage = graph.metadata?.coverage?.[graph.view];
  const status = graph.rebuilding ? 'Rebuilding family relationships…' : graph.rebuildError ? `Could not rebuild relationships. ${escapeHtml(graph.rebuildError)}`
    : graph.valid ? '' : graph.canRebuild ? 'Relationships need refreshing.'
      : 'Relationships need refreshing. <a href="http://localhost:8000/docs/?tab=tree">Open the local viewer to rebuild</a>.';
  const families = focus !== undefined && graph.components?.length ? `<label>Family group <select data-family-focus><option value="all"${focus === 'all' ? ' selected' : ''}>All family groups</option>${graph.components.map((component) => `<option value="${escapeHtml(component.key)}"${component.key === focus ? ' selected' : ''}>${escapeHtml(component.label)}</option>`).join('')}</select></label>` : '';
  const counts = coverage?.reconstructedPeople !== undefined
    ? `${coverage.reconstructedPeople} source identities · ${coverage.reconstructedRelationships} relationships · ${graph.components?.length || 0} family groups · ${coverage.conflicts} conflicts`
    : coverage ? `${coverage.unresolvedMentions} unresolved mentions · ${coverage.omittedRelationships} relationships omitted · ${coverage.conflicts} conflicts` : '';
  return `<div class="family-graph-controls">${graph.metadata && (graph.metadata.schema === undefined || graph.metadata.schema >= 4) ? '' : graph.views.length > 1 ? `<label>Evidence <select data-family-view>${graph.views.map((view) => `<option value="${view}"${view === graph.view ? ' selected' : ''}>${view === 'facts' ? 'Facts only' : 'Include guesses'}</option>`).join('')}</select></label>` : '<span>Facts only</span>'}${families}${graph.canRebuild && !graph.valid && !graph.rebuilding ? '<button type="button" data-family-rebuild>Retry rebuild</button>' : ''}<span>${escapeHtml(counts)}</span><p class="status" role="status" data-family-rebuild-status>${status}</p></div>`;
}

export function relationshipPanel(graph, key = null) {
  if (!graph?.generated || !graph.valid) return '';
  const records = new Map(graph.records.map((person) => [person._treeKey, person]));
  const link = (key) => {
    const person = records.get(key);
    return `<a class="person-link" href="?person=${encodeURIComponent(person.id || (person._evidence ? person._treeKey : person.name))}">${escapeHtml(person.name)}</a>`;
  };
  const edges = key ? graph.reverse.get(key) || [] : graph.edges;
  if (!edges.length) return '<section class="entity-relationships"><h3>Reconstructed relationships</h3><p>No resolved relationships in this evidence view.</p></section>';
  return `<section class="entity-relationships"><h3>Reconstructed relationships</h3><ul>${edges.map((edge) => `<li><details><summary>${link(edge.person)} ${edge.type === 'parent' ? 'is parent of' : edge.type === 'spouse' ? 'is spouse of' : edge.type === 'sibling' ? 'is sibling of' : 'is kin of'} ${link(edge.of)}${edge.term ? ` (${escapeHtml(edge.term)})` : ''}${edge.sourceIdentity ? ' <span class="relationship-uncertainty">source identity open</span>' : ''}${edge.inferred ? ' <span class="relationship-uncertainty">inferred identity</span>' : ''}${edge.usesGuesses ? ' <span class="relationship-uncertainty">depends on guesses</span>' : ''}</summary>${edge.derivations.map((d) => `<p>${escapeHtml(d.identity)} identity · ${d.usesGuesses ? 'uses guesses' : 'facts support'}${d.assertionWeight === undefined ? '' : ` · assertion evidence weight ${(d.assertionWeight * 100).toFixed(1)}%${d.endpointProbability === null ? '' : ` · estimated endpoint identity ${(d.endpointProbability * 100).toFixed(1)}%`}`}</p><ul>${d.sources.map((source) => {
    const index = Number(source.pointer.match(/\/entries\/(\d+)/)?.[1] || 0);
    return `<li><a href="${escapeHtml(documentNavigationUrl(source.path, index))}">${escapeHtml(source.path)}#${escapeHtml(source.pointer)}</a></li>`;
  }).join('')}</ul>`).join('')}</details></li>`).join('')}</ul></section>${identityComparisons(graph, key)}`;
}

export function identityComparisons(graph, key = null) {
  if (!graph?.valid || !graph.comparisons?.length) return '';
  const names = new Map(graph.records.map((person) => [person._treeKey, person.name]));
  const comparisons = graph.comparisons.filter((item) => (!key || [item.person, item.candidate].includes(key))
    && names.has(item.person) && names.has(item.candidate)).sort((a, b) => b.probability - a.probability);
  if (!comparisons.length) return '';
  const shown = comparisons.slice(0, key ? 100 : 30);
  return `<section class="identity-comparisons"><h3>Identity match estimates</h3><p>Uncalibrated estimates; showing ${shown.length} of ${comparisons.length} comparisons. Full calculations are stored in tree.json.</p>${shown.map((item) => `<details><summary>${escapeHtml(names.get(item.person))} / ${escapeHtml(names.get(item.candidate))} · ${item.reason.startsWith('blocked') ? 'blocked' : `${(item.probability * 100).toFixed(1)}%`} · ${escapeHtml(item.status)}</summary><p>${escapeHtml(item.reason)}${item.usesGuesses ? ' · depends on guesses' : ''}</p><ul>${item.features.map((feature) => `<li>${escapeHtml(feature.name)}: ${feature.contribution > 0 ? '+' : ''}${feature.contribution.toFixed(3)} log-odds</li>`).join('')}</ul><ul>${item.sources.map((source) => `<li><a href="${escapeHtml(documentNavigationUrl(source.path, Number(source.pointer.match(/\/entries\/(\d+)/)?.[1] || 0)))}">${escapeHtml(source.path)}#${escapeHtml(source.pointer)}</a></li>`).join('')}</ul></details>`).join('')}</section>`;
}
