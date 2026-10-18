"""Lecture articles remain complete, source-bound and compatible with old notes."""
import copy
from html.parser import HTMLParser
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_study_notes import fixture, notes, seed
from test_study_notes_v2 import Page


def fixture_v3():
    old = fixture()
    data = {key: old[key] for key in ('course', 'unit', 'scope', 'sources')}
    data.update(schema_version=3, kind='chapter', intro_html='<p>从物理假设到模型，再看模型如何用于已讲示范。</p>')
    data['items'] = []
    for item in old['items'][:2]:
        data['items'].append({key: copy.deepcopy(item[key]) for key in ('id', 'title', 'source', 'source_refs', 'summary_html', 'recall')})
        data['items'][-1]['body_html'] = item['detail_html']
    data['items'][0]['body_html'] += '<p lang="en">Reference expression: The decay constant is the probability per unit time that an undecayed particle decays.</p>'
    data['items'][0].update(exam_basis='reference', exam_reference='已讲定义的自拟参考表达', aliases=['decay constant'])
    data['items'][1]['hints'] = [{'title': '第一条线索', 'html': '<p>先想变化率与哪个数量成正比。</p>'}, {'title': '第二条线索', 'html': '<p>再用初始条件选择积分边界。</p>'}]
    data['items'][1]['answer_html'] = '<p>建立变化率方程，分离变量，使用初始条件积分，再取指数。</p>'
    data['items'][1]['supplement_html'] = '<p>本节以平均数量为对象，个别粒子的实际衰变时间有随机性。</p>'
    data['items'][1]['supplement_title'] = '补充：个别粒子与平均数量'
    data['items'][1]['related'] = ['decay-model']
    data['coverage'] = [{'id': 'input-' + item['id'], 'topic': item['title'], 'source_refs': item['source_refs'], 'status': 'included', 'item_ids': [item['id']]} for item in data['items']]
    return data


