"""Synthetic material intake/navigation regressions; no real course or learner data."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/study-planner/scripts/course_files.py'
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location('course_files', SCRIPT)
files = importlib.util.module_from_spec(spec)
spec.loader.exec_module(files)


@unittest.skipIf(files.records.fcntl is None, 'POSIX writing support required')
class CourseFilesTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.base = Path(folder.name).resolve()
        self.root = self.base / 'records'
        self.materials = self.base / 'materials'
        self.external = self.base / 'supplied-originals'
        self.external.mkdir()
        files.init_course(self.root, self.materials, 'SYNTHETIC-COURSE', [self.external])

    def manifest(self):
        return json.loads((self.root / 'materials.json').read_text())

    def version(self):
        return files.sha_file(self.root / 'materials.json')

    def write(self, relative, content=b'Synthetic source', external=False):
        path = (self.external if external else self.materials) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def item(self, path, category='lectures', **extra):
        return dict(path=str(path), sha256=files.sha_file(path), category=category,
                    chapters=[{'chapter': 'C01', 'locator': 'pp.1-3'}],
                    inspection='Synthetic fixture: read pp.1-3', **extra)

    def intake(self, path, category='lectures', **extra):
        return files.import_material(self.root, self.item(path, category, **extra), self.version())

    def targets(self):
        return {path: files.sha_file(self.root / path) if (self.root / path).exists() else 'absent'
                for path in files.INDEX_PATHS}

    def snapshot(self, root):
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*')
                if p.is_file() and p.name != '.course-records.lock'}

    def test_init_is_idempotent_creates_real_intake_categories_only(self):
        version = self.version()
        mtime = (self.root / 'materials.json').stat().st_mtime_ns
        result = files.init_course(self.root, self.materials, 'SYNTHETIC-COURSE', [self.external])
        self.assertFalse(result['changed'])
        self.assertEqual(self.version(), version)
        self.assertEqual((self.root / 'materials.json').stat().st_mtime_ns, mtime)
        self.assertEqual({p.name for p in self.materials.iterdir()}, {'inbox', *files.CATEGORIES})
        self.assertFalse((self.root / 'notes').exists())
        self.assertEqual(self.manifest()['entries'], [])
        self.assertEqual(result['inbox'], str(self.materials / 'inbox'))
        with self.assertRaises(ValueError):
            files.init_course(self.root, self.materials, 'DIFFERENT', [self.external])

    def test_scan_reports_new_and_duplicate_bytes_without_guessing_classification(self):
        first = self.write('inbox/lecture.pdf', b'Chapter A')
        second = self.write('inbox/copy.pdf', b'Chapter A')
        unknown = self.write('inbox/unusual.bin', b'Unknown kind')
        before = self.snapshot(self.materials), self.snapshot(self.root)
        scan = files.scan_course(self.root)
        self.assertEqual(len(scan['added']), 2)
        self.assertEqual(len(scan['duplicates']), 1)
        self.assertEqual({v['path'] for v in scan['files']}, {str(first), str(second), str(unknown)})
        self.assertFalse(any('category' in value for value in scan['files']))
        self.assertEqual((self.snapshot(self.materials), self.snapshot(self.root)), before)

    def test_scan_reports_modified_missing_and_moved_files(self):
        original = self.write('reading.pdf', b'Initial source', external=True)
        added = self.intake(original)
        canonical = Path(added['path'])
        canonical.write_bytes(b'Manual modification')
        scan = files.scan_course(self.root)
        self.assertEqual([e['path'] for e in scan['modified']], [str(canonical)])
        self.assertEqual(scan['affected_ids'], [added['id']])
        canonical.unlink()
        scan = files.scan_course(self.root)
        self.assertIn(str(canonical), {e['path'] for e in scan['missing']})
        moved = self.external / 'renamed.pdf'
        original.rename(moved)
        scan = files.scan_course(self.root)
        original_event = next(e for e in scan['moved'] if e['path'] == str(original))
        self.assertEqual(original_event['candidates'], [str(moved)])

    def test_external_originals_untouched_and_import_idempotent(self):
        source = self.write('supplied.pdf', b'Immutable original', external=True)
        before_bytes, before_mtime = source.read_bytes(), source.stat().st_mtime_ns
        first = self.intake(source)
        version, mtime = self.version(), (self.root / 'materials.json').stat().st_mtime_ns
        second = self.intake(source)
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(first['path'], second['path'])
        self.assertEqual(len(self.manifest()['entries']), 1)
        self.assertEqual(self.version(), version)
        self.assertEqual((self.root / 'materials.json').stat().st_mtime_ns, mtime)
        self.assertEqual(source.read_bytes(), before_bytes)
        self.assertEqual(source.stat().st_mtime_ns, before_mtime)
        self.assertTrue(second['source_preserved'])
        self.assertFalse(second['inbox_consumed'])

    def test_same_name_different_bytes_retains_both_versions(self):
        source = self.write('inbox/same.pdf', b'Version one')
        first = self.intake(source)
        source = self.write('inbox/same.pdf', b'Version two')
        second = self.intake(source, id=first['id'])
        self.assertEqual(first['id'], second['id'])
        self.assertNotEqual(first['path'], second['path'])
        self.assertEqual(Path(first['path']).read_bytes(), b'Version one')
        self.assertEqual(Path(second['path']).read_bytes(), b'Version two')
        entry = self.manifest()['entries'][0]
        self.assertEqual(entry['versions'], [{'path': first['path'], 'sha256': first['source_sha256']}])
        self.assertFalse(files.scan_course(self.root)['added'])

    def test_external_old_version_is_not_reported_as_modified(self):
        old_source = self.write('original/lecture.pdf', b'Old original', external=True)
        first = self.intake(old_source)
        new_source = self.write('replacement/lecture.pdf', b'New original', external=True)
        self.intake(new_source, id=first['id'])
        self.assertEqual(old_source.read_bytes(), b'Old original')
        self.assertEqual(new_source.read_bytes(), b'New original')
        self.assertFalse(files.scan_course(self.root)['modified'])

    def test_in_place_canonical_update_records_unavailable_old_bytes_honestly(self):
        first = self.intake(self.write('inbox/lecture.pdf', b'Initial bytes'))
        canonical = Path(first['path'])
        canonical.write_bytes(b'Edited canonical bytes')
        before = files.scan_course(self.root)
        self.assertEqual([e['path'] for e in before['modified']], [str(canonical)])
        result = self.intake(canonical, id=first['id'])
        entry = self.manifest()['entries'][0]
        self.assertEqual(result['path'], str(canonical))
        self.assertEqual(entry['versions'], [])
        self.assertEqual(entry['unavailable_versions'], [{'path': str(canonical),
                                                        'sha256': first['source_sha256']}])
        self.assertEqual(canonical.read_bytes(), b'Edited canonical bytes')
        self.assertFalse(files.scan_course(self.root)['modified'])
        self.intake(canonical, id=first['id'])
        self.assertEqual(self.manifest()['entries'][0]['unavailable_versions'], entry['unavailable_versions'])

    def test_inbox_consumed_only_after_copy_and_registry_success(self):
        source = self.write('inbox/source.pdf', b'Preserve on failure')
        registry_before = (self.root / 'materials.json').read_bytes()
        original = files.records.atomic_write
        def fail_registry(target, data):
            if target.name == 'materials.json':
                raise OSError('Synthetic registry failure')
            return original(target, data)
        with patch.object(files.records, 'atomic_write', fail_registry):
            with self.assertRaisesRegex(OSError, 'Synthetic registry failure'):
                self.intake(source)
        self.assertEqual(source.read_bytes(), b'Preserve on failure')
        self.assertEqual((self.root / 'materials.json').read_bytes(), registry_before)
        # A verified archive copy left by an interrupted registry write is reusable.
        result = self.intake(source)
        self.assertTrue(result['inbox_consumed'])
        self.assertFalse(source.exists())
        self.assertEqual(Path(result['path']).read_bytes(), b'Preserve on failure')

    def test_stale_registry_and_source_versions_reject_before_consuming(self):
        first = self.write('inbox/a.pdf', b'A')
        old_version = self.version()
        self.intake(first)
        second = self.write('inbox/b.pdf', b'B')
        before = self.snapshot(self.materials), self.snapshot(self.root)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            files.import_material(self.root, self.item(second), old_version)
        self.assertEqual((self.snapshot(self.materials), self.snapshot(self.root)), before)
        inspected = self.item(second)
        second.write_bytes(b'B edited after inspection')
        with self.assertRaisesRegex(ValueError, 'changed after inspection'):
            files.import_material(self.root, inspected, self.version())
        self.assertTrue(second.exists())
        self.assertFalse((self.materials / 'lectures/b.pdf').exists())

    def test_course_learning_records_are_unchanged_by_intake(self):
        records = {'current.md': b'Continue real lesson here', 'study-plan.md': b'Flexible plan',
                   'practice/P01.md': b'Unanswered', 'lessons/L01.md': b'Learner evidence',
                   'notes/C01.html': b'<p>Existing notes</p>', 'exam/profile.md': b'Prior analysis'}
        for relative, content in records.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.intake(self.write('inbox/new.txt', b'New supplementary reading'), 'supplements')
        files.scan_course(self.root)
        files.build_indexes(self.root, self.version(), self.targets())
        self.assertEqual({p: (self.root / p).read_bytes() for p in records}, records)

    def test_source_symlinks_and_declared_root_escape_rejected(self):
        outside = self.base / 'outside.pdf'
        outside.write_bytes(b'Outside declared sources')
        with self.assertRaisesRegex(ValueError, 'outside the declared'):
            self.intake(outside)
        alias = self.materials / 'inbox/alias.pdf'
        alias.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.intake(alias)
        alias_directory = self.materials / 'inbox/link'
        alias_directory.symlink_to(self.external, target_is_directory=True)
        actual = self.write('symlink-target.pdf', b'Source', external=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.intake(alias_directory / actual.name)
        scan = files.scan_course(self.root)
        self.assertEqual({e['path'] for e in scan['warnings']}, {str(alias), str(alias_directory)})
        self.assertNotIn(str(alias), {e['path'] for e in scan['files']})
        self.assertEqual(outside.read_bytes(), b'Outside declared sources')

    def test_scan_preserves_source_and_registry_bytes_mtimes_and_missing_sources(self):
        source = self.write('unclassified-source.dat', b'Unclassified raw source', external=True)
        self.intake(self.write('inbox/known.pdf', b'Known lecture'))
        paths = [source, self.root / 'materials.json', *self.materials.rglob('*.pdf')]
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
        files.scan_course(self.root)
        after = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
        self.assertEqual(after, before)
        source.unlink()
        self.external.rmdir()
        scan = files.scan_course(self.root)
        self.assertIn(str(self.external), {e['path'] for e in scan['warnings']})
        self.assertFalse(self.external.exists())

    def test_scan_of_uninitialized_root_does_not_create_records(self):
        missing_root = self.base / 'wrong-record-path'
        with self.assertRaises(ValueError):
            files.scan_course(missing_root)
        self.assertFalse(missing_root.exists())

    def test_unclassified_is_pending_and_chapter_locator_required(self):
        source = self.write('inbox/unknown.txt')
        item = self.item(source)
        item['chapters'] = [{'chapter': 'C01', 'locator': ''}]
        with self.assertRaisesRegex(ValueError, 'locator'):
            files.import_material(self.root, item, self.version())
        result = self.intake(source, 'unclassified')
        self.assertEqual(files.scan_course(self.root)['pending_classification'], [result['id']])

    def test_indexes_list_actual_outputs_and_hide_author_solutions(self):
        source = self.write('inbox/transcript.vtt', b'00:00:01.000 --> 00:00:04.000\nsynthetic transcript')
        self.intake(source, 'transcripts')
        outputs = {'notes/C01.html': '<p>Note</p>', 'questions/prompts/P01.md': 'Question only',
                   'questions/solutions/P01.md': 'Author answer', 'questions/legacy.md': 'Unknown mixed contents',
                   'practice/P01.md': 'Actual attempt', 'transcripts/L01.md': 'Uncertain term at 00:03'}
        for relative, content in outputs.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        result = files.build_indexes(self.root, self.version(), self.targets())
        self.assertEqual(result['index'], str(self.root / 'index.html'))
        html = (self.root / 'index.html').read_text()
        self.assertIn('notes/C01.html', html)
        self.assertIn('questions/prompts/P01.md', html)
        self.assertIn('practice/P01.md', html)
        self.assertIn('transcripts/L01.md', html)
        self.assertNotIn('questions/solutions/P01.md', html)
        self.assertNotIn('questions/legacy.md', html)
        self.assertNotIn('notes/C02.html', html)
        files.build_indexes(self.root, self.version(), self.targets(), show_solutions=True)
        self.assertIn('questions/solutions/P01.md', (self.root / 'index.html').read_text())

    def test_analysis_brief_visible_without_enumerating_internal_reports(self):
        files.build_indexes(self.root, self.version(), self.targets())
        initial = (self.root / 'index.html').read_text()
        self.assertIn('题目与考试分析简报', initial)
        self.assertNotIn('exam/brief.md', initial)
        payload = {'exam/items.json': '{"papers": []}',
                   'exam/summary.json': '{"synthetic": true}',
                   'exam/profile.md': 'Synthetic internal full capability chain',
                   'exam/brief.md': 'Synthetic brief: analyzed scope is empty; no conclusions.',
                   'exam/internal/audit.md': 'Internal audit detail'}
        files.records.write_bundle(self.root, 'analyst', [
            {'path': path, 'expected': 'absent', 'content': content}
            for path, content in payload.items()])
        before = {path: (self.root / path).read_bytes() for path in payload}
        files.build_indexes(self.root, self.version(), self.targets())
        for name in ('index.md', 'index.html'):
            content = (self.root / name).read_text()
            self.assertIn('exam/brief.md', content)
            for internal in ('exam/profile.md', 'exam/items.json', 'exam/summary.json', 'exam/internal/audit.md'):
                self.assertNotIn(internal, content)
        self.assertEqual(before, {path: (self.root / path).read_bytes() for path in payload})

    def test_index_stale_guards_prevent_partial_publication(self):
        self.intake(self.write('inbox/new.pdf'))
        targets = self.targets()
        (self.root / 'index.md').write_text('Manual user navigation')
        with self.assertRaisesRegex(ValueError, 'Stale'):
            files.build_indexes(self.root, self.version(), targets)
        self.assertEqual((self.root / 'index.md').read_text(), 'Manual user navigation')
        self.assertFalse((self.root / 'index.html').exists())
        self.assertFalse((self.root / 'materials-index.md').exists())
        with self.assertRaisesRegex(ValueError, 'changed'):
            files.build_indexes(self.root, '0' * 64, self.targets())

    def test_html_escapes_labels_details_and_urls(self):
        source = self.write('inbox/a & <tag> [x] "quote".pdf')
        item = self.item(source)
        item['inspection'] = '<script>bad</script> & details'
        files.import_material(self.root, item, self.version())
        files.build_indexes(self.root, self.version(), self.targets())
        html = (self.root / 'index.html').read_text()
        self.assertIn('&lt;tag&gt;', html)
        self.assertIn('&lt;script&gt;bad&lt;/script&gt; &amp; details', html)
        self.assertIn('%3Ctag%3E', html)
        self.assertIn('%22quote%22', html)
        self.assertNotIn('<script>', html)
        self.assertNotIn('href="../materials/lectures/a &', html)

    def test_output_symlink_rejects_without_publishing_indexes(self):
        outside = self.base / 'outside-note.html'
        outside.write_text('<p>Outside note</p>')
        (self.root / 'notes').mkdir()
        (self.root / 'notes/alias.html').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            files.build_indexes(self.root, self.version(), self.targets())
        self.assertFalse((self.root / 'index.html').exists())
        self.assertEqual(outside.read_text(), '<p>Outside note</p>')


if __name__ == '__main__':
    unittest.main()
