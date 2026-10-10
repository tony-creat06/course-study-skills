"""Synthetic regression checks for review evidence and mathematical delivery."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


review = load('review', 'skills/study-planner/scripts/render_review.py')
math = load('math_check', 'skills/course-study/scripts/check_math.py')


class ReviewEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.item = {'id': 'synthetic-q1', 'title': 'Synthetic practice', 'source': 'Test fixture',
                     'question_html': '<p>Compute <math><mn>2</mn><mo>+</mo><mn>3</mn></math>.</p>',
                     'solution_html': '<p>The sum is <math><mn>5</mn></math>.</p>',
                     'personal_review': 'Synthetic observation, not a real student record.'}

    def render(self, evidence):
        self.item['evidence'] = evidence
        return review.render({'course': 'Synthetic', 'unit': 'Regression', 'items': [self.item]}, ROOT)

    def test_hint_does_not_imply_completion(self):
        self.item['personal_review'] = '获得提示后仍未完成。'
        html = self.render({'assistance': 'hint', 'outcome': 'partial'})
        self.assertIn('部分完成', html)
        self.assertIn('本次使用提示', html)
        self.assertNotIn('使用提示后完成', html)

    def test_hint_and_incorrect_answer_remain_distinct(self):
        html = self.render({'assistance': 'hint', 'outcome': 'incorrect'})
        self.assertIn('作答有误', html)
        self.assertNotIn('正确完成', html)

    def test_shown_solution_without_attempt_is_readable(self):
        html = self.render({'assistance': 'solution', 'outcome': 'not_attempted'})
        self.assertIn('未独立尝试', html)
        self.assertIn('本次已展示解析', html)

    def test_future_question_is_not_a_completed_review(self):
        for help_used in ('none', 'hint', 'unknown'):
            with self.subTest(help_used=help_used), self.assertRaisesRegex(ValueError, 'unattempted'):
                self.render({'assistance': help_used, 'outcome': 'not_attempted'})

    def test_correct_reproduction_is_not_labelled_independent_mastery(self):
        html = self.render({'assistance': 'none', 'outcome': 'correct', 'reproduction': True})
        self.assertIn('正确完成', html)
        self.assertIn('已见解法后的再现', html)
        self.assertNotIn('独立完成且正确', html)
        self.assertNotIn('已掌握', html)

    def test_delayed_observation_is_not_mastery(self):
        html = self.render({'assistance': 'none', 'outcome': 'correct', 'reproduction': False, 'delayed': True})
        self.assertIn('隔时回访', html)
        self.assertNotIn('已掌握', html)

    def test_mixed_parts_keep_detail(self):
        self.item['personal_review'] = 'a无提示正确；b获得提示但未完成。'
        html = self.render({'assistance': 'mixed', 'outcome': 'mixed'})
        self.assertIn(self.item['personal_review'], html)
        self.assertIn('各小问结果不同', html)
        self.item['personal_review'] = ''
        with self.assertRaisesRegex(ValueError, 'per-part'):
            self.render({'assistance': 'mixed', 'outcome': 'mixed'})

    def test_unknown_help_does_not_become_independent(self):
        html = self.render({'assistance': 'unknown', 'outcome': 'correct'})
        self.assertIn('帮助条件未知', html)
        self.assertNotIn('独立完成且正确', html)

    def test_invalid_or_ambiguous_versions_are_rejected(self):
        for evidence in ({'assistance': 'none'}, {'assistance': [], 'outcome': 'correct'},
                         {'assistance': 'none', 'outcome': 'mastered'},
                         {'assistance': 'none', 'outcome': 'correct', 'delayed': 'true'},
                         {'assistance': 'none', 'outcome': 'correct', 'help': 'hint'},
                         {'assistance': 'solution', 'outcome': 'not_attempted', 'reproduction': True}):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                self.render(evidence)
        self.item['attempt'] = 'independent_correct'
        with self.assertRaisesRegex(ValueError, 'not both'):
            self.render({'assistance': 'hint', 'outcome': 'partial'})

    def test_legacy_hint_does_not_assert_an_outcome(self):
        self.item['attempt'] = 'hinted'
        self.item['personal_review'] = '获得提示后仍未完成。'
        html = review.render({'course': 'Synthetic', 'unit': 'Legacy', 'items': [self.item]}, ROOT)
        self.assertIn('本题使用过提示（结果见复盘）', html)
        self.assertNotIn('使用提示后完成', html)

    def test_other_legacy_records_still_render(self):
        for status in ('independent_correct', 'independent_incorrect', 'partial', 'shown_solution'):
            with self.subTest(status=status):
                self.item['attempt'] = status
                self.assertIn('<mfrac>', review.render_fragment('<math><mfrac><mn>1</mn><mn>2</mn></mfrac></math>', ROOT))
                self.assertIn('完整解析', review.render({'course': 'Synthetic', 'unit': 'Legacy', 'items': [self.item]}, ROOT))

    def test_duplicate_question_is_not_silently_added(self):
        self.item['evidence'] = {'assistance': 'none', 'outcome': 'partial'}
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            review.render({'course': 'Synthetic', 'unit': 'Unit', 'items': [self.item, copy.deepcopy(self.item)]}, ROOT)

    def test_cli_keeps_shared_version_protection(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            self.item['evidence'] = {'assistance': 'hint', 'outcome': 'partial'}
            source = base / 'fixture.json'
            source.write_text(json.dumps({'course': 'Synthetic', 'unit': 'Unit', 'items': [self.item]}))
            script = ROOT / 'skills/study-planner/scripts/render_review.py'
            command = [sys.executable, '-B', str(script), '--input', str(source), '--root', str(base / 'records'),
                       '--path', 'reviews/unit.html', '--expected', 'absent']
            first = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            destination = base / 'records/reviews/unit.html'
            destination.write_text('Manual annotation must survive')
            stale = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(stale.returncode, 2)
            self.assertEqual(destination.read_text(), 'Manual annotation must survive')


class MathematicalDeliveryTests(unittest.TestCase):
    def test_saved_baseline_command_typo_is_found(self):
        issues = math.check(r'The real amplitude is $A_{mathrm{real}}$.')
        self.assertTrue(any(x['kind'] == 'missing-backslash' for x in issues))
        self.assertEqual(math.check(r'The real amplitude is $A_{\mathrm{real}}$.'), [])

    def test_commands_in_plain_parentheses_need_inspection(self):
        issues = math.check(r'Frequency (\omega), wavefunction (\psi).')
        self.assertEqual(len(issues), 2)
        self.assertTrue(all(x['severity'] == 'warning' for x in issues))

    def test_valid_inline_display_and_escaped_delimiters(self):
        examples = [r'$\psi=Ae^{i(kx-\omega t)}$', r'\(\frac{1}{2}\)',
                    r'\[\partial_x(XT)=T\partial_xX\]', '$$\nx^{2}+y^{2}=1\n$$', r'$\{x\}$']
        for example in examples:
            with self.subTest(example=example):
                self.assertEqual(math.check(example), [])

    def test_unclosed_delimiters_and_braces_are_reported(self):
        for example in (r'$\psi', r'\(x', r'\[x\)', r'$x^{2$'):
            with self.subTest(example=example):
                self.assertTrue(any(x['severity'] == 'error' for x in math.check(example)))

    def test_code_and_prose_are_not_rewritten_or_flagged_as_math(self):
        for example in ('`A_{mathrm{real}}`', '```tex\n$\\psi\n```\nPlain text.',
                        '~~~python\n\\partial x\n~~~', r'Price is \$20.', 'Price is $20.', 'f(x) and a matrix.'):
            with self.subTest(example=example):
                self.assertEqual(math.check(example), [])

    def test_line_numbers_survive_code_masking(self):
        issues = math.check('```tex\n$bad\n```\n$A_{mathrm{real}}$')
        self.assertEqual(issues[0]['line'], 4)

    def test_recorded_skill_requests_do_not_open_math(self):
        for name in ('study-planner', 'course-study', 'exam-analysis', 'practice-builder'):
            source = '$' + name + ' Continue studying.\n' + r'\(x^2\)'
            with self.subTest(name=name):
                self.assertEqual(math.check(source), [])
        issues = math.check('$study-planner Continue.\n' + r'$x-y')
        self.assertEqual(issues[0]['line'], 2)
        self.assertEqual(issues[0]['kind'], 'delimiter')

    def test_cli_is_read_only_and_returns_actionable_result(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'draft.md'
            path.write_text(r'$A_{mathrm{real}}$')
            before = (path.read_bytes(), path.stat().st_mtime_ns)
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'skills/course-study/scripts/check_math.py'), str(path)],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
            self.assertEqual(json.loads(result.stdout)['files'][0]['issues'][0]['kind'], 'missing-backslash')


if __name__ == '__main__':
    unittest.main(verbosity=2)
