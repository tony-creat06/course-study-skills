"""Synthetic move/recovery regressions; no live courses or installed Skill edits."""
import errno
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/study-planner/scripts/course_files.py'
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location('move_course_files', SCRIPT)
files = importlib.util.module_from_spec(spec)
spec.loader.exec_module(files)


@unittest.skipIf(files.records.fcntl is None, 'POSIX writing support required')
class CourseMovesTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.base = Path(folder.name).resolve()
        self.root = self.base / 'records'
        self.materials = self.base / 'materials'
        self.external = self.base / 'supplied'
        self.external.mkdir()
        files.init_course(self.root, self.materials, 'SYNTHETIC-MOVES', [self.external])

    def source(self, relative='lecture.pdf', content=b'Synthetic lecture', inbox=False):
        path = (self.materials / 'inbox' if inbox else self.external) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def version(self):
        return files.sha_file(self.root / 'materials.json')

    def manifest(self):
        return json.loads((self.root / 'materials.json').read_text())

    def item(self, path, category='lectures', **extra):
        return dict(path=str(path), sha256=files.sha_file(path), category=category,
                    chapters=[{'chapter': 'C01', 'locator': 'pp.1-2'}],
                    inspection='Synthetic fixture read pp.1-2', **extra)

    def intake(self, path, category='lectures', mode='move', **extra):
        return files.import_material(self.root, self.item(path, category, **extra),
                                     self.version(), mode=mode)

    def crash_after(self, stage, source, category='lectures', **extra):
        """Use real process exit after a public move stage, bypassing Python cleanup."""
        code = '\n'.join([
            'import os, sys',
            'sys.path.insert(0, ' + repr(str(SCRIPT.parent)) + ')',
            'import course_files as files',
            'moves = files.course_moves',
            'original = getattr(moves, ' + repr(stage) + ')',
            'def interrupted(*args, **kwargs):',
            '    result = original(*args, **kwargs)',
            '    os._exit(77)',
            'setattr(moves, ' + repr(stage) + ', interrupted)',
            'files.import_material(' + repr(str(self.root)) + ', ' + repr(self.item(source, category, **extra)) +
            ', ' + repr(self.version()) + ')',
        ])
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 77, result.stderr)
        self.assertTrue((self.root / files.MOVE_PENDING).exists())

    def test_default_external_and_inbox_materials_are_moved_after_verification(self):
        for inbox in (False, True):
            with self.subTest(inbox=inbox):
                source = self.source('inbox.pdf' if inbox else 'external.pdf', b'Input ' + bytes([inbox]), inbox)
                original_bytes = source.read_bytes()
                result = files.import_material(self.root, self.item(source), self.version())
                target = Path(result['path'])
                self.assertFalse(source.exists())
                self.assertEqual(target.read_bytes(), original_bytes)
                self.assertEqual(target.parent, self.materials / 'lectures')
                self.assertFalse((self.root / files.MOVE_PENDING).exists())
        scan = files.scan_course(self.root)
        self.assertFalse(scan['missing'])
        self.assertFalse(scan['added'])
        self.assertFalse(scan['duplicates'])

    def test_explicit_copy_preserves_external_and_inbox_sources(self):
        for inbox in (False, True):
            with self.subTest(inbox=inbox):
                source = self.source('copy-inbox.pdf' if inbox else 'copy-external.pdf',
                                     b'Copy ' + bytes([inbox]), inbox)
                before = source.read_bytes(), source.stat().st_mtime_ns
                result = self.intake(source, mode='copy')
                self.assertEqual((source.read_bytes(), source.stat().st_mtime_ns), before)
                self.assertEqual(Path(result['path']).read_bytes(), before[0])
                self.assertTrue(result['source_preserved'])
                self.assertFalse(result['inbox_consumed'])

    def test_canonical_reclassification_relocates_bytes_without_duplicate_version(self):
        first = self.intake(self.source())
        initial = Path(first['path'])
        second = self.intake(initial, 'revision', id=first['id'])
        target = Path(second['path'])
        self.assertFalse(initial.exists())
        self.assertEqual(target.parent, self.materials / 'revision')
        self.assertEqual(target.read_bytes(), b'Synthetic lecture')
        entry = self.manifest()['entries'][0]
        self.assertEqual(entry['id'], first['id'])
        self.assertEqual(entry.get('versions', []), [])
        self.assertFalse(files.scan_course(self.root)['duplicates'])
        version = self.version()
        self.intake(target, 'revision', id=first['id'])
        self.assertEqual(self.version(), version)
        self.assertEqual(list(self.materials.rglob('*.pdf')), [target])

    def test_legacy_identical_retained_category_copy_is_removed_without_new_version(self):
        first = self.intake(self.source())
        legacy = self.materials / 'revision/old-copy.pdf'
        legacy.write_bytes(Path(first['path']).read_bytes())
        data = self.manifest()
        data['entries'][0]['versions'] = [{'path': str(legacy), 'sha256': first['source_sha256']}]
        (self.root / 'materials.json').write_text(json.dumps(data))
        result = self.intake(Path(first['path']), id=first['id'])
        self.assertFalse(legacy.exists())
        self.assertTrue(Path(result['path']).exists())
        self.assertEqual(self.manifest()['entries'][0]['versions'], [])

    def test_new_bytes_keep_old_canonical_version_but_move_new_source(self):
        first = self.intake(self.source(content=b'Original revision'))
        replacement = self.source(content=b'Replacement revision')
        second = self.intake(replacement, id=first['id'])
        self.assertFalse(replacement.exists())
        self.assertNotEqual(first['path'], second['path'])
        self.assertEqual(Path(first['path']).read_bytes(), b'Original revision')
        self.assertEqual(Path(second['path']).read_bytes(), b'Replacement revision')
        self.assertEqual(self.manifest()['entries'][0]['versions'],
                         [{'path': first['path'], 'sha256': first['source_sha256']}])
        self.assertFalse(files.scan_course(self.root)['missing'])

    def test_same_name_collision_retains_unrelated_bytes_without_overwrite(self):
        first_source = self.source('first/same.pdf', b'First distinct source')
        second_source = self.source('second/same.pdf', b'Second distinct source')
        first = self.intake(first_source)
        second = self.intake(second_source)
        self.assertNotEqual(first['id'], second['id'])
        self.assertNotEqual(first['path'], second['path'])
        self.assertEqual(Path(first['path']).read_bytes(), b'First distinct source')
        self.assertEqual(Path(second['path']).read_bytes(), b'Second distinct source')
        self.assertFalse(first_source.exists())
        self.assertFalse(second_source.exists())
        self.assertEqual(len(self.manifest()['entries']), 2)

    def test_duplicate_source_is_consumed_without_an_extra_canonical_file(self):
        first = self.intake(self.source('first.pdf'))
        duplicate = self.source('duplicate.pdf')
        second = self.intake(duplicate)
        self.assertFalse(duplicate.exists())
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(first['path'], second['path'])
        self.assertEqual(len(self.manifest()['entries']), 1)
        self.assertEqual(list(self.materials.rglob('*.pdf')), [Path(first['path'])])

    def test_cross_filesystem_link_failure_falls_back_to_verified_move(self):
        source = self.source()
        original_link = files.course_moves.os.link
        def cross_device_source_link(src, dst, *args, **kwargs):
            if Path(src) == source:
                raise OSError(errno.EXDEV, 'Synthetic cross-device link')
            return original_link(src, dst, *args, **kwargs)
        with patch.object(files.course_moves.os, 'link', cross_device_source_link):
            result = self.intake(source)
        self.assertFalse(source.exists())
        self.assertEqual(Path(result['path']).read_bytes(), b'Synthetic lecture')
        self.assertFalse((self.root / files.MOVE_PENDING).exists())

    def test_stale_registry_or_inspected_source_does_not_move_any_bytes(self):
        first = self.source('first.pdf', b'First')
        stale = self.version()
        self.intake(first)
        source = self.source('second.pdf', b'Second')
        item = self.item(source)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            files.import_material(self.root, item, stale)
        self.assertTrue(source.exists())
        self.assertFalse((self.materials / 'lectures/second.pdf').exists())
        source.write_bytes(b'Changed after inspection')
        with self.assertRaises(ValueError):
            files.import_material(self.root, item, self.version())
        self.assertEqual(source.read_bytes(), b'Changed after inspection')
        self.assertFalse((self.root / files.MOVE_PENDING).exists())

    def test_real_interruption_after_publish_blocks_consumers_then_finish_moves_source(self):
        source = self.source()
        self.crash_after('publish_target', source)
        self.assertTrue(source.exists())
        for operation in (lambda: files.registry(self.root), lambda: files.scan_course(self.root)):
            with self.assertRaises(ValueError):
                operation()
        files.recover_moves(self.root, 'finish')
        self.assertFalse(source.exists())
        entry = self.manifest()['entries'][0]
        self.assertEqual(Path(entry['path']).read_bytes(), b'Synthetic lecture')
        self.assertFalse((self.root / files.MOVE_PENDING).exists())
        self.assertFalse(files.scan_course(self.root)['missing'])

    def test_real_interruption_after_source_removal_can_abort_and_restore_bytes(self):
        source = self.source()
        before = (self.root / 'materials.json').read_bytes()
        self.crash_after('remove_source', source)
        self.assertFalse(source.exists())
        files.recover_moves(self.root, 'abort')
        self.assertEqual(source.read_bytes(), b'Synthetic lecture')
        self.assertEqual((self.root / 'materials.json').read_bytes(), before)
        self.assertFalse(list((self.materials / 'lectures').glob('*.pdf')))
        self.assertFalse((self.root / files.MOVE_PENDING).exists())

    def test_recovery_never_deletes_source_edited_after_interruption(self):
        source = self.source()
        self.crash_after('commit_registry', source)
        source.write_bytes(b'Human edit after interruption')
        with self.assertRaises(ValueError):
            files.recover_moves(self.root, 'finish')
        self.assertEqual(source.read_bytes(), b'Human edit after interruption')
        self.assertTrue((self.root / files.MOVE_PENDING).exists())

    def test_recovery_never_overwrites_changed_target(self):
        source = self.source()
        self.crash_after('publish_target', source)
        target = self.materials / 'lectures/lecture.pdf'
        target.unlink()  # User replacement has an independent inode.
        target.write_bytes(b'Human edit in archive')
        with self.assertRaises(ValueError):
            files.recover_moves(self.root, 'finish')
        self.assertEqual(source.read_bytes(), b'Synthetic lecture')
        self.assertEqual(target.read_bytes(), b'Human edit in archive')
        self.assertTrue((self.root / files.MOVE_PENDING).exists())


if __name__ == '__main__':
    unittest.main()
