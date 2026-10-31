#!/usr/bin/env python3
"""Reconstruct family relationships from typed source evidence (read-only by default).

The normal tree always includes weighted guesses. Use --explain ID for matching
evidence, and --apply to write data/tree.json after validation.
"""

import argparse
from pathlib import Path
import sys
from family_graph import build, load_inputs
from family_graph.export import ConcurrentChange, apply, serialize

CONCURRENT_CHANGE = 75


def explain(result, query):
    print(f'\n{result.view}: explanations for {query}')
    for node in result.evidence_graph.get('nodes', []):
        if query not in (node['key'], node['name']):
            continue
        print(f'  SOURCE PERSON {node["key"]}: {node["name"]} ({node["status"]})')
        for mention in node['mentions']:
            ref = mention['source']
            print(f'    {mention["date"]}: {ref["path"]}#{ref["pointer"]}/{mention["field"]}')
        for edge in result.evidence_graph['relationships']:
            if node['key'] in (edge['person'], edge['of']):
                print(f'    {edge["person"]} --{edge["type"]}--> {edge["of"]}')
        for comparison in result.evidence_graph.get('comparisons', []):
            if node['key'] not in (comparison['person'], comparison['candidate']):
                continue
            print(f'    ESTIMATED {comparison["probability"]:.2%} (uncalibrated): {comparison["status"]}; {comparison["reason"]}')
            for feature in comparison['features']:
                print(f'      {feature["name"]}: {feature["contribution"]:+g} log-odds')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--explain', metavar='ID_OR_MENTION')
    parser.add_argument('--apply', action='store_true', help='write the reconstructed graph to data/tree.json')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1], help=argparse.SUPPRESS)
    parser.add_argument('--search-limit', type=int, default=10000, help='maximum component search states')
    args = parser.parse_args(argv)
    if args.search_limit < 1:
        parser.error('--search-limit must be positive')
    try:
        inputs = load_inputs(args.root)
        results = [build(inputs, include_guesses=True, search_limit=args.search_limit)]
        tree = serialize(inputs, results)
        print(f'Read {len(inputs.assertions)} typed assertions; supporting prose: {inputs.prose["facts"]} facts, {inputs.prose["guesses"]} guesses.')
        for result in results:
            coverage = tree['coverage'][result.view]
            exported = coverage['registryRelationships']
            print(f'{result.view}: {coverage["reconstructedPeople"]} source identities, '
                  f'{coverage["reconstructedRelationships"]} relationships ({exported} between registry records), '
                  f'{coverage["unresolvedMentions"]} unresolved mentions, {coverage["conflicts"]} conflicts.')
            for conflict in result.conflicts:
                print(f'  REVIEW: {conflict["reason"]}: {", ".join(conflict.get("identities", []))}')
                for source in conflict.get('sources', []):
                    print(f'    {source["path"]}#{source["pointer"]}')
            if args.explain:
                explain(result, args.explain)
        for diagnostic in results[0].diagnostics:
            print(diagnostic)
        if args.apply:
            apply(inputs, tree)
            print('Wrote validated family graph to data/tree.json.')
        else:
            print('Read-only: no files changed. Use --apply to write data/tree.json.')
    except ConcurrentChange as exc:
        print(f'Reconstruction failed: {exc}', file=sys.stderr)
        return CONCURRENT_CHANGE
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'Reconstruction failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
