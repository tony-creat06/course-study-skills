"""Synthetic source, denominator, style and mark-allocation regressions."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/exam-analysis/scripts/summarize_exam.py'
spec = importlib.util.spec_from_file_location('stats', SCRIPT)
stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stats)


def paper():
    return {'id': 'synthetic-real', 'kind': 'real', 'exam_year': 2026,
            'source': 'Synthetic paper; no real course material', 'scope_complete': False,
            'all_questions_required': True, 'questions': [
                {'number': 1, 'primary_topic': 'A', 'parts': [
                    {'label': 'a', 'source_page': 2, 'marks': 4, 'topics': ['A', 'B'],
                     'abilities': ['derive', 'interpret'], 'styles': ['linked calculation'], 'command_verbs': ['show']},
                    {'label': 'b', 'source_page': 2, 'marks': 6, 'topics': ['A'],
                     'abilities': ['sketch', 'interpret'], 'styles': ['graphical explanation'], 'command_verbs': ['sketch', 'explain']}]},
                {'number': 2, 'primary_topic': None, 'parts': [
                    {'label': 'whole', 'source_page': None, 'marks': None, 'topics': []}]}]}


class ExamStatisticsTests(unittest.TestCase):
    def analyze(self, item=None):
        return stats.summarize({'papers': [item or paper()]})['papers'][0]['analysis']

    def test_overlap_and_unknowns_keep_denominators(self):
        result = self.analyze()
        self.assertEqual(result['question_count'], 2)
        self.assertEqual(sum(row['question_count'] for row in result['primary_topics']), 2)
        self.assertEqual(result['known_available_marks'], 10)
        self.assertEqual(result['unknown_mark_parts'], 1)
        self.assertEqual(sum(row['marks'] for row in result['mark_groups']), 10)
        self.assertIsNone(result['candidate_required_marks'])
        self.assertIn({'topics': ['A', 'B'], 'marks': 4}, result['mark_groups'])

    def test_style_ability_and_verb_weights_are_joint_source_groups(self):
        dimensions = self.analyze()['assessment_dimensions']
        for dimension in dimensions.values():
            self.assertEqual(sum(row['marks'] for row in dimension['joint_mark_groups']), 10)
            self.assertEqual(sum(row['percent_of_known_available_marks'] for row in dimension['joint_mark_groups']), 100)
            self.assertEqual(dimension['unclassified_parts'], 1)
        sketch = next(row for row in dimensions['abilities']['joint_mark_groups'] if 'sketch' in row['labels'])
        self.assertEqual(sketch['labels'], ['interpret', 'sketch'])
        self.assertEqual(sketch['marks'], 6)
        self.assertEqual(sketch['percent_of_known_available_marks'], 60)
        self.assertEqual(sketch['parts'], [{'question': '1', 'part': 'b', 'source_page': 2}])
        # Repeated interpretation within one big question counts once.
        coverage = {row['topic']: row['question_count'] for row in dimensions['abilities']['question_coverage']}
        self.assertEqual(coverage['interpret'], 1)

    def test_legacy_fields_leave_style_unclassified(self):
        item = paper()
        for question in item['questions']:
            for part in question['parts']:
                for key in ('abilities', 'styles', 'command_verbs'):
                    part.pop(key, None)
        result = self.analyze(item)
        for dimension in result['assessment_dimensions'].values():
            self.assertEqual(dimension['unclassified_parts'], 3)
            self.assertEqual(dimension['question_coverage'], [])
            self.assertEqual(dimension['joint_mark_groups'][0]['labels'], [])

    def test_complete_total_and_optional_paper_are_not_confused(self):
        item = paper()
        item['expected_available_marks'] = 100
        self.analyze(item)  # Partial subset does not assert a full-paper total.
        item['scope_complete'] = True
        item['questions'].pop()
        with self.assertRaisesRegex(ValueError, 'total disagrees'):
            self.analyze(item)
        item['expected_available_marks'] = 10
        self.assertEqual(self.analyze(item)['candidate_required_marks'], 10)
        item['all_questions_required'] = False
        self.assertIsNone(self.analyze(item)['candidate_required_marks'])

    def test_duplicate_papers_questions_and_trimmed_parts_rejected(self):
        item = paper()
        with self.assertRaisesRegex(ValueError, 'Duplicate paper'):
            stats.summarize({'papers': [item, copy.deepcopy(item)]})
        item['questions'].append(copy.deepcopy(item['questions'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate question'):
            self.analyze(item)
        item = paper()
        duplicate = copy.deepcopy(item['questions'][0]['parts'][0])
        duplicate['label'] = ' a '
        item['questions'][0]['parts'].append(duplicate)
        with self.assertRaisesRegex(ValueError, 'unique'):
            self.analyze(item)

    def test_bad_marks_and_labels_are_rejected(self):
        for marks in (-1, True, float('inf'), '6'):
            item = paper()
            item['questions'][0]['parts'][0]['marks'] = marks
            with self.subTest(marks=marks), self.assertRaises(ValueError):
                self.analyze(item)
        for labels in ('sketch', [None], [''], ['未分类']):
            item = paper()
            item['questions'][0]['parts'][0]['styles'] = labels
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                self.analyze(item)

    def test_mock_practice_and_real_are_separate_even_same_year(self):
        items = [dict(paper(), id=kind, kind=kind) for kind in ('real', 'mock', 'practice')]
        result = stats.summarize({'papers': items})
        self.assertEqual({group['kind'] for group in result['year_groups']}, {'real', 'mock', 'practice'})
        self.assertEqual([group['question_count'] for group in result['year_groups']], [2, 2, 2])

    def test_cli_summary_keeps_role_and_stale_write_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / 'input.json'
            source.write_text(json.dumps({'papers': [paper()]}))
            command = [sys.executable, '-B', str(SCRIPT), '--input', str(source), '--root', str(base / 'records'),
                       '--path', 'exam/summary.json', '--expected', 'absent']
            first = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            target = base / 'records/exam/summary.json'
            target.write_text('{"manual":true}')
            stale = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(stale.returncode, 2)
            self.assertEqual(target.read_text(), '{"manual":true}')
            command[command.index('exam/summary.json')] = 'reviews/wrong.json'
            wrong_role = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(wrong_role.returncode, 2)
            self.assertFalse((base / 'records/reviews').exists())


class ExamCliPathTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)
        self.source = self.base / 'draft.json'
        self.source.write_text(json.dumps({'papers': [paper()]}), encoding='utf-8')

    def run_cli(self, destination):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--input', str(self.source),
                               '--output', str(destination)], text=True, capture_output=True)

    def assert_alias_rejected(self, destination):
        before = self.source.read_bytes(), self.source.stat().st_mtime_ns
        alias_before = destination.read_bytes(), destination.stat().st_mtime_ns
        result = self.run_cli(destination)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('Output must not overwrite', result.stderr)
        self.assertEqual((self.source.read_bytes(), self.source.stat().st_mtime_ns), before)
        self.assertEqual((destination.read_bytes(), destination.stat().st_mtime_ns), alias_before)
        self.assertTrue(self.source.samefile(destination))

    def test_cli_rejects_hard_link_alias(self):
        alias = self.base / 'hard-link.json'
        alias.hardlink_to(self.source)
        self.assert_alias_rejected(alias)

    def test_cli_rejects_case_alias_on_case_insensitive_filesystem(self):
        alias = self.base / 'Draft.json'
        if not alias.exists() or not self.source.samefile(alias):
            self.skipTest('Case-insensitive filesystem required')
        self.assert_alias_rejected(alias)

    def test_cli_renders_distinct_output_and_preserves_input(self):
        before = self.source.read_bytes(), self.source.stat().st_mtime_ns
        destination = self.base / 'summary.json'
        result = self.run_cli(destination)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(destination.read_text(encoding='utf-8'))['papers']), 1)
        self.assertEqual((self.source.read_bytes(), self.source.stat().st_mtime_ns), before)


if __name__ == '__main__':
    unittest.main()
