import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_study_notes import notes, seed
from test_study_notes_v3 import fixture_v3
from test_study_notes_v2 import Page

MATH = '<math xmlns="http://www.w3.org/1998/Math/MathML" display="block"><mrow><mi>F</mi><mo>=</mo><mi>m</mi><mi>a</mi></mrow></math>'


def draft():
    data = fixture_v3()
    section = data['items'][0]
    data['terms'] = [dict(id='force', term_zh='力', term_en='force', meaning_html='<p>使运动状态改变的相互作用。</p>', section_id=section['id'], source_refs=section['source_refs'], symbol_html='<math><mi>F</mi></math>', units_html='<p>N</p>', conditions_html='<p>本章惯性参考系。</p>', aliases=['Force'])]
    data['equations'] = [dict(id='second-law', title='牛顿第二定律', section_id=section['id'], source_refs=section['source_refs'], math_html=MATH, conditions_html='<p>质量保持不变。</p>')]
    section['body_html'] = '<p>使用 <note-ref kind="term" ref="force"/>，关系见 <note-ref kind="equation" ref="second-law"/>。</p><note-equation ref="second-law"/>' + section['body_html']
    section['summary_html'] += '<p>使用 <note-ref kind="equation" ref="second-law"/>。</p>'
    section['supplement_html'] = '<p>复核 <note-ref kind="term" ref="force"/>。</p>'
    section['answer_html'] = '<p>从 <note-ref kind="equation" ref="second-law"/> 开始。</p>'
    section['hints'] = [{'title': '关系', 'html': '<p>回到 <note-ref kind="equation" ref="second-law"/>。</p>'}]
    data['intro_html'] += '<p>可查 <note-ref kind="term" ref="force"/>。</p>'
    return data


