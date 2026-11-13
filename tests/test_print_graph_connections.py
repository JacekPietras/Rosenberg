"""Read-only graph inspection, source selection and relationship direction."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from print_graph_connections import connections, main, render, select_nodes
from family_graph.export import pack_evidence, unpack_evidence
from family_graph.model import fingerprint


def graph():
    ref = {'path': 'data/documents/example.json', 'pointer': '/entries/0/facts/0', 'fingerprint': 'sha256:' + 'a' * 64}
    def node(key, field, name='Alex', date='1400'):
        return dict(key=key, name=name, status='source', dates=[date], titles=[], identityProbability=1,
                    mentions=[dict(source=ref, field=field, date=date)], identitySources=[ref])
    nodes = [node('id', 'person'), node('@evidence/a', 'of'), node('@evidence/b', 'person', 'Child')]
    nodes[2]['mentions'][0]['source'] = dict(ref, pointer='/entries/0/facts/1')
    nodes[0]['registry'] = 'id'
    nodes[0]['possiblySame'] = [{'key': '@evidence/a', 'probability': 0.6}]
    def edge(a, b):
        return dict(type='parent', person=a, of=b,
                    derivations=[dict(identity='source', usesGuesses=False, sources=[ref])])
    comparison = dict(person='id', candidate='@evidence/a', probability=0.6, status='ambiguous',
                      reason='tie', sources=[ref], features=[dict(name='shared spouse', contribution=1)])
    return dict(nodes=nodes, relationships=[edge('id', '@evidence/a'), edge('@evidence/a', '@evidence/b')],
                comparisons=[comparison])


class ConnectionTests(unittest.TestCase):
    def test_exact_id_or_evidence_key_precedes_name(self):
        g = graph()
        self.assertEqual(['id'], [n['key'] for n in select_nodes(g, 'id')])
        self.assertEqual(['@evidence/a'], [n['key'] for n in select_nodes(g, '@evidence/a')])
        self.assertEqual(2, len(select_nodes(g, 'Alex')))

    def test_source_pointer_selects_both_roles_but_field_selects_one(self):
        g = graph()
        base = 'data/documents/example.json#/entries/0/facts/0'
        self.assertEqual(['id', '@evidence/a'], [n['key'] for n in select_nodes(g, base)])
        self.assertEqual(['@evidence/a'], [n['key'] for n in select_nodes(g, base + '/of')])
        self.assertEqual(3, len(select_nodes(g, 'data/documents/example.json#/entries/0')))
        self.assertEqual([], select_nodes(g, base + '0'))

    def test_depth_preserves_direction_and_does_not_expand_comparison_families(self):
        g = graph()
        self.assertEqual(1, len(connections(g, 'id')['relationships']))
        report = connections(g, 'id', depth=2)
        self.assertEqual(2, len(report['relationships']))
        self.assertEqual('id', report['relationships'][0]['person'])
        self.assertEqual('@evidence/a', report['relationships'][0]['of'])
        self.assertEqual(1, len(report['comparisons']))
        self.assertEqual(1, len(report['possiblySame']))
        with self.assertRaises(ValueError):
            connections(g, '@evidence/missing')

    def test_packed_sources_are_expanded_and_rendered(self):
        g = unpack_evidence(pack_evidence(graph()))
        report = connections(g, 'id')
        report.update(tree='saved.json', view='with-guesses', depth=1, inputStatus='current')
        output = io.StringIO()
        with redirect_stdout(output):
            render(report, details=True)
        text = output.getvalue()
        self.assertIn('--parent of-->', text)
        self.assertIn('data/documents/example.json#/entries/0/facts/0', text)
        self.assertIn('shared spouse: +1 log-odds', text)

    def test_cli_json_reports_stale_without_changing_tree(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'tree.json'
            tree = {'evidence': {'with-guesses': pack_evidence(graph())}, 'inputs': {}, 'fingerprint': fingerprint({})}
            path.write_text(json.dumps(tree))
            original = path.read_bytes()
            output, errors = io.StringIO(), io.StringIO()
            with patch('print_graph_connections.input_manifest', return_value={'changed': 'hash'}), redirect_stdout(output), redirect_stderr(errors):
                status = main(['id', '--tree', str(path), '--json'])
            self.assertEqual(0, status)
            report = json.loads(output.getvalue())
            self.assertEqual('STALE', report['inputStatus'])
            self.assertIsInstance(report['relationships'][0]['derivations'][0]['sources'][0], dict)
            self.assertIn('stale', errors.getvalue())
            self.assertEqual(original, path.read_bytes())

    def test_cli_uses_the_matching_debug_cache_and_notes_its_absence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            kept = graph()
            full = {**kept, 'comparisons': [*kept['comparisons'], {**kept['comparisons'][0], 'status': 'below-threshold'}]}
            path = root / 'tree.json'
            tree = {'evidence': {'with-guesses': pack_evidence(kept)}, 'inputs': {}, 'fingerprint': fingerprint({})}
            path.write_text(json.dumps(tree))
            def run():
                output, errors = io.StringIO(), io.StringIO()
                with patch('print_graph_connections.input_manifest', return_value={}), redirect_stdout(output), redirect_stderr(errors):
                    self.assertEqual(0, main(['id', '--tree', str(path), '--root', str(root), '--json']))
                return len(json.loads(output.getvalue())['comparisons']), errors.getvalue()
            count, errors = run()
            self.assertIn('tree-debug.json', errors)
            (root / '.cache').mkdir()
            debug = root / '.cache/tree-debug.json'
            debug.write_text(json.dumps({**tree, 'evidence': {'with-guesses': pack_evidence(full)}}))
            more, errors = run()
            self.assertEqual(count + 1, more)
            self.assertNotIn('tree-debug.json', errors)
            debug.write_text(json.dumps({**tree, 'fingerprint': 'other', 'evidence': {'with-guesses': pack_evidence(full)}}))
            self.assertEqual(count, run()[0])


if __name__ == '__main__':
    unittest.main()
