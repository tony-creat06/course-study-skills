"""Synthetic feedback only: offline rendering, provenance and shared-role isolation."""
import base64
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/study-notes/scripts/render_notes.py'
spec = importlib.util.spec_from_file_location('notes', SCRIPT)
notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notes)

FEEDBACK = {
    'course.md': ('study-planner', 'Synthetic course, learner fixture only; taught unit L01. No real student evidence.'),
    'lessons/L01.md': ('course-study', 'Synthetic lesson: assume constant independent decay probability per unit time. dN/dt=-λN. Divide by N, integrate from N0 at t=0 to N at t. ln(N/N0)=-λt; N=N0 exp(-λt). λ has unit s^-1. Half-life is ln(2)/λ. This derivation was shown; no learner answer.'),
    'exam/profile.md': ('exam-analysis', 'Synthetic feedback: no verified past papers. A concise English definition may be offered as a reference expression only.'),
    'questions/Q01.md': ('practice-builder', 'Synthetic shown example: starting from the taught decay law, setting N=N0/2 gives the half-life ln(2)/λ. Q02 is a future unshown question and its solution must remain in questions.'),
}


def fixture():
    sources = [{'module': role, 'path': path, 'sha256': notes.records.digest(body.encode())}
               for path, (role, body) in FEEDBACK.items()]
    formula = '<math display="block"><mi>N</mi><mo>=</mo><msub><mi>N</mi><mn>0</mn></msub><msup><mi>e</mi><mrow><mo>−</mo><mi>λ</mi><mi>t</mi></mrow></msup></math>'
    integral = '<math display="block"><msubsup><mo>∫</mo><msub><mi>N</mi><mn>0</mn></msub><mi>N</mi></msubsup><mfrac><mrow><mi mathvariant="normal">d</mi><mi>N′</mi></mrow><mi>N′</mi></mfrac><mo>=</mo><mo>−</mo><mi>λ</mi><msubsup><mo>∫</mo><mn>0</mn><mi>t</mi></msubsup><mi mathvariant="normal">d</mi><mi>t′</mi></math>'
    return {'schema_version': 1, 'course': '合成课程示例', 'unit': 'L01 · 指数衰减', 'kind': 'lesson',
            'scope': '仅用于验证笔记模块的合成反馈，不是真实课程材料或学生学习记录。', 'sources': sources,
            'items': [
                {'id': 'decay-model', 'kind': 'concept', 'title': '指数衰减模型 · Exponential decay',
                 'source': '合成教师反馈 L01 · 模型假设', 'source_refs': ['lessons/L01.md'],
                 'summary_html': '<p>每个尚未衰变的粒子具有恒定的单位时间衰变概率；样本的平均衰变速率与剩余粒子数成正比。</p>',
                 'detail_html': '<h3>为什么与剩余数量有关</h3><p>剩余粒子越多，同一小段时间内预计发生的衰变越多。这里讨论统计平均行为，假设粒子独立且衰变常数保持不变。</p><p>负号表示剩余数量减少，不表示衰变常数为负。</p>',
                 'recall': ['模型需要哪些假设？负号表示什么？']},
                {'id': 'decay-law', 'kind': 'derivation', 'title': '从变化率重建衰减规律',
                 'source': '合成教师反馈 L01 · 已展示推导', 'source_refs': ['lessons/L01.md'],
                 'summary_html': '<ol><li>从“变化率与剩余数量成正比”建立微分方程。</li><li>分离变量，将数量和时间放在两边。</li><li>用初始条件确定积分边界，再取指数。</li></ol>' + formula,
                 'detail_html': '<h3>起点与理由</h3><p>我们要求数量随时间的变化规律，所以从数量的变化率出发：</p><math display="block"><mfrac><mrow><mi mathvariant="normal">d</mi><mi>N</mi></mrow><mrow><mi mathvariant="normal">d</mi><mi>t</mi></mrow></mfrac><mo>=</mo><mo>−</mo><mi>λ</mi><mi>N</mi></math><h3>为什么分离变量</h3><p>将两边除以数量，使左边只含数量变量；这样才能分别积分。在数量为正的范围进行这一步。</p>' + integral + '<h3>从积分到结论</h3><p>倒数的积分给出自然对数；代入上下限后，数量之比的对数等于时间乘以负的衰变常数。两边取指数，得到：</p>' + formula + '<p>初始时刻数量等于初始值；随时间增加数量下降。该结论依赖恒定衰变常数。</p>',
                 'recall': ['从哪个物理关系开始？', '为什么要分离变量？初始条件在哪一步使用？']},
                {'id': 'decay-constant', 'kind': 'term', 'title': '衰变常数 · Decay constant',
                 'source': '合成教师反馈 L01 · 术语', 'source_refs': ['lessons/L01.md'],
                 'summary_html': '<p>衰变常数描述每个尚未衰变粒子的单位时间衰变概率，符号为 <math><mi>λ</mi></math>，单位为 <math><msup><mi mathvariant="normal">s</mi><mrow><mo>−</mo><mn>1</mn></mrow></msup></math>。</p>',
                 'detail_html': '<p>它是模型参数；衰变常数越大，数量平均下降越快。它与半衰期不同：一个是单位时间的概率参数，一个是数量减半所需的时间。</p><math display="block"><msub><mi>t</mi><mrow><mn>1</mn><mo>/</mo><mn>2</mn></mrow></msub><mo>=</mo><mfrac><mrow><mi mathvariant="normal">ln</mi><mn>2</mn></mrow><mi>λ</mi></mfrac></math>'},
                {'id': 'state-definition', 'kind': 'exam', 'title': 'State：简明陈述概念',
                 'source': '合成考试反馈 · 无真题依据；教师已讲概念', 'source_refs': ['exam/profile.md', 'lessons/L01.md'],
                 'exam_basis': 'reference', 'exam_reference': '依已讲定义编写，供表达练习',
                 'summary_html': '<blockquote>The decay constant is the probability per unit time that an undecayed particle decays.</blockquote>',
                 'detail_html': '<p>这是自拟参考表达。State要求简明陈述；若要求Explain，还需要根据题意说明理由。未据此认定该概念必考或声称这是官方评分原句。</p>'}
            ]}


