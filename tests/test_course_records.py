"""Synthetic record persistence regressions; no course or learner fixtures."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
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

    def exam_updates(self, revision=1):
        return [{'path': 'exam/items.json', 'expected': 'absent', 'content': json.dumps({'revision': revision, 'marks': 12})},
                {'path': 'exam/summary.json', 'expected': 'absent', 'content': json.dumps({'revision': revision, 'known_marks': 12})},
                {'path': 'exam/profile.md', 'expected': 'absent', 'content': 'Revision ' + str(revision)}]

    def crash(self, role='main', updates=None, stop='p1.md'):
        # Real process exit after the first public record, before the checkpoint.
        code = """
import importlib.util, json, os
from pathlib import Path
spec = importlib.util.spec_from_file_location('records', SCRIPT)
records = importlib.util.module_from_spec(spec); spec.loader.exec_module(records)
original = records.atomic_write
def interrupted(target, data):
    original(target, data)
    if target.name == STOP: os._exit(77)
records.atomic_write = interrupted
records.write_bundle(ROOT, ROLE, UPDATES)
"""
        code = ('SCRIPT=' + repr(str(SCRIPT)) + '\nROOT=' + repr(str(self.root)) +
                '\nUPDATES=' + repr(self.updates() if updates is None else updates) +
                '\nROLE=' + repr(role) + '\nSTOP=' + repr(stop) + '\n' + code)
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 77, result.stderr)
        self.assertTrue((self.root / records.PENDING).exists())
        self.assertFalse((self.root / 'current.md').exists())

    def test_damaged_journal_cli_preserves_state_and_names_recovery_file(self):
        records.write_record(self.root, 'current.md', 'main', 'absent', 'Keep this checkpoint')
        pending = self.root / records.PENDING
        for body in (b'', b'{broken', b'[]', b'null', b'\xff'):
            with self.subTest(body=body):
                pending.write_bytes(body)
                before = (pending.read_bytes(), pending.stat().st_mtime_ns)
                for command in (['read', '--path', 'current.md'], ['recover', '--role', 'main']):
                    result = subprocess.run([sys.executable, '-B', str(SCRIPT), *command, '--root', str(self.root)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2)
                    self.assertNotIn('Traceback', result.stderr)
                    if command[0] == 'recover':
                        self.assertIn(str(pending), result.stderr)
                        self.assertIn('preserve', result.stderr)
                    self.assertEqual((pending.read_bytes(), pending.stat().st_mtime_ns), before)
                    self.assertEqual((self.root / 'current.md').read_text(), 'Keep this checkpoint')
                    self.assertFalse((self.root / '.history').exists())

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
        for role in ('aside', 'questions'):
            with self.assertRaisesRegex(ValueError, 'Only main'):
                records.write_bundle(self.root, role, self.updates())

    def test_analyst_batch_and_role_preflight(self):
        with self.assertRaisesRegex(ValueError, 'Role cannot'):
            records.write_bundle(self.root, 'analyst', self.exam_updates() + self.updates())
        self.assertFalse(self.root.exists())
        records.write_bundle(self.root, 'analyst', self.exam_updates())
        result = records.read_records(self.root, [e['path'] for e in self.exam_updates()])
        self.assertEqual([r['content'] for r in result['records']], [e['content'] for e in self.exam_updates()])
        self.assertFalse((self.root / 'current.md').exists())

    def test_interrupted_analyst_batch_blocks_snapshot_and_allows_owner_or_main_recovery(self):
        for owner in ('analyst', 'main'):
            with self.subTest(owner=owner):
                self.root = self.root / owner
                self.crash('analyst', self.exam_updates(), 'items.json')
                with self.assertRaisesRegex(ValueError, 'Incomplete'):
                    records.read_records(self.root, ['exam/items.json', 'exam/profile.md'])
                records.recover_bundle(self.root, owner)
                self.assertEqual([r['content'] for r in records.read_records(self.root, [e['path'] for e in self.exam_updates()])['records']],
                                 [e['content'] for e in self.exam_updates()])

    def test_analyst_cannot_recover_main_and_legacy_journal_remains_recoverable(self):
        self.crash()
        with self.assertRaisesRegex(ValueError, 'cannot recover'):
            records.recover_bundle(self.root, 'analyst')
        path = self.root / records.PENDING
        journal = json.loads(path.read_text())
        journal.pop('role')
        journal['version'] = 1
        path.write_text(json.dumps(journal))
        records.recover_bundle(self.root, 'main')
        self.assertEqual(records.read_record(self.root, 'current.md')['content'], self.updates()[0]['content'])

    def test_snapshot_waits_for_whole_analyst_batch(self):
        records.write_bundle(self.root, 'analyst', self.exam_updates())
        paths = [e['path'] for e in self.exam_updates()]
        old = records.read_records(self.root, paths)['records']
        updates = [dict(e, expected=r['sha256']) for e, r in zip(self.exam_updates(2), old)]
        entered, release = threading.Event(), threading.Event()
        original = records.atomic_write
        def paused(target, data):
            original(target, data)
            if target == self.root.resolve() / 'exam/items.json':
                entered.set()
                if not release.wait(5):
                    raise OSError('Test writer was not released')
        with ThreadPoolExecutor(max_workers=2) as workers, patch.object(records, 'atomic_write', paused):
            writer = workers.submit(records.write_bundle, self.root, 'analyst', updates)
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaisesRegex(ValueError, 'busy'):
                    records.read_records(self.root, paths, lock_timeout=0)
                reader = workers.submit(records.read_records, self.root, paths)
            finally:
                release.set()
            writer.result()
            self.assertEqual([r['content'] for r in reader.result()['records']], [e['content'] for e in updates])

    def test_analyst_stale_batch_and_manual_edit_abort(self):
        records.write_bundle(self.root, 'analyst', self.exam_updates())
        paths = [e['path'] for e in self.exam_updates()]
        old = records.read_records(self.root, paths)['records']
        updates = [dict(e, expected=r['sha256']) for e, r in zip(self.exam_updates(2), old)]
        stale = [dict(e) for e in updates]
        stale[-1]['expected'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Stale bundle'):
            records.write_bundle(self.root, 'analyst', stale)
        self.assertEqual(records.read_records(self.root, paths)['records'], old)
        self.crash('analyst', updates, 'items.json')
        (self.root / 'exam/items.json').write_text('{"manual": true}')
        with self.assertRaisesRegex(ValueError, 'manual edit'):
            records.recover_bundle(self.root, 'analyst')
        result = records.recover_bundle(self.root, 'analyst', 'abort')
        self.assertEqual(result['preserved_manual_edits'], ['exam/items.json'])
        self.assertEqual(records.read_record(self.root, 'exam/summary.json'), old[1])
        self.assertEqual(records.read_record(self.root, 'exam/profile.md'), old[2])

    def test_read_set_cli_missing_root_and_duplicate_paths(self):
        with self.assertRaisesRegex(ValueError, 'already exist'):
            records.read_records(self.root, ['current.md'])
        self.assertFalse(self.root.exists())
        self.root.mkdir()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            records.read_records(self.root, ['exam/a.md', 'exam/./a.md'])
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), 'read-set', '--root', str(self.root),
                                 '--paths', 'exam/items.json', 'exam/profile.md'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([r['sha256'] for r in json.loads(result.stdout)['records']], ['absent', 'absent'])

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
            root.mkdir()
            with self.assertRaisesRegex(ValueError, 'macOS/Linux'):
                records.read_records(root, ['current.md'])


if __name__ == '__main__':
    unittest.main()
