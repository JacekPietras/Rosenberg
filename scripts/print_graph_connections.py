#!/usr/bin/env python3
"""Inspect saved graph connections for a person ID, evidence key, name, or source pointer.

Reads data/tree.json without rebuilding or modifying it. Comparisons that are not
merged or ambiguous come from the local .cache/tree-debug.json written by --apply. Parent arrows point
from parent to child; spouse, sibling and kin connections are symmetric.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from family_graph.export import DEBUG_CACHE, load_debug_tree, unpack_evidence
from family_graph.model import fingerprint
from family_graph.sources import input_manifest

ROOT = Path(__file__).resolve().parents[1]


def source_label(ref):
    return f'{ref["path"]}#{ref["pointer"]}'


def select_nodes(graph, query):
    """Exact identities take precedence over same-name or source matches."""
    exact = [n for n in graph['nodes'] if query == n['key'] or query == n.get('registry')]
    if exact:
        return exact
    if '#' in query:
        path, pointer = query.split('#', 1)
        path = path.removeprefix('./')
        matches = []
        for node in graph['nodes']:
            for mention in node.get('mentions', []):
                ref = mention['source']
                if path != ref['path']:
                    continue
                fact = ref['pointer']
                occurrence = f'{fact}/{mention["field"]}'
                # A source assertion/entry selects all participants; a field selects one.
                if (pointer in (fact, occurrence)
                        or (pointer and fact.startswith(pointer.rstrip('/') + '/'))):
                    matches.append(node)
                    break
        return matches
    return [n for n in graph['nodes'] if n['name'] == query]


def connections(graph, query, depth=1):
    roots = select_nodes(graph, query)
    if not roots:
        raise ValueError(f'No graph node matches {query!r}; evidence handles may change after rebuilding')
    selected = {n['key'] for n in roots}
    root_keys = set(selected)
    edges = []
    seen_edges = set()
    frontier = set(selected)
    for _ in range(depth):
        next_frontier = set()
        for index, edge in enumerate(graph['relationships']):
            if frontier.intersection((edge['person'], edge['of'])):
                if index not in seen_edges:
                    edges.append(edge)
                    seen_edges.add(index)
                next_frontier.update((edge['person'], edge['of']))
        frontier = next_frontier - selected
        selected.update(frontier)
    comparisons = [c for c in graph.get('comparisons', [])
                   if root_keys.intersection((c['person'], c['candidate']))]
    possible = [dict(person=n['key'], **candidate)
                for n in roots for candidate in n.get('possiblySame', [])]
    # Include labels for comparison candidates, without expanding their families.
    for comparison in comparisons:
        selected.update((comparison['person'], comparison['candidate']))
    selected.update(p['key'] for p in possible)
    return {'query': query, 'roots': [n['key'] for n in roots],
            'nodes': [n for n in graph['nodes'] if n['key'] in selected],
            'relationships': edges, 'comparisons': comparisons, 'possiblySame': possible}


def percent(value):
    return 'unresolved' if value is None else f'{value * 100:.6g}%'


def render(report, details=False, comparison_limit=10):
    nodes = {n['key']: n for n in report['nodes']}

    def label(key):
        node = nodes.get(key, {})
        return f'{node.get("name", "unknown")} [{key}]'

    def sources(refs, indent='    '):
        unique = {source_label(ref): ref for ref in refs}
        labels = sorted(unique)
        for text in labels if details else labels[:3]:
            print(indent + text)
        if not details and len(labels) > 3:
            print(f'{indent}... {len(labels) - 3} more source references (use --details)')

    print(f'Saved graph: {report["tree"]}; view: {report["view"]}; inputs: {report["inputStatus"]}')
    for key in report['roots']:
        node = nodes[key]
        print(f'\nPERSON {label(key)}')
        print(f'  {node["status"]}; identity membership confidence: '
              f'{percent(node.get("identityProbability"))} (uncalibrated)')
        print(f'  Titles: {", ".join(node.get("titles", [])) or "none"}')
        print(f'  Attested: {", ".join(node.get("dates", [])) or "undated"}')
        mentions = node.get('mentions', [])
        print(f'  Mentions: {len(mentions)}; identity support: {len(node.get("identitySources", []))} references')
        if details:
            for mention in mentions:
                print(f'    {mention.get("date", "undated")}: '
                      f'{source_label(mention["source"])}/{mention["field"]}'
                      + (f' ({mention["reference"]})' if mention.get('reference') else ''))
            print('  Identity support:')
            sources(node.get('identitySources', []))
    print(f'\nRELATIONSHIPS ({len(report["relationships"])}, depth {report["depth"]})')
    for edge in report['relationships']:
        relation = 'parent of' if edge['type'] == 'parent' else edge['type']
        if edge.get('term'):
            relation += f' ({edge["term"]})'
        arrow = '-->' if edge['type'] == 'parent' else '<-->'
        print(f'  {label(edge["person"])} --{relation}{arrow} {label(edge["of"])}')
        for derivation in edge.get('derivations', []):
            print(f'    {derivation["identity"]}; uses guesses: {derivation["usesGuesses"]}; '
                  f'assertion weight: {derivation.get("assertionWeight", "unknown")}; '
                  f'endpoint confidence: {percent(derivation.get("endpointProbability"))}')
            sources(derivation.get('sources', []), '      ')
    print(f'\nPOSSIBLY THE SAME ({len(report["possiblySame"])})')
    for candidate in report['possiblySame']:
        print(f'  {label(candidate["person"])} <--> {label(candidate["key"])}: '
              f'{percent(candidate["probability"])} (uncalibrated)')
    comparisons = report['comparisons']
    counts = Counter(c['status'] for c in comparisons)
    print(f'\nIDENTITY COMPARISONS ({len(comparisons)}; '
          + ', '.join(f'{status}: {count}' for status, count in sorted(counts.items())) + ')')
    ordered = sorted(comparisons, key=lambda c: -c.get('probability', 0))
    shown = ordered if comparison_limit == 0 else ordered[:comparison_limit]
    for comparison in shown:
        print(f'  {label(comparison["person"])} <--> {label(comparison["candidate"])}')
        print(f'    {comparison["status"]}; stage {comparison.get("stage", "?")}, '
              f'iteration {comparison.get("iteration", "?")}; '
              f'probability {percent(comparison["probability"])} (uncalibrated)'
              + (f'; share {percent(comparison["share"])}' if 'share' in comparison else ''))
        print(f'    {comparison["reason"]}; uses guesses: {comparison.get("usesGuesses", False)}')
        if details:
            for mention in comparison.get('mentions', []):
                print(f'      original mention: {mention}')
            for feature in comparison.get('features', []):
                print(f'      {feature["name"]}: {feature["contribution"]:+g} log-odds')
            sources(comparison.get('sources', []), '      ')
    if len(shown) < len(ordered):
        print(f'  ... {len(ordered) - len(shown)} more comparisons; --comparison-limit 0 prints all')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', help='person ID, @evidence/... key, exact full name, or data/FILE.json#/pointer[/person|/of]')
    parser.add_argument('--tree', type=Path, default=ROOT / 'data/tree.json')
    parser.add_argument('--root', type=Path, default=ROOT, help='repository root for checking saved inputs')
    parser.add_argument('--view', help='evidence view; defaults to with-guesses when available')
    parser.add_argument('--depth', type=int, default=1, help='family relationship hops (default: 1)')
    parser.add_argument('--details', action='store_true', help='include mentions, all source references and comparison features')
    parser.add_argument('--comparison-limit', type=int, default=10, help='highest-probability comparisons to print; 0 means all')
    parser.add_argument('--json', action='store_true', help='print full selected graph with expanded source references')
    args = parser.parse_args(argv)
    if args.depth < 1 or args.comparison_limit < 0:
        parser.error('--depth must be positive and --comparison-limit nonnegative')
    try:
        tree = json.loads(args.tree.read_text(encoding='utf-8'))
        debug = load_debug_tree(args.root / DEBUG_CACHE, tree)
        if debug is None:
            print(f'Note: {DEBUG_CACHE} is missing or from another build; only merged and ambiguous '
                  'comparisons are shown. Run rebuild_family_tree.py --apply to restore it.', file=sys.stderr)
        views = (debug or tree)['evidence']
        view = args.view or ('with-guesses' if 'with-guesses' in views else next(iter(views)))
        if view not in views:
            raise ValueError(f'Unknown view {view!r}; available: {", ".join(views)}')
        report = connections(unpack_evidence(views[view]), args.query, args.depth)
        report.update(tree=str(args.tree), view=view, depth=args.depth)
        current = input_manifest(args.root)
        stale = tree.get('inputs') != current or tree.get('fingerprint') != fingerprint(tree.get('inputs', {}))
        report['inputStatus'] = 'STALE' if stale else 'current (source fingerprints only)'
        if stale:
            print('Warning: saved graph inputs are stale; showing the saved graph without rebuilding.', file=sys.stderr)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            render(report, args.details, args.comparison_limit)
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print(f'Cannot inspect graph: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
