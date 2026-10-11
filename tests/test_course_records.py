"""Synthetic record persistence regressions; no course or learner fixtures."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/study-planner/scripts/course_records.py'
spec = importlib.util.spec_from_file_location('records', SCRIPT)
records = importlib.util.module_from_spec(spec)
spec.loader.exec_module(records)


@unittest.skipIf(records.fcntl is None, 'POSIX writing support required')
class RecordTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name) / 'records'

    def updates(self):
        return [{'path': 'current.md', 'expected': 'absent', 'content': 'Continue after P1'},
                {'path': 'practice/p1.md', 'expected': 'absent', 'content': 'Synthetic attempt P1'},
                {'path': 'study-plan.md', 'expected': 'absent', 'content': 'Next: P2'}]

    def crash(self):
        # Real process exit after the first public record, before the checkpoint.
        code = """
import importlib.util, json, os
from pathlib import Path
spec = importlib.util.spec_from_file_location('records', SCRIPT)
records = importlib.util.module_from_spec(spec); spec.loader.exec_module(records)
original = records.atomic_write
def interrupted(target, data):
    original(target, data)
    if target.name == 'p1.md': os._exit(77)
records.atomic_write = interrupted
records.write_bundle(ROOT, 'main', UPDATES)
"""
        code = 'SCRIPT=' + repr(str(SCRIPT)) + '\nROOT=' + repr(str(self.root)) + '\nUPDATES=' + repr(self.updates()) + '\n' + code
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 77, result.stderr)
        self.assertTrue((self.root / records.PENDING).exists())
        self.assertFalse((self.root / 'current.md').exists())

    def test_noop_backup_and_manual_edit_protection(self):
        initial = records.write_record(self.root, 'current.md', 'main', 'absent', 'A')
        mtime = (self.root / 'current.md').stat().st_mtime_ns
        self.assertFalse(records.write_record(self.root, 'current.md', 'main', initial['sha256'], 'A')['changed'])
        self.assertEqual((self.root / 'current.md').stat().st_mtime_ns, mtime)
        updated = records.write_record(self.root, 'current.md', 'main', initial['sha256'], 'B')
        self.assertEqual((self.root / updated['backup']).read_text(), 'A')
        (self.root / 'current.md').write_text('manual')
        with self.assertRaisesRegex(ValueError, 'Stale'):
            records.write_record(self.root, 'current.md', 'main', updated['sha256'], 'C')
        self.assertEqual((self.root / 'current.md').read_text(), 'manual')

    def test_roles_paths_json_and_aside_append_only(self):
        for role, path in [('aside', 'current.md'), ('questions', 'exam/q.json'),
                           ('analyst', 'study-plan.md'), ('main', '../current.md'), ('main', 'reviews/a.png')]:
            with self.subTest(role=role, path=path), self.assertRaises(ValueError):
                records.write_record(self.root, path, role, 'absent', '{}')
        with self.assertRaises(ValueError):
            records.write_record(self.root, 'exam/q.json', 'analyst', 'absent', '{broken')
        self.assertFalse(self.root.exists())
        note = records.add_note(self.root, 'aside', 'Temporary question')
        with self.assertRaisesRegex(ValueError, 'append-only'):
            records.write_record(self.root, note['path'], 'aside', note['sha256'], 'edited')
        (self.root / 'current.md').symlink_to(self.root.parent / 'outside.md')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            records.write_record(self.root, 'current.md', 'main', 'absent', 'x')

    def test_lock_timeout_and_parallel_asides(self):
        with records.course_lock(self.root):
            with self.assertRaisesRegex(ValueError, 'busy'):
                records.write_record(self.root, 'current.md', 'main', 'absent', 'x', lock_timeout=0)
        self.assertFalse((self.root / 'current.md').exists())
        with ThreadPoolExecutor(max_workers=4) as workers:
            notes = list(workers.map(lambda i: records.add_note(self.root, 'aside', 'Note ' + str(i)), range(8)))
        self.assertEqual(len({note['id'] for note in notes}), 8)
        self.assertEqual(len(list((self.root / 'side-notes').glob('*.md'))), 8)

    def test_bundle_preflight_rejects_stale_and_bad_inputs_without_partial_records(self):
        updates = self.updates()
        updates[-1]['expected'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Stale bundle'):
            records.write_bundle(self.root, 'main', updates)
        self.assertFalse((self.root / 'practice').exists())
        self.assertFalse((self.root / records.PENDING).exists())
        for updates in (self.updates() + [self.updates()[0]],
                        [{'path': 'reviews/r.json', 'expected': 'absent', 'content': '{bad'}],
                        [{'path': 'exam/r.md', 'expected': 'absent', 'content': 'x'}]):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                records.write_bundle(self.root, 'main', updates)
        for role in ('aside', 'analyst', 'questions'):
            with self.assertRaisesRegex(ValueError, 'Only main'):
                records.write_bundle(self.root, role, self.updates())

    def test_bundle_success_and_noop_keep_record_mtimes(self):
        self.assertTrue(records.write_bundle(self.root, 'main', self.updates())['changed'])
        updates, mtimes = [], {}
        for item in self.updates():
            current = records.read_record(self.root, item['path'])
            updates.append(dict(item, expected=current['sha256']))
            mtimes[item['path']] = (self.root / item['path']).stat().st_mtime_ns
        self.assertFalse(records.write_bundle(self.root, 'main', updates)['changed'])
        self.assertFalse((self.root / records.PENDING).exists())
        self.assertEqual(mtimes, {path: (self.root / path).stat().st_mtime_ns for path in mtimes})

    def test_real_interruption_blocks_reads_and_writes_then_recovers_once(self):
        self.crash()
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            records.read_record(self.root, 'current.md')
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            records.add_note(self.root, 'aside', 'unsafe overlap')
        self.assertTrue(records.recover_bundle(self.root, 'main')['recovered'])
        self.assertFalse(records.recover_bundle(self.root, 'main')['recovered'])
        for item in self.updates():
            self.assertEqual(records.read_record(self.root, item['path'])['content'], item['content'])
        self.assertEqual(len(list((self.root / 'practice').glob('*.md'))), 1)

    def test_recovery_preserves_manual_edit_and_abort_retains_canceled_content(self):
        self.crash()
        (self.root / 'practice/p1.md').write_text('Manual correction')
        with self.assertRaisesRegex(ValueError, 'manual edit'):
            records.recover_bundle(self.root, 'main')
        self.assertFalse((self.root / 'study-plan.md').exists())
        result = records.recover_bundle(self.root, 'main', decision='abort')
        self.assertEqual(result['preserved_manual_edits'], ['practice/p1.md'])
        self.assertEqual(records.read_record(self.root, 'practice/p1.md')['content'], 'Manual correction')
        self.assertFalse((self.root / 'current.md').exists())
        self.assertTrue(any('Synthetic attempt P1' in file.read_text() for file in (self.root / '.history').iterdir()))

    def test_abort_restores_old_files_and_removes_only_known_new_content(self):
        records.write_record(self.root, 'current.md', 'main', 'absent', 'Old checkpoint')
        updates = self.updates()
        updates[0]['expected'] = records.read_record(self.root, 'current.md')['sha256']
        original = records.atomic_write
        def fail(target, data):
            original(target, data)
            if target.name == 'current.md':
                raise OSError('Synthetic failure after checkpoint write')
        with patch.object(records, 'atomic_write', fail), self.assertRaises(OSError):
            records.write_bundle(self.root, 'main', updates)
        records.recover_bundle(self.root, 'main', decision='abort')
        self.assertEqual(records.read_record(self.root, 'current.md')['content'], 'Old checkpoint')
        self.assertFalse((self.root / 'practice/p1.md').exists())
        self.assertFalse((self.root / 'study-plan.md').exists())

    def test_symlink_journal_and_tampered_previous_content_rejected(self):
        self.root.mkdir()
        (self.root / records.PENDING).symlink_to(self.root.parent / 'elsewhere')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            records.read_record(self.root, 'current.md')
        (self.root / records.PENDING).unlink()
        self.crash()
        journal = self.root / records.PENDING
        body = json.loads(journal.read_text())
        body['updates'][0]['previous'] = 'Contradicts absent'
        journal.write_text(json.dumps(body))
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            records.recover_bundle(self.root, 'main')
        self.assertFalse((self.root / 'current.md').exists())


class ReadOnlyPlatformTests(unittest.TestCase):
    def test_read_without_fcntl_and_clear_unsupported_write(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(records, 'fcntl', None):
            root = Path(folder) / 'records'
            self.assertEqual(records.read_record(root, 'current.md')['sha256'], 'absent')
            with self.assertRaisesRegex(ValueError, 'macOS/Linux'):
                records.write_record(root, 'current.md', 'main', 'absent', 'x')
            self.assertFalse(root.exists())


if __name__ == '__main__':
    unittest.main()
