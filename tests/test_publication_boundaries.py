"""Synthetic CLI regressions for preview preservation and note draft freshness."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
# Standalone unittest invocation must use the same fixture imports as discovery.
sys.path.insert(0, str(ROOT / 'tests'))
from test_study_notes import FEEDBACK, notes, seed
from test_study_notes_v3 import fixture_v3
from test_exam_statistics import paper

SCRIPTS = {
    'notes': ROOT / 'skills/study-notes/scripts/render_notes.py',
    'review': ROOT / 'skills/study-planner/scripts/render_review.py',
    'exam': ROOT / 'skills/exam-analysis/scripts/summarize_exam.py',
}
SUFFIXES = {'notes': '.html', 'review': '.html', 'exam': '.json'}
FORMAL_PATHS = {'notes': 'notes/chapters/C01.html',
                'review': 'reviews/U01.html', 'exam': 'exam/summary.json'}


def input_data(kind, marker='ORIGINAL-BODY'):
    if kind == 'notes':
        data = fixture_v3()
        data['intro_html'] = '<p>' + marker + '</p>'
        return data
    if kind == 'review':
        return {'course': 'Synthetic', 'unit': marker, 'items': [{
            'id': 'synthetic-q1', 'title': 'Synthetic practice', 'source': 'Test fixture',
            'question_html': '<p>State the result.</p>',
            'solution_html': '<p>Synthetic shown solution.</p>',
            'personal_review': 'Synthetic fixture only.',
            'evidence': {'assistance': 'hint', 'outcome': 'partial'}}]}
    return {'papers': [dict(paper(), id=marker)]}


def saved_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def file_state(path):
    return path.read_bytes(), path.stat().st_mtime_ns


def tree_state(base):
    """Observe user contents, file mtimes, links and newly created directories."""
    state = {}
    for path in base.rglob('*'):
        relative = str(path.relative_to(base))
        if path.is_symlink():
            state[relative] = ('symlink', str(path.readlink()), path.lstat().st_mtime_ns)
        elif path.is_dir():
            state[relative] = ('directory',)
        else:
            state[relative] = ('file', *file_state(path))
    return state


class PreviewPreservationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)

    def case(self, kind):
        base = self.base / kind
        base.mkdir()
        source = base / 'draft.json'
        saved_json(source, input_data(kind))
        return base, source

    def run_cli(self, kind, source, destination):
        return subprocess.run([sys.executable, '-B', str(SCRIPTS[kind]),
                               '--input', str(source), '--output', str(destination)],
                              text=True, capture_output=True, timeout=15)

    def assert_preserved_on_rejection(self, kind, base, source, destination):
        before = tree_state(base)
        result = self.run_cli(kind, source, destination)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(tree_state(base), before)

    def test_existing_preview_file_is_preserved_at_each_entry_point(self):
        for kind, suffix in SUFFIXES.items():
            with self.subTest(kind=kind):
                base, source = self.case(kind)
                target = base / ('existing' + suffix)
                target.write_bytes(b'Existing user document; do not replace.')
                self.assert_preserved_on_rejection(kind, base, source, target)

    def test_existing_hard_link_is_preserved_at_each_entry_point(self):
        for kind, suffix in SUFFIXES.items():
            with self.subTest(kind=kind):
                base, source = self.case(kind)
                victim = base / 'user-document.txt'
                victim.write_bytes(b'Hard-linked user content must survive.')
                target = base / ('linked-preview' + suffix)
                target.hardlink_to(victim)
                self.assert_preserved_on_rejection(kind, base, source, target)
                self.assertTrue(target.samefile(victim))

    def test_existing_symbolic_link_is_preserved_at_each_entry_point(self):
        for kind, suffix in SUFFIXES.items():
            with self.subTest(kind=kind):
                base, source = self.case(kind)
                victim = base / 'user-document.txt'
                victim.write_bytes(b'Symbolic-linked user content must survive.')
                target = base / ('linked-preview' + suffix)
                target.symlink_to(victim)
                self.assert_preserved_on_rejection(kind, base, source, target)
                self.assertTrue(target.is_symlink())

    def test_dangling_symbolic_link_is_not_replaced(self):
        for kind, suffix in SUFFIXES.items():
            with self.subTest(kind=kind):
                base, source = self.case(kind)
                target = base / ('dangling-preview' + suffix)
                target.symlink_to(base / 'absent-user-document')
                self.assert_preserved_on_rejection(kind, base, source, target)
                self.assertTrue(target.is_symlink())

    def test_wrong_suffix_does_not_create_parent_or_replace_existing_file(self):
        for kind in SUFFIXES:
            with self.subTest(kind=kind):
                base, source = self.case(kind)
                absent = base / 'uncreated' / 'subdirectory' / 'preview.pdf'
                self.assert_preserved_on_rejection(kind, base, source, absent)
                self.assertFalse(absent.parent.exists())
                existing = base / 'user-document.md'
                existing.write_bytes(b'This is not a preview output.')
                self.assert_preserved_on_rejection(kind, base, source, existing)

    def test_rival_created_after_preview_check_is_never_overwritten(self):
        for kind, suffix in SUFFIXES.items():
            with self.subTest(kind=kind):
                base, source = self.case(kind)
                target = base / ('rival-output' + suffix)
                before_source = file_state(source)
                instrumentation = self.base / (kind + '-instrumentation')
                instrumentation.mkdir()
                signal = instrumentation / 'ready'
                resume = instrumentation / 'resume'
                wrapper = instrumentation / 'wait_before_publish.py'
                # Pause at the OS publication call, after the product has checked
                # destination absence. The competing writer then creates it.
                wrapper.write_text(
                    'import importlib.util, os, time\n'
                    'from pathlib import Path\n'
                    'spec = importlib.util.spec_from_file_location("preview_under_test", ' + repr(str(SCRIPTS[kind])) + ')\n'
                    'module = importlib.util.module_from_spec(spec)\n'
                    'spec.loader.exec_module(module)\n'
                    'original = os.link\n'
                    'def announce(source, destination, *args, **kwargs):\n'
                    '    Path(' + repr(str(signal)) + ').write_text("ready")\n'
                    '    deadline = time.monotonic() + 10\n'
                    '    while not Path(' + repr(str(resume)) + ').exists():\n'
                    '        if time.monotonic() > deadline:\n'
                    '            raise RuntimeError("Test writer did not resume publication")\n'
                    '        time.sleep(.01)\n'
                    '    return original(source, destination, *args, **kwargs)\n'
                    'os.link = announce\n'
                    'module.main()\n', encoding='utf-8')
                process = subprocess.Popen(
                    [sys.executable, '-B', str(wrapper), '--input', str(source), '--output', str(target)],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    deadline = time.monotonic() + 5
                    while not signal.exists() and process.poll() is None and time.monotonic() < deadline:
                        time.sleep(.01)
                    if not signal.exists():
                        self.fail('Preview did not reach the real atomic publication call')
                    with target.open('xb') as stream:
                        stream.write(b'Rival writer content must survive unchanged.')
                    before_target = file_state(target)
                    resume.write_text('continue', encoding='utf-8')
                    stdout, stderr = process.communicate(timeout=15)
                    self.assertEqual(process.returncode, 2, stdout + stderr)
                    self.assertNotIn('Traceback', stderr)
                    self.assertEqual(file_state(target), before_target)
                    self.assertEqual(file_state(source), before_source)
                    self.assertEqual(set(base.iterdir()), {source, target})
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()

    def test_fresh_preview_works_and_preserves_the_source(self):
        for kind, suffix in SUFFIXES.items():
            with self.subTest(kind=kind):
                base, source = self.case(kind)
                before = file_state(source)
                target = base / 'new-preview' / ('output' + suffix)
                result = self.run_cli(kind, source, target)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(file_state(source), before)
                if suffix == '.html':
                    self.assertTrue(target.read_text(encoding='utf-8').startswith('<!doctype html>'))
                else:
                    self.assertEqual(len(json.loads(target.read_text(encoding='utf-8'))['papers']), 1)
                self.assertFalse((base / '.history').exists())
                self.assertFalse((base / '.course-records.lock').exists())


@unittest.skipIf(notes.records.fcntl is None, 'POSIX writing support required')
class ProtectedPublicationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)

    def command(self, kind, source, root, expected):
        command = [sys.executable, '-B', str(SCRIPTS[kind]), '--input', str(source),
                   '--root', str(root), '--path', FORMAL_PATHS[kind], '--expected', expected]
        if kind == 'notes':
            command += ['--lock-timeout', '10']
        return command

    def test_protected_updates_still_use_sha_and_back_up_previous_output(self):
        for kind in SUFFIXES:
            with self.subTest(kind=kind):
                root = self.base / kind / 'course'
                root.mkdir(parents=True)
                if kind == 'notes':
                    seed(root)
                    source = root / 'notes/chapters/C01.json'
                else:
                    source = self.base / kind / 'draft.json'
                saved_json(source, input_data(kind))
                before = file_state(source)
                first = subprocess.run(self.command(kind, source, root, 'absent'),
                                       text=True, capture_output=True, timeout=15)
                self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
                self.assertEqual(file_state(source), before)
                receipt = json.loads(first.stdout)
                target = root / FORMAL_PATHS[kind]
                previous = target.read_bytes()
                saved_json(source, input_data(kind, 'UPDATED-BODY'))
                before = file_state(source)
                second = subprocess.run(self.command(kind, source, root, receipt['sha256']),
                                        text=True, capture_output=True, timeout=15)
                self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
                updated = json.loads(second.stdout)
                self.assertTrue(updated['changed'])
                self.assertEqual((root / updated['backup']).read_bytes(), previous)
                self.assertIn('UPDATED-BODY', target.read_text(encoding='utf-8'))
                self.assertEqual(file_state(source), before)
                state = tree_state(root)
                stale = subprocess.run(self.command(kind, source, root, receipt['sha256']),
                                       text=True, capture_output=True, timeout=15)
                self.assertEqual(stale.returncode, 2, stale.stdout + stale.stderr)
                self.assertEqual(tree_state(root), state)

    def test_note_input_changed_while_publication_waits_for_lock_is_rejected(self):
        root = self.base / 'course'
        seed(root)
        source = root / 'notes/chapters/C01.json'
        old_data = input_data('notes', 'OLD-BODY')
        saved_json(source, old_data)
        initial = subprocess.run(self.command('notes', source, root, 'absent'),
                                 text=True, capture_output=True, timeout=15)
        self.assertEqual(initial.returncode, 0, initial.stdout + initial.stderr)
        target = root / FORMAL_PATHS['notes']
        receipt = json.loads(initial.stdout)
        before_target = file_state(target)
        before_sources = {name: file_state(root / name) for name in FEEDBACK}
        before_history = tree_state(root / '.history') if (root / '.history').exists() else {}
        signal = self.base / 'render-complete'
        wrapper = self.base / 'wait_at_publication.py'
        # This wrapper only announces entry to the real course lock after rendering.
        # Both the publisher and lock implementation remain the production code.
        wrapper.write_text(
            'import contextlib, importlib.util\n'
            'from pathlib import Path\n'
            'spec = importlib.util.spec_from_file_location("publication_under_test", ' + repr(str(SCRIPTS['notes'])) + ')\n'
            'module = importlib.util.module_from_spec(spec)\n'
            'spec.loader.exec_module(module)\n'
            'original = module.records.course_lock\n'
            '@contextlib.contextmanager\n'
            'def announce(root, timeout=2.0):\n'
            '    Path(' + repr(str(signal)) + ').write_text("rendered")\n'
            '    with original(root, timeout):\n'
            '        yield\n'
            'module.records.course_lock = announce\n'
            'module.main()\n', encoding='utf-8')
        command = self.command('notes', source, root, receipt['sha256'])
        command[2] = str(wrapper)
        process = None
        try:
            with notes.records.course_lock(root):
                process = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                deadline = time.monotonic() + 5
                while not signal.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(.01)
                if not signal.exists():
                    self.fail('Publisher did not reach the real course lock after rendering')
                self.assertIsNone(process.poll(), 'Publisher should wait for the held course lock')
                changed = copy.deepcopy(old_data)
                changed['intro_html'] = '<p>NEW-BODY</p>'
                # The fixture writer owns the held lock; update the saved JSON only.
                notes.records.atomic_write(source, json.dumps(changed, ensure_ascii=False).encode('utf-8'))
                changed_source = file_state(source)
                after_fixture_update = tree_state(root)
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 2, stdout + stderr)
            self.assertNotIn('Traceback', stderr)
            self.assertRegex(stderr.lower(), r'(input|draft).*(chang|stale|version)|stale.*(input|draft)')
            self.assertEqual(file_state(target), before_target)
            self.assertEqual(file_state(source), changed_source)
            self.assertEqual(tree_state(root), after_fixture_update)
            self.assertEqual({name: file_state(root / name) for name in FEEDBACK}, before_sources)
            after_history = tree_state(root / '.history') if (root / '.history').exists() else {}
            self.assertEqual(after_history, before_history)
            self.assertIn('OLD-BODY', target.read_text(encoding='utf-8'))
            self.assertNotIn('NEW-BODY', target.read_text(encoding='utf-8'))
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.communicate()


if __name__ == '__main__':
    unittest.main(verbosity=2)