def seed(root):
    for path, (module, body) in FEEDBACK.items():
        role = {'study-planner': 'main', 'course-study': 'main', 'exam-analysis': 'analyst', 'practice-builder': 'questions'}[module]
        notes.records.write_record(root, path, role, 'absent', body)


class NoteRenderingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)
        self.data = fixture()

    def test_offline_math_layers_and_source_versions(self):
        html = notes.render(self.data, self.base)
        self.assertIn('<mfrac>', html)
        self.assertIn('<msubsup>', html)
        self.assertEqual(html.count('<details class="explanation">'), 4)
        self.assertIn('feedback-versions', html)
        self.assertNotIn('src="http', html)
        self.assertNotIn('<link', html)
        self.assertIn('beforeprint', html)
        self.assertIn('afterprint', html)
        self.assertIn('自拟参考表达', html)

    def test_raw_math_cannot_hide_in_code_or_metadata(self):
        for field in ('summary_html', 'detail_html', 'title'):
            for raw in (r'<code>\frac{1}{2}</code>', r'\ket{x}', '$x^2$', 'x_{0}'):
                data = copy.deepcopy(self.data)
                data['items'][0][field] = raw
                with self.subTest(field=field, raw=raw), self.assertRaisesRegex(ValueError, 'LaTeX'):
                    notes.render(data, self.base)

    def test_external_loads_and_active_content_are_rejected(self):
        for raw in ('<script>fetch("https://example.com")</script>', '<img src="https://example.com/x.png" alt="x"/>', '<p onclick="x()">x</p>', '<iframe src="https://example.com"/>'):
            self.data['items'][0]['summary_html'] = raw
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                notes.render(self.data, self.base)

    def test_local_images_are_embedded(self):
        (self.base / 'tiny.png').write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jmZ8AAAAASUVORK5CYII='))
        self.data['items'][0]['summary_html'] += '<img src="tiny.png" alt="合成测试图"/>'
        self.assertIn('src="data:image/png;base64,', notes.render(self.data, self.base))

    def test_provenance_and_exam_basis_are_required(self):
        mutations = [lambda d: d['sources'][0].update(sha256='absent'),
                     lambda d: d['sources'][1].update(module='exam-analysis'),
                     lambda d: d['items'][0].update(source_refs=['unknown.md']),
                     lambda d: d['items'][3].update(exam_basis='mandatory'),
                     lambda d: d['items'][3].update(exam_basis='past-paper', source_refs=['lessons/L01.md']),
                     lambda d: d.update(mastery='mastered'),
                     lambda d: d['items'].append(copy.deepcopy(d['items'][0]))]
        for mutate in mutations:
            data = copy.deepcopy(self.data)
            mutate(data)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                notes.render(data, self.base)

    def test_chapter_links_remain_local(self):
        self.data['kind'] = 'chapter'
        self.data['lesson_links'] = [{'title': 'L01', 'path': 'lessons/L01.html'}]
        self.assertIn('href="lessons/L01.html"', notes.render(self.data, self.base))
        for path in ('../current.md', '/tmp/x.html', 'https://example.com/x.html'):
            self.data['lesson_links'][0]['path'] = path
            with self.assertRaises(ValueError):
                notes.render(self.data, self.base)


class NoteCliPathTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)
        self.draft = self.base / 'draft.json'
        self.draft.write_text(json.dumps(fixture()), encoding='utf-8')

    def snapshot(self):
        return self.draft.read_bytes(), self.draft.stat().st_mtime_ns

    def run_cli(self, source, *options):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--input', str(source), *map(str, options)],
                              text=True, capture_output=True)

    def assert_rejected_without_input_change(self, source, *options):
        before = self.snapshot()
        result = self.run_cli(source, *options)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('Output must not overwrite source records', result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_cli_rejects_same_input_output(self):
        self.assert_rejected_without_input_change(self.draft, '--output', self.draft)

    def test_cli_rejects_symbolic_path_aliases(self):
        alias = self.base / 'alias.json'
        alias.symlink_to(self.draft)
        with self.subTest(alias='input'):
            self.assert_rejected_without_input_change(alias, '--output', self.draft)
        with self.subTest(alias='output'):
            self.assert_rejected_without_input_change(self.draft, '--output', alias)
        self.assertTrue(alias.is_symlink())
        directory_alias = self.base / 'alias-directory'
        directory_alias.symlink_to(self.base, target_is_directory=True)
        with self.subTest(alias='parent directory'):
            self.assert_rejected_without_input_change(self.draft, '--output', directory_alias / self.draft.name)

    def test_cli_rejects_hard_link_alias(self):
        alias = self.base / 'hard-link.json'
        alias.hardlink_to(self.draft)
        before = alias.read_bytes(), alias.stat().st_mtime_ns
        self.assert_rejected_without_input_change(self.draft, '--output', alias)
        self.assertEqual((alias.read_bytes(), alias.stat().st_mtime_ns), before)
        self.assertTrue(self.draft.samefile(alias))

    def test_cli_rejects_case_alias_on_case_insensitive_filesystem(self):
        alias = self.base / 'Draft.json'
        if not alias.exists() or not self.draft.samefile(alias):
            self.skipTest('Case-insensitive filesystem required')
        self.assert_rejected_without_input_change(self.draft, '--output', alias)

    def test_cli_rejects_protected_output_alias_before_publication(self):
        root = self.base / 'records'
        target = root / 'notes/chapters/C01.html'
        target.parent.mkdir(parents=True)
        target.write_bytes(self.draft.read_bytes())
        self.draft = target
        before_files = set(root.rglob('*'))
        for source in (target, self.base / 'protected-draft.json'):
            if source != target:
                source.symlink_to(target)
            with self.subTest(source=source.name):
                self.assert_rejected_without_input_change(
                    source, '--root', root, '--path', 'notes/chapters/C01.html',
                    '--expected', notes.records.digest(target.read_bytes()))
        self.assertEqual(set(root.rglob('*')), before_files)

    def test_cli_renders_distinct_output_and_preserves_input(self):
        before = self.snapshot()
        destination = self.base / 'preview.html'
        result = self.run_cli(self.draft, '--output', destination)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(destination.read_text(encoding='utf-8').startswith('<!doctype html>'))
        self.assertEqual(self.snapshot(), before)


@unittest.skipIf(notes.records.fcntl is None, 'POSIX writing support required')
class NotePublicationTests(unittest.TestCase):
    def setUp(self):
        NoteRenderingTests.setUp(self)
        self.root = self.base / 'records'
        seed(self.root)
        self.relative = 'notes/lessons/L01.html'

    def publish(self, expected='absent'):
        return notes.publish(self.root, self.relative, expected, self.data, notes.render(self.data, self.base))

    def test_notes_role_isolated_and_cannot_recover_or_bundle(self):
        for role in ('main', 'aside', 'analyst', 'questions'):
            with self.subTest(role=role), self.assertRaises(ValueError):
                notes.records.write_record(self.root, self.relative, role, 'absent', 'x')
        for path in ('current.md', 'study-plan.md', 'lessons/x.md', 'exam/x.json', 'questions/x.json', 'practice/x.md', 'reviews/x.html', 'notes/x.pdf'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                notes.records.write_record(self.root, path, 'notes', 'absent', 'x')
        with self.assertRaises(ValueError):
            notes.records.write_bundle(self.root, 'notes', [])
        with self.assertRaises(ValueError):
            notes.records.recover_bundle(self.root, 'notes')

    def test_save_noop_backup_and_upstream_integrity(self):
        before = {p: ((self.root / p).read_bytes(), (self.root / p).stat().st_mtime_ns) for p in FEEDBACK}
        first = self.publish()
        target = self.root / self.relative
        mtime = target.stat().st_mtime_ns
        self.assertFalse(self.publish(first['sha256'])['changed'])
        self.assertEqual(target.stat().st_mtime_ns, mtime)
        previous = target.read_bytes()
        self.data['items'][0]['recall'].append('哪些条件变化时需要重新检查模型？')
        second = self.publish(first['sha256'])
        self.assertEqual((self.root / second['backup']).read_bytes(), previous)
        self.assertEqual(before, {p: ((self.root / p).read_bytes(), (self.root / p).stat().st_mtime_ns) for p in FEEDBACK})

    def test_source_change_or_manual_note_edit_stops_overwrite(self):
        first = self.publish()
        target = self.root / self.relative
        previous = target.read_bytes()
        (self.root / 'lessons/L01.md').write_text('Corrected upstream feedback')
        with self.assertRaisesRegex(ValueError, 'Stale feedback'):
            self.publish(first['sha256'])
        self.assertEqual(target.read_bytes(), previous)
        target.write_text('User annotation')
        with self.assertRaisesRegex(ValueError, 'Stale note'):
            self.publish(first['sha256'])
        self.assertEqual(target.read_text(), 'User annotation')

    def test_pending_publication_and_busy_lock_do_not_write_notes(self):
        with notes.records.course_lock(self.root):
            with self.assertRaisesRegex(ValueError, 'busy'):
                notes.publish(self.root, self.relative, 'absent', self.data, 'html', lock_timeout=0)
        (self.root / notes.records.PENDING).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            self.publish()
        self.assertFalse((self.root / 'notes').exists())

    def test_missing_feedback_or_new_root_cannot_create_course(self):
        (self.root / 'exam/profile.md').unlink()
        with self.assertRaisesRegex(ValueError, 'Stale feedback'):
            self.publish()
        other = self.base / 'unconfirmed'
        with self.assertRaisesRegex(ValueError, 'existing'):
            notes.publish(other, self.relative, 'absent', self.data, 'html')
        self.assertFalse(other.exists())

    def test_cli_checks_sources_and_chapter_relative_links(self):
        self.data['kind'] = 'chapter'
        self.data['lesson_links'] = [{'title': 'L01', 'path': 'lessons/L01.html'}]
        draft = self.base / 'draft.json'
        draft.write_text(json.dumps(self.data))
        command = [sys.executable, '-B', str(SCRIPT), '--input', str(draft), '--root', str(self.root), '--path', 'notes/chapters/C01.html', '--expected', 'absent']
        result = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('href="../lessons/L01.html"', (self.root / 'notes/chapters/C01.html').read_text())
        stale = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(stale.returncode, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