class CoreReader(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.stack, self.core, self.folded = [], [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag not in {'meta', 'input', 'img', 'br', 'link', 'hr'}:
            self.stack.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, value):
        if any(a.get('data-panel') == 'full' for _, a in self.stack):
            if any(tag == 'details' for tag, _ in self.stack):
                self.folded.append(value)
            elif not any('hidden' in a for _, a in self.stack):
                self.core.append(value)


class LectureNoteTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)
        self.data = fixture_v3()

    def test_prices_pass_body_metadata_and_locked_publication(self):
        data = copy.deepcopy(self.data)
        price = '成本从 $5 升到 $10。'
        data['unit'] += ' · ' + price
        data['scope'] += price
        data['intro_html'] = '<p>' + price + '</p>'
        data['items'][0]['body_html'] += '<p>' + price + '</p>'
        data['items'][0]['summary_html'] += '<p>' + price + '</p>'
        html = notes.render(data, self.base)
        self.assertIn(price, html)
        root = self.base / 'course'
        seed(root)
        source = root / 'notes/chapters/prices.json'
        import json
        saved = notes.records.write_record(root, 'notes/chapters/prices.json', 'notes', 'absent', json.dumps(data, ensure_ascii=False))
        receipt = notes.publish(root, 'notes/chapters/prices.html', 'absent', data, html,
                                input_path=source, input_sha256=saved['sha256'])
        self.assertTrue(receipt['changed'])
        self.assertIn(price, (root / receipt['path']).read_text())

    def test_numeric_raw_math_still_rejected_in_body_metadata_and_code(self):
        for raw in ('$2x+1', '$2 x+1', '$20$', r'\frac{1}{2}'):
            for field in ('body', 'metadata', 'code'):
                data = copy.deepcopy(self.data)
                if field == 'metadata':
                    data['scope'] += raw
                else:
                    tag = 'pre' if field == 'code' else 'p'
                    data['items'][0]['body_html'] += '<' + tag + '>' + raw + '</' + tag + '>'
                with self.subTest(raw=raw, field=field), self.assertRaises(ValueError):
                    notes.render(data, self.base)

    def test_full_core_is_readable_without_unfolding_or_javascript(self):
        html = notes.render(self.data, self.base)
        page = CoreReader(html)
        self.assertIn('为什么分离变量', ''.join(page.core))
        self.assertIn('初始时刻数量等于初始值', ''.join(page.core))
        self.assertIn('个别粒子的实际衰变时间有随机性', ''.join(page.folded))
        self.assertNotIn('class="explanation"', html)
        parsed = Page(html)
        self.assertTrue(set(parsed.hashes) <= parsed.ids)
        self.assertEqual(parsed.externals, [])

    def test_three_views_keep_answers_out_of_initial_recall_task(self):
        html = notes.render(self.data, self.base)
        self.assertIn('data-panel="summary" hidden', html)
        self.assertIn('data-panel="recall" hidden', html)
        recall = html.split('data-panel="recall" hidden', 1)[1].split('</main>', 1)[0]
        self.assertNotIn('<h2>' + self.data['items'][1]['title'] + '</h2>', recall)
        self.assertIn('为什么要分离变量', recall)
        self.assertIn('看一条提示', recall)

    def test_sections_need_bodies_coverage_and_exam_provenance(self):
        mutations = [lambda d: d['items'][0].pop('body_html'),
                     lambda d: d['items'][0].update(body_html=''),
                     lambda d: d['items'][0].update(mastery='learned'),
                     lambda d: d['coverage'].pop(),
                     lambda d: d['items'][0].update(exam_basis='past-paper'),
                     lambda d: d['items'][0].pop('exam_basis')]
        for mutate in mutations:
            value = copy.deepcopy(self.data); mutate(value)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                notes.render(value, self.base)

    def test_new_fragments_keep_math_and_offline_guards(self):
        for field in ('body_html', 'summary_html', 'answer_html', 'supplement_html'):
            for raw in (r'<code>\frac{1}{2}</code>', '<script>alert(1)</script>', '<img src="https://example.com/x.png" alt="remote"/>'):
                value = copy.deepcopy(self.data); value['items'][1][field] = raw
                with self.subTest(field=field, raw=raw), self.assertRaises(ValueError):
                    notes.render(value, self.base)

    def test_caption_and_native_operator_form_preserve_scientific_markup(self):
        self.data['items'][0]['body_html'] += '<table><caption>模型量</caption><tr><th>量</th><td>单位</td></tr></table><math><mo form="prefix">−</mo><mi>x</mi></math>'
        html = notes.render(self.data, self.base)
        self.assertIn('<caption>模型量</caption>', html)
        self.assertIn('form="prefix"', html)
        self.data['items'][0]['body_html'] = '<math><mi form="prefix">x</mi></math>'
        with self.assertRaises(ValueError):
            notes.render(self.data, self.base)
        shared = notes.helper('unchanged_shared_review', 'render_review.py')
        with self.assertRaises(ValueError):
            shared.render_fragment('<table><caption>Source</caption></table>', self.base)

    def test_course_synthesis_uses_same_self_contained_article(self):
        self.data['kind'] = 'course'
        self.data['lesson_links'] = [{'title': '本课程第一章', 'path': 'chapters/C01.html'}]
        html = notes.render(self.data, self.base)
        self.assertIn('href="chapters/C01.html"', html)
        self.assertIn('为什么分离变量', html)

    def test_v3_publish_protects_sources_and_manual_annotations(self):
        root = self.base / 'course'; seed(root)
        rel = 'notes/chapters/C01.html'
        html = notes.render(self.data, self.base)
        first = notes.publish(root, rel, 'absent', self.data, html)
        target = root / rel
        source = root / 'lessons/L01.md'
        previous = source.read_bytes()
        source.write_text('Corrected upstream feedback')
        with self.assertRaisesRegex(ValueError, 'Stale feedback'):
            notes.publish(root, rel, first['sha256'], self.data, html)
        self.assertEqual(target.read_text(), html)
        source.write_bytes(previous)
        target.write_text('User annotation')
        with self.assertRaisesRegex(ValueError, 'Stale note'):
            notes.publish(root, rel, first['sha256'], self.data, html)
        self.assertEqual(target.read_text(), 'User annotation')
        self.data['coverage'] = []
        with self.assertRaises(ValueError):
            notes.publish(root, 'notes/chapters/C02.html', 'absent', self.data, html)
        self.assertFalse((root / 'notes/chapters/C02.html').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
