"""Normal price prose and numeric raw math must remain distinguishable."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


shared = load('shared_math_text_tests', 'skills/study-planner/scripts/math_text.py')
checker = load('price_checker_tests', 'skills/course-study/scripts/check_math.py')


class DollarClassificationTests(unittest.TestCase):
    def test_legitimate_prices_and_escaped_dollars_are_not_raw_math(self):
        examples = ('成本从 $5 升到 $10。', 'cost $5 and $10', '$20.',
                    'The cost is $20 per person.', 'The cost is $5 a day.',
                    'It costs $10 a month.', '$5 a day and $10 a month.',
                    '$5', '$1,250.50 each.',
                    '$5–$10', '$5 to $10; $15 for delivery.',
                    r'Escaped \$5 and \$10.', r'Pay $5 and \$10.',
                    '$5 (including tax).')
        for source in examples:
            with self.subTest(source=source):
                self.assertFalse(shared.has_math_dollars(source))
                self.assertEqual(checker.check(source), [])

    def test_raw_numeric_math_is_not_mistaken_for_currency(self):
        examples = ('$2x+1', '$2 x+1', '$2^2', '$2=3', '$2/3', '$2x+1$',
                    '$20$', '$2 x$', '$2 kg$', '$2 + 1', '$2 (x+1)', '$2 [x+1]', r'$2 \alpha$',
                    '$2 sin x$', '$2 a+1', '$2 a$', '$2 a day$', '$x$', '$$x$$', '$', r'Even escapes \\$x',
                    'cost $5 and $10; formula $2x+1', 'Pay $5, then use $x$.')
        for source in examples:
            with self.subTest(source=source):
                self.assertTrue(shared.has_math_dollars(source))
        for source in ('$2x+1', '$2 x+1', '$2^2', '$2=3', '$2/3', '$2 a+1'):
            with self.subTest(unclosed=source):
                self.assertTrue(any(issue['severity'] == 'error' for issue in checker.check(source)))

    def test_checker_keeps_valid_delimited_math_and_multiple_prices(self):
        for source in ('$20$', '$2 x$', '$2 kg$', '$2x+1$', '$2 x+1$',
                       '$20 per person$', '$2 a$', '$2 a day$', '$2 and 3$', '$2,3$', '$2.5, 3.6$', '$2.$',
                       '$2 (x+1)$', '$2,3$ and $4,5$',
                       '$2,3$ and cost $4.', '$2 and 3$; price $4.', '$2 and x$; price $4.',
                       'Pay $5 and $10, then use $x+1$.',
                       'The cost is $5; formula $2 x$.'):
            with self.subTest(source=source):
                self.assertEqual(checker.check(source), [])

    def test_classifier_uses_the_requested_position_and_ignores_escaped_dollars(self):
        source = r'Pay $5, then use $2x+1$ and escape \$10.'
        positions = [position for position, char in enumerate(source) if char == '$']
        self.assertEqual([shared.is_currency_dollar(source, position) for position in positions],
                         [True, False, False, False])
        for position in (-1, 0, len(source)):
            self.assertFalse(shared.is_currency_dollar(source, position))

    def test_ambiguous_unit_text_prefers_an_explicit_math_closer(self):
        # A bare amount plus an ordinary word can be currency prose. Adding an
        # explicit closing delimiter makes it math; no full TeX parse is claimed.
        self.assertFalse(shared.has_math_dollars('$2 kg'))
        self.assertTrue(shared.has_math_dollars('$2 kg$'))
        self.assertEqual(checker.check('$2 kg$'), [])

    def test_checker_keeps_recorded_suite_invocations_as_command_prose(self):
        for name in ('study-planner', 'course-study', 'exam-analysis', 'practice-builder', 'study-notes'):
            self.assertEqual(checker.check('$' + name + ' Continue this course.'), [])


if __name__ == '__main__':
    unittest.main()
