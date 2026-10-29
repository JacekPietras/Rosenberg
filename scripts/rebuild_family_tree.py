#!/usr/bin/env python3
"""Reconstruct family relationships from typed source evidence (read-only by default).

Use --include-guesses for two independent views, --explain ID for matching
evidence, and --apply to replace registry relationships after validation.
"""

import argparse
from pathlib import Path
import sys
from family_graph import build, load_inputs
from family_graph.export import apply, serialize


def explain(result, query):
    print(f'\n{result.view}: explanations for {query}')
    for handle, decision in result.decisions.items():
        if not (query in (handle, decision.identity, decision.mention.reference)
                or any(candidate.identity == query for candidate in decision.candidates)):
            continue
        mention = decision.mention
        print(f'  {handle}: {mention.reference!r} -> {decision.identity or "unresolved"} ({decision.method}; {decision.status})')
        print(f'    date: {mention.assertion.historical_date}; {decision.reason}')
        print(f'    titles: {", ".join(mention.titles) or "none"}; deceased: {mention.deceased}; guess-dependent: {decision.uses_guesses}')
        if mention.assertion.context.get('place'):
            print(f'    issuance context: {mention.assertion.context["place"]} (not evidence of presence)')
        for candidate in decision.candidates:
            print(f'    candidate {candidate.identity}: score {candidate.score:g}' + (f'; excluded: {", ".join(candidate.exclusions)}' if candidate.exclusions else ''))
            for feature in candidate.features:
                print(f'      {feature["name"]}: {feature["score"]:g}')
            for source in {source.key: source for source in candidate.sources}.values():
                print(f'      evidence: {source.key} ({source.kind})')
    for edge in result.relationships:
        if query in (edge.person, edge.of):
            print(f'  {edge.person} --{edge.type}{f" ({edge.term})" if edge.term else ""}--> {edge.of}')
            for derivation in edge.derivations:
                print(f'    {derivation["identity"]}; usesGuesses={derivation["usesGuesses"]}')
                for source in derivation['sources']:
                    print(f'    {source["path"]}#{source["pointer"]}')
    for alternative in result.alternatives:
        for edge in alternative.get('relationships', []):
            if query in (edge.person, edge.of):
                print(f'  EXCLUDED ALTERNATIVE: {edge.person} --{edge.type}--> {edge.of}')
                for derivation in edge.derivations:
                    for source in derivation['sources']:
                        print(f'    {source["path"]}#{source["pointer"]}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-guesses', action='store_true')
    parser.add_argument('--explain', metavar='ID_OR_MENTION')
    parser.add_argument('--apply', action='store_true', help='replace relationships in data/people.json')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1], help=argparse.SUPPRESS)
    parser.add_argument('--search-limit', type=int, default=10000, help='maximum component search states')
    args = parser.parse_args(argv)
    if args.search_limit < 1:
        parser.error('--search-limit must be positive')
    try:
        inputs = load_inputs(args.root)
        results = [build(inputs, search_limit=args.search_limit)]
        if args.include_guesses:
            results.append(build(inputs, include_guesses=True, search_limit=args.search_limit))
        people = serialize(inputs, results)
        print(f'Read {len(inputs.assertions)} typed assertions; supporting prose: {inputs.prose["facts"]} facts, {inputs.prose["guesses"]} guesses.')
        for result in results:
            coverage = people[0]['familyGraph']['coverage'][result.view]
            exported = sum(any(d['view'] == result.view for d in edge['derivations']) for person in people for edge in person['relationships'])
            print(f'{result.view}: {exported} exported relationships, {coverage["omittedRelationships"]} omitted, '
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
            apply(inputs, people)
            print('Applied validated relationships to data/people.json.')
        else:
            print('Read-only: no files changed. Use --apply to replace registry relationships.')
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'Reconstruction failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
