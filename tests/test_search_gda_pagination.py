import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/archive_search'))
from search_gda_bayern import Client, Results


def page(updates):
    return '<partial-response><changes>' + ''.join(
        f'<update id="{key}"><![CDATA[{value}]]></update>' for key, value in updates.items()
    ) + '</changes></partial-response>'


class PaginationTests(unittest.TestCase):
    def test_extracts_citation_from_search_result(self):
        parser = Results()
        parser.feed('''<a id="searchEntry:0:docForm:searchDocumentLink" href="/gvl/archive.xhtml?id=1">491/a - Charter</a>
            <table><tr><td class="doc-header">Bestellsignatur:</td>
            <td data-label="Bestellsignatur:"><span>BayHStA, Hochstift Regensburg Urkunden <b>491/a</b></span></td></tr></table>
            <a id="searchEntry:1:docForm:searchDocumentLink" href="/gvl/archive.xhtml?id=2">Other</a>''')
        self.assertEqual(parser.rows[0]['citation'], 'BayHStA, Hochstift Regensburg Urkunden 491/a')
        self.assertNotIn('citation', parser.rows[1])

    def test_next_page_uses_new_state_and_preserves_total(self):
        initial = '<form id="searchForm"><input name="jakarta.faces.ViewState" value="initial"/></form><script nonce="nonce"></script>'
        first = page({'docsMessagePanel': '2 Datensätze gefunden',
                      'docResultPanel': '<a id="searchEntry:0:docForm:searchDocumentLink" href="/gvl/document/first">First</a>',
                      'pagingTopForm': '<a id="pagingTopForm:next" title="Zur Seite 2">2</a>',
                      'j_id1:jakarta.faces.ViewState:0': 'state-one'})
        second = page({'docResultPanel': '<a id="searchEntry:0:docForm:searchDocumentLink" href="/gvl/document/second">Second</a>',
                       'pagingTopForm': '', 'j_id1:jakarta.faces.ViewState:0': 'state-two'})
        with tempfile.TemporaryDirectory() as tmp:
            client = Client(cache_dir=Path(tmp))
            with patch.object(client, 'request', side_effect=[initial, first, second]) as request:
                rows = list(client.search('example'))
            self.assertEqual([row[0]['title'] for row in rows], ['First', 'Second'])
            self.assertEqual([row[1] for row in rows], [2, 2])
            sent = parse_qs(request.call_args_list[2].args[0].decode())
            self.assertEqual(sent['jakarta.faces.source'], ['pagingTopForm:next'])
            self.assertEqual(sent['jakarta.faces.ViewState'], ['state-one'])
            self.assertEqual(len(list(Path(tmp).glob('*.json'))), 1)


if __name__ == '__main__':
    unittest.main()
