"""Content provenance, stable navigation and backward-compatible version-2 notes."""
import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_study_notes import fixture, notes, seed


def fixture_v2():
    data = fixture()
    data['schema_version'] = 2
    data['intro_html'] = '<p>这一课从数量的变化率出发，连接模型假设、微分方程与衰减规律。复习时先理清各步的理由，再核对术语和英文表达。</p>'
    derivation = data['items'][1]
    derivation['goal_html'] = '<p>目标：根据恒定衰变概率，重新建立数量随时间的变化规律。</p>'
    derivation['hints'] = [
        {'title': '起点线索', 'html': '<p>先考虑变化率应当与哪个数量成正比，再判断变化的正负号。</p>'},
        {'title': '关键一步', 'html': '<p>把只含数量的量放到左边，只含时间的量放到右边；用初始条件选择定积分边界。</p>'}]
    derivation['key_steps'] = [
        {'title': '从模型假设建立变化率', 'action_html': '<p>将单位时间衰变概率与剩余数量联系起来，得到数量变化率。</p>',
         'why_html': '<p>剩余粒子越多，同一时间内平均发生的衰变越多，因此变化率的大小与剩余数量成正比。</p>',
         'conditions_html': '<p>粒子相互独立，且衰变常数保持不变；这里讨论统计平均数量。</p>', 'prerequisites': ['decay-model', 'decay-constant']},
        {'title': '分离变量并使用初始条件', 'action_html': '<p>把数量变量和时间变量分开，再从初始时刻积分到当前时刻。</p>',
         'why_html': '<p>分离后两边各只含一个积分变量；定积分边界同时编码初始条件，避免遗漏积分常数。</p>',
         'conditions_html': '<p>除以数量时采用数量为正的范围。若衰变常数随时间改变，必须保留在时间积分内。</p>'}]
    derivation['related'] = ['decay-model', 'decay-constant']
    constant = data['items'][2]
    constant['source_refs'].append('questions/Q01.md')
    constant['aliases'] = ['lambda', 'λ', 'decay parameter']
    constant['goal_html'] = '<p>试着用一句英文准确说明衰变常数的含义。</p>'
    constant['recall'] = ['定义应针对哪些粒子？为什么单位是时间的倒数？']
    constant['hints'] = [{'title': '定义的对象', 'html': '<p>把定义的对象限定为尚未衰变的粒子，并说清单位时间。</p>'}]
    constant['definition'] = {
        'term_zh': '衰变常数', 'term_en': 'Decay constant',
        'meaning_html': '<p>描述尚未衰变粒子的单位时间衰变概率。</p>',
        'definition_en_html': '<p>The decay constant is the probability per unit time that an undecayed particle decays.</p>',
        'conditions_html': '<p>本课模型将其取为与时间无关的常数。</p>',
        'symbols_html': '<p>符号 <math><mi>λ</mi></math>；单位 <math><msup><mi mathvariant="normal">s</mi><mrow><mo>−</mo><mn>1</mn></mrow></msup></math>。</p>',
        'contrast_html': '<p>衰变常数是单位时间的概率参数；半衰期是平均数量减半所需的时间。</p>'}
    data['items'][3]['related'] = ['decay-constant']
    data['coverage'] = [
        {'id': 'feedback-model', 'topic': '独立粒子与恒定衰变概率', 'source_refs': ['lessons/L01.md'], 'status': 'included', 'item_ids': ['decay-model'], 'source_location': '合成教师反馈：模型假设'},
        {'id': 'feedback-law', 'topic': '分离变量、初始条件及指数规律', 'source_refs': ['lessons/L01.md'], 'status': 'included', 'item_ids': ['decay-law']},
        {'id': 'feedback-term', 'topic': '衰变常数及其单位', 'source_refs': ['lessons/L01.md'], 'status': 'included', 'item_ids': ['decay-constant']},
        {'id': 'feedback-example', 'topic': '已展示的半衰期示范', 'source_refs': ['questions/Q01.md'], 'status': 'merged', 'item_ids': ['decay-constant'], 'reason': '合并在衰变常数与半衰期的区别中，保留原关系式。'},
        {'id': 'feedback-expression', 'topic': '无真题依据时的英文参考表达', 'source_refs': ['exam/profile.md'], 'status': 'included', 'item_ids': ['state-definition']}
    ]
    return data


class Page(HTMLParser):
    def __init__(self, value):
        super().__init__()
        self.ids, self.hashes, self.externals = set(), [], []
        self.feed(value)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if 'id' in attrs:
            if attrs['id'] in self.ids:
                raise AssertionError('Duplicate HTML id: ' + attrs['id'])
            self.ids.add(attrs['id'])
        if tag == 'a' and attrs.get('href', '').startswith('#'):
            self.hashes.append(attrs['href'][1:])
        if tag in {'script', 'img', 'link', 'iframe'}:
            address = attrs.get('src', attrs.get('href', ''))
            if address and not address.startswith('data:'):
                self.externals.append(address)


class StructuredNoteTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)
        self.data = fixture_v2()

    def test_stable_ids_and_related_links_survive_reordering(self):
        first = Page(notes.render(self.data, self.base))
        self.data['items'].reverse()
        second = Page(notes.render(self.data, self.base))
        for item in self.data['items']:
            expected = notes.sections.anchor(item['id'])
            self.assertIn(expected, first.ids)
            self.assertIn(expected, second.ids)
        self.assertTrue(set(first.hashes) <= first.ids)
        self.assertTrue(set(second.hashes) <= second.ids)
        self.assertEqual(first.externals, [])

    def test_missing_or_fictitious_coverage_is_rejected(self):
        cases = [lambda d: d.pop('coverage'), lambda d: d.update(coverage=[]),
                 lambda d: d['coverage'][0].update(item_ids=['invented']),
                 lambda d: d['coverage'][0].update(source_refs=['absent.md']),
                 lambda d: d['coverage'][0].update(source_refs=['exam/profile.md']),
                 lambda d: d['coverage'].pop(),
                 lambda d: d['coverage'].append(copy.deepcopy(d['coverage'][0]))]
        for mutate in cases:
            value = copy.deepcopy(self.data)
            mutate(value)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                notes.render(value, self.base)

    def test_omissions_must_be_explained_and_visible(self):
        self.data['coverage'].append({'id': 'pending-assumption', 'topic': '需要原教师进一步核对的条件', 'source_refs': ['lessons/L01.md'], 'status': 'unresolved', 'item_ids': []})
        with self.assertRaisesRegex(ValueError, 'reason'):
            notes.render(self.data, self.base)
        self.data['coverage'][-1]['reason'] = '该条件的说明不足，交回原维护者核对。'
        html = notes.render(self.data, self.base)
        self.assertIn(self.data['coverage'][-1]['topic'], html)
        self.assertIn(self.data['coverage'][-1]['reason'], html)
        self.data['coverage'][-1]['item_ids'] = ['decay-model']
        with self.assertRaisesRegex(ValueError, 'cannot claim'):
            notes.render(self.data, self.base)

    def test_step_requires_a_reason_and_real_prerequisites(self):
        step = self.data['items'][1]['key_steps'][0]
        why = step.pop('why_html')
        with self.assertRaisesRegex(ValueError, 'why_html'):
            notes.render(self.data, self.base)
        step['why_html'] = why
        step['prerequisites'] = ['not-in-this-document']
        with self.assertRaisesRegex(ValueError, 'prerequisites'):
            notes.render(self.data, self.base)

    def test_new_html_fields_obey_existing_math_and_offline_guards(self):
        for mutate in [lambda d: d['items'][2]['definition'].update(definition_en_html=r'<code>\frac{1}{2}</code>'),
                       lambda d: d['items'][1]['hints'][0].update(html='<img src="https://example.com/a.png" alt="remote"/>'),
                       lambda d: d['items'][1]['key_steps'][0].update(why_html='<script>alert(1)</script>'),
                       lambda d: d.update(intro_html='<iframe src="https://example.com"/>')]:
            value = copy.deepcopy(self.data); mutate(value)
            with self.assertRaises(ValueError):
                notes.render(value, self.base)

    def test_legacy_payload_still_renders_without_coverage_or_new_inputs(self):
        legacy = fixture()
        before = copy.deepcopy(legacy)
        self.assertIn('指数衰减', notes.render(legacy, self.base))
        self.assertEqual(legacy, before)

    def test_bilingual_passages_keep_language_annotations_without_relaxing_shared_renderer(self):
        self.data['items'][2]['definition']['definition_en_html'] = '<p lang="en">The constant describes the rate per undecayed particle.</p>'
        self.data['intro_html'] = '<figure><p>模型关系示意</p><figcaption lang="zh-CN">仅供本课解释。</figcaption></figure>'
        rendered = notes.render(self.data, self.base)
        self.assertIn('<p lang="en">', rendered)
        self.assertIn('<figcaption lang="zh-CN">', rendered)
        shared = notes.helper('unchanged_review_renderer', 'render_review.py')
        with self.assertRaisesRegex(ValueError, 'lang'):
            shared.render_fragment('<p lang="en">Example</p>', self.base)

    def test_invalid_payload_cannot_publish_an_unchecked_v2_inventory(self):
        root = self.base / 'course';seed(root)
        self.data['coverage'] = []
        with self.assertRaisesRegex(ValueError, 'coverage'):
            notes.publish(root, 'notes/lesson.html', 'absent', self.data, 'unchecked')
        self.assertFalse((root / 'notes').exists())

    def test_coverage_is_not_a_learner_state(self):
        self.data['coverage'][0]['mastery'] = 'learned'
        with self.assertRaises(ValueError):
            notes.render(self.data, self.base)
        self.data = fixture_v2()
        self.data['mastery'] = 'learned'
        with self.assertRaises(ValueError):
            notes.render(self.data, self.base)


if __name__ == '__main__':
    unittest.main(verbosity=2)