class References(unittest.TestCase):
    def render(self, data):
        return notes.render(data, Path('/private/tmp'))

    def test_valid_and_deterministic(self):
        data = draft()
        html = self.render(data)
        self.assertEqual(html, self.render(data))
        eq = 'eq-' + hashlib.sha256(b'second-law').hexdigest()[:20]
        term = 'term-' + hashlib.sha256(b'force').hexdigest()[:20]
        self.assertEqual(html.count('id="' + eq + '"'), 1)
        self.assertEqual(html.count('id="' + term + '"'), 1)
        self.assertIn('data-note-target="' + eq + '"', html)
        self.assertIn('式（1）', html)
        self.assertIn('id="note-terms"', html)
        self.assertIn('<details><summary>术语与符号速查</summary>', html)
        self.assertNotIn('<note-ref', html)
        self.assertNotIn('<note-equation', html)
        self.assertNotIn('NOTEREF', html)
        parsed = Page(html)
        self.assertTrue(set(parsed.hashes) <= parsed.ids)
        self.assertEqual(parsed.externals, [])
        self.assertIn(' 力 force Force"', html)

    def test_bad_fields_provenance_and_markup(self):
        mutations = {
            'unknown term field': lambda d: d['terms'][0].update(mastery=True),
            'unknown equation field': lambda d: d['equations'][0].update(number=9),
            'unknown section': lambda d: d['terms'][0].update(section_id='absent'),
            'undeclared source': lambda d: d['equations'][0].update(source_refs=['lessons/no.md']),
            'duplicate term': lambda d: d['terms'].append(copy.deepcopy(d['terms'][0])),
            'duplicate equation': lambda d: d['equations'].append(copy.deepcopy(d['equations'][0])),
            'inline equation': lambda d: d['equations'][0].update(math_html='<math><mi>F</mi></math>'),
            'extra math content': lambda d: d['equations'][0].update(math_html=MATH + '<p>x</p>'),
            'HTML id': lambda d: d['terms'][0].update(meaning_html='<p id="x">x</p>'),
            'raw TeX': lambda d: d['terms'][0].update(meaning_html='<p>\\frac{x}{y}</p>'),
            'nested custom': lambda d: d['terms'][0].update(meaning_html='<p><note-ref kind="equation" ref="second-law"/></p>'),
            'bad mo form': lambda d: d['equations'][0].update(math_html='<math display="block"><mo form="evil">=</mo></math>'),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                data = draft(); mutate(data)
                with self.assertRaises((ValueError, TypeError)):
                    self.render(data)

    def test_placement_and_reference_integrity(self):
        mutations = {
            'unknown ref': lambda d: d['items'][0].update(body_html='<p><note-ref kind="equation" ref="absent"/></p>'),
            'unknown kind': lambda d: d['items'][0].update(body_html='<p><note-ref kind="other" ref="second-law"/></p>'),
            'nonempty placeholder': lambda d: d['items'][0].update(body_html='<p><note-ref kind="equation" ref="second-law">bad</note-ref></p>'),
            'attribute injection': lambda d: d['items'][0].update(body_html='<p><note-ref kind="equation" ref="second-law" onclick="evil"/></p>'),
            'missing placement': lambda d: d['items'][0].update(body_html='<p>Missing</p>'),
            'duplicate placement': lambda d: d['items'][0].update(body_html=d['items'][0]['body_html'] + '<note-equation ref="second-law"/>'),
            'summary placement': lambda d: d['items'][0].update(summary_html='<note-equation ref="second-law"/>'),
            'other section placement': lambda d: d['equations'][0].update(section_id=d['items'][1]['id']),
            'code ref': lambda d: d['items'][0].update(body_html=d['items'][0]['body_html'] + '<code><note-ref kind="term" ref="force"/></code>'),
            'math ref': lambda d: d['items'][0].update(body_html=d['items'][0]['body_html'] + '<math><note-ref kind="term" ref="force"/></math>'),
            'link ref': lambda d: d['items'][0].update(body_html=d['items'][0]['body_html'] + '<a href="https://example.com"><note-ref kind="term" ref="force"/></a>'),
            'inline canonical': lambda d: d['items'][0].update(body_html='<p><note-equation ref="second-law"/></p>'),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                data = draft(); mutate(data)
                with self.assertRaises(ValueError):
                    self.render(data)

    def test_publish_rechecks_contract_before_any_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = draft(); seed(root)
            data['items'][0]['body_html'] = '<p>Equation omitted.</p>'
            with self.assertRaisesRegex(ValueError, 'exactly once'):
                notes.publish(root, 'notes/chapters/C01.html', 'absent', data, '<html>not trusted</html>')
            self.assertFalse((root / 'notes/chapters/C01.html').exists())
            self.assertFalse((root / 'notes').exists())

    def test_reference_ids_survive_section_reordering_and_numbering_is_consistent(self):
        data = draft()
        before = self.render(data)
        data['items'].reverse()
        after = self.render(data)
        for kind, key in [('eq', 'second-law'), ('term', 'force')]:
            target = kind + '-' + hashlib.sha256(key.encode()).hexdigest()[:20]
            self.assertIn('id="' + target + '"', before)
            self.assertIn('id="' + target + '"', after)
        self.assertIn('式（1）', after)

    def test_reference_publication_keeps_stale_source_and_destination_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); seed(root)
            data = draft(); html = self.render(data)
            path = 'notes/chapters/C01.html'
            first = notes.publish(root, path, 'absent', data, html)
            target = root / path
            self.assertFalse(notes.publish(root, path, first['sha256'], data, html)['changed'])
            origin = root / data['equations'][0]['source_refs'][0]
            previous = origin.read_bytes(); origin.write_text('Source correction')
            with self.assertRaisesRegex(ValueError, 'Stale feedback'):
                notes.publish(root, path, first['sha256'], data, html)
            self.assertEqual(target.read_text(), html)
            origin.write_bytes(previous)
            target.write_text('Student annotation')
            with self.assertRaisesRegex(ValueError, 'Stale note'):
                notes.publish(root, path, first['sha256'], data, html)
            self.assertEqual(target.read_text(), 'Student annotation')

if __name__ == '__main__':
    unittest.main()
