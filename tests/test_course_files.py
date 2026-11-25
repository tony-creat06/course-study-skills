"""Synthetic material intake/navigation regressions; no real course or learner data."""
import importlib.util
import json
import subprocess
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

    def intake(self, path, category='lectures', mode='move', **extra):
        return files.import_material(self.root, self.item(path, category, **extra), self.version(), mode=mode)

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

    def test_registry_validation_names_malformed_fields_in_cli_without_mutation(self):
        self.intake(self.write('registered.pdf', b'Registered source', external=True), mode='copy')
        valid = self.manifest()
        entry = valid['entries'][0]
        entry['versions'] = [{'path': entry['path'], 'sha256': entry['sha256']}]
        malformed = [
            ('registry', [], None), ('registry', None, None),
            ('schema_version', 2, ('schema_version',)),
            ('course_id', [], ('course_id',)),
            ('materials_root', None, ('materials_root',)),
            ('source_roots', None, ('source_roots',)),
            ('source_roots[0]', {}, ('source_roots', 0)),
            ('entries', None, ('entries',)),
            ('entries[0]', None, ('entries', 0)),
            ('entries[0].id', [], ('entries', 0, 'id')),
            ('entries[0].path', None, ('entries', 0, 'path')),
            ('entries[0].sha256', 'not-a-digest', ('entries', 0, 'sha256')),
            ('entries[0].category', 'unknown', ('entries', 0, 'category')),
            ('entries[0].inspection', [], ('entries', 0, 'inspection')),
            ('entries[0].chapters', None, ('entries', 0, 'chapters')),
            ('entries[0].chapters[0]', [], ('entries', 0, 'chapters', 0)),
            ('entries[0].chapters[0].chapter', None, ('entries', 0, 'chapters', 0, 'chapter')),
            ('entries[0].chapters[0].locator', {}, ('entries', 0, 'chapters', 0, 'locator')),
            ('entries[0].origin_paths', {}, ('entries', 0, 'origin_paths')),
            ('entries[0].origin_paths[0]', None, ('entries', 0, 'origin_paths', 0)),
            ('entries[0].origin_sha256', [], ('entries', 0, 'origin_sha256')),
            ('entries[0].origin_sha256', {'bad': None}, ('entries', 0, 'origin_sha256')),
            ('entries[0].versions', None, ('entries', 0, 'versions')),
            ('entries[0].versions[0]', [], ('entries', 0, 'versions', 0)),
            ('entries[0].versions[0].path', None, ('entries', 0, 'versions', 0, 'path')),
            ('entries[0].versions[0].sha256', None, ('entries', 0, 'versions', 0, 'sha256')),
            ('entries[0].unavailable_versions', None, ('entries', 0, 'unavailable_versions')),
            ('entries[0].received_sources', None, ('entries', 0, 'received_sources')),
        ]

        def unchanged_files():
            return {str(p.relative_to(self.base)): (p.read_bytes(), p.stat().st_mtime_ns)
                    for p in self.base.rglob('*') if p.is_file() and p.name != '.course-records.lock'}

        for field, replacement, route in malformed:
            with self.subTest(field=field, replacement=replacement):
                data = json.loads(json.dumps(valid))
                if route is None:
                    data = replacement
                else:
                    parent = data
                    for part in route[:-1]:
                        parent = parent[part]
                    parent[route[-1]] = replacement
                (self.root / 'materials.json').write_text(json.dumps(data))
                before = unchanged_files()
                result = subprocess.run([sys.executable, '-B', str(SCRIPT), 'scan', '--root', str(self.root)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('Invalid materials.json: ' + field, result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertEqual(result.stdout, '')
                self.assertEqual(unchanged_files(), before)

        (self.root / 'materials.json').write_text('{broken json')
        before = unchanged_files()
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), 'scan', '--root', str(self.root)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Invalid materials.json: JSON could not be parsed', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(unchanged_files(), before)

    def test_malformed_registry_rejects_all_consumers_before_material_or_index_writes(self):
        self.intake(self.write('registered.pdf', b'Registered source', external=True))
        data = self.manifest()
        data['entries'][0]['chapters'] = None
        (self.root / 'materials.json').write_text(json.dumps(data))
        source = self.write('inbox/new.pdf', b'Keep pending source')
        item = self.base / 'item.json'
        item.write_text(json.dumps(self.item(source)))
        targets = self.base / 'targets.json'
        targets.write_text(json.dumps(self.targets()))
        commands = [
            ['init', '--materials-root', str(self.materials), '--course', 'SYNTHETIC-COURSE',
             '--source-root', str(self.external)],
            ['scan'],
            ['import', '--item-json', str(item), '--expected', self.version()],
            ['index', '--expected-manifest', self.version(), '--expected-targets-json', str(targets)],
        ]
        before = {str(p.relative_to(self.base)): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.base.rglob('*') if p.is_file() and p.name != '.course-records.lock'}
        for command in commands:
            with self.subTest(command=command[0]):
                result = subprocess.run([sys.executable, '-B', str(SCRIPT), *command, '--root', str(self.root)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('Invalid materials.json: entries[0].chapters', result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertEqual(result.stdout, '')
                after = {str(p.relative_to(self.base)): (p.read_bytes(), p.stat().st_mtime_ns)
                         for p in self.base.rglob('*') if p.is_file() and p.name != '.course-records.lock'}
                self.assertEqual(after, before)

    def test_registry_validation_preserves_extra_fields_and_optional_legacy_collections(self):
        source = self.write('registered.pdf', b'Registered source', external=True)
        self.intake(source, mode='copy')
        data = self.manifest()
        data['custom_registry'] = {'preserve': ['unknown', 1]}
        entry = data['entries'][0]
        entry['custom_entry'] = {'preserve': 'original'}
        for field in ('origin_paths', 'origin_sha256', 'versions', 'received_sources'):
            entry.pop(field, None)
        (self.root / 'materials.json').write_text(json.dumps(data))
        self.assertEqual(files.registry(self.root)[0], data)
        self.assertIs(files.validate_registry(data), data)
        files.scan_course(self.root)
        files.build_indexes(self.root, self.version(), self.targets())
        self.intake(source, mode='copy')
        self.assertEqual(self.manifest()['custom_registry'], data['custom_registry'])
        self.assertEqual(self.manifest()['entries'][0]['custom_entry'], entry['custom_entry'])

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
        added = self.intake(original, mode='copy')
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
        first = self.intake(source, mode='copy')
        version, mtime = self.version(), (self.root / 'materials.json').stat().st_mtime_ns
        second = self.intake(source, mode='copy')
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
        first = self.intake(old_source, mode='copy')
        new_source = self.write('replacement/lecture.pdf', b'New original', external=True)
        self.intake(new_source, mode='copy', id=first['id'])
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

    def test_explicit_copy_failure_preserves_source_and_success_preserves_inbox(self):
        source = self.write('inbox/source.pdf', b'Preserve on failure')
        registry_before = (self.root / 'materials.json').read_bytes()
        original = files.records.atomic_write
        def fail_registry(target, data):
            if target.name == 'materials.json':
                raise OSError('Synthetic registry failure')
            return original(target, data)
        with patch.object(files.records, 'atomic_write', fail_registry):
            with self.assertRaisesRegex(OSError, 'Synthetic registry failure'):
                self.intake(source, mode='copy')
        self.assertEqual(source.read_bytes(), b'Preserve on failure')
        self.assertEqual((self.root / 'materials.json').read_bytes(), registry_before)
        # A failed transaction must be recovered explicitly before retrying.
        self.assertTrue((self.root / files.MOVE_PENDING).exists())
        with self.assertRaises(ValueError):
            self.intake(source, mode='copy')
        files.recover_moves(self.root, 'abort')
        result = self.intake(source, mode='copy')
        self.assertFalse(result['inbox_consumed'])
        self.assertTrue(source.exists())
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

    def test_init_course_rejects_hidden_codex_and_skill_roots_but_allows_hidden_source_root(self):
        hidden_src = self.base / '.codex' / 'downloads'
        hidden_src.mkdir(parents=True)
        for bad_root, bad_mat in [
            (self.base / '.codex/records', self.base / 'visible_mat'),
            (self.base / 'visible_rec', self.base / '.hidden_mat'),
        ]:
            with self.assertRaisesRegex(ValueError, 'visible'):
                files.init_course(bad_root, bad_mat, 'BAD', [hidden_src])
        skill_dir = self.base / 'skill-pkg'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text('---\nname: x\n---\n')
        with self.assertRaisesRegex(ValueError, 'Skill directory'):
            files.init_course(skill_dir / 'records', self.base / 'visible_mat2', 'BAD')
        good_rec = self.base / 'good_rec'
        good_mat = self.base / 'good_mat'
        res = files.init_course(good_rec, good_mat, 'GOOD', [hidden_src])
        self.assertTrue((good_rec / 'materials.json').is_file())
        self.assertIn('inbox', res)

    def test_import_batch_moves_deduplicates_and_preflights_atomically(self):
        f1 = self.write('lec1.pdf', b'Lecture one', external=True)
        f2 = self.write('lec2.pdf', b'Lecture two', external=True)
        f3_dup = self.write('lec1-copy.pdf', b'Lecture one', external=True)
        items = [
            self.item(f1, 'lectures'),
            self.item(f2, 'exercises'),
            self.item(f3_dup, 'lectures'),
        ]
        # Preflight failure on item #2 must leave item #1 untouched
        bad_items = [self.item(f1, 'lectures'), {**self.item(f2, 'exercises'), 'sha256': '0' * 64}]
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            files.import_materials_batch(self.root, bad_items, self.version())
        self.assertTrue(f1.exists())
        self.assertEqual(self.manifest()['entries'], [])
        # Duplicate source path in same batch must be rejected in preflight
        with self.assertRaisesRegex(ValueError, 'Duplicate source path'):
            files.import_materials_batch(self.root, [self.item(f1), self.item(f1)], self.version())
        # Valid batch moves all, deduplicates f1 & f3_dup, leaves scan clean
        res = files.import_materials_batch(self.root, items, self.version())
        self.assertEqual(res['count'], 3)
        self.assertEqual(res['moved_count'], 3)
        self.assertFalse(f1.exists())
        self.assertFalse(f2.exists())
        self.assertFalse(f3_dup.exists())
        self.assertEqual(len(self.manifest()['entries']), 2)
        scan = files.scan_course(self.root)
        self.assertFalse(scan['added'] or scan['missing'] or scan['duplicates'])

    def test_cli_import_batch_stdin_and_copy_mode(self):
        f1 = self.write('c1.pdf', b'Copy one', external=True)
        f2 = self.write('c2.pdf', b'Copy two', external=True)
        payload = json.dumps([self.item(f1, 'lectures'), self.item(f2, 'revision')])
        proc = subprocess.run(
            [sys.executable, '-B', str(SCRIPT), 'import-batch',
             '--root', str(self.root), '--items-json', '-', '--expected', self.version(), '--copy'],
            input=payload, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out['count'], 2)
        self.assertEqual(out['moved_count'], 0)
        self.assertTrue(f1.exists() and f2.exists())

    def test_import_batch_preflight_and_non_destructive_resumable_failures(self):
        f1 = self.write('a1.pdf', b'Alpha one', external=True)
        f2 = self.write('a2.pdf', b'Alpha two', external=True)
        item1, item2 = self.item(f1, 'lectures'), self.item(f2, 'exercises')
        # 1) Invalid id on item #2 must fail in dry-run preflight without moving item #1.
        before_sha = self.version()
        with self.assertRaisesRegex(ValueError, 'Unknown material id'):
            files.import_materials_batch(self.root, [item1, {**item2, 'id': 'M-nonexistent'}], before_sha)
        self.assertTrue(f1.exists() and f2.exists())
        self.assertEqual(self.version(), before_sha)
        self.assertEqual(self.manifest()['entries'], [])

        # 2) Manual edit to materials.json between items must be preserved (never overwritten by rollback)
        #    and the error report must return completed + remaining_items for clean resumption.
        real_start = files.course_moves.start_move
        calls = {'n': 0}
        def edit_after_first(root, plan):
            calls['n'] += 1
            res = real_start(root, plan)
            if calls['n'] == 1:
                cur = json.loads((root / 'materials.json').read_text())
                cur['manual_note'] = 'keep-my-manual-edit'
                (root / 'materials.json').write_text(json.dumps(cur, ensure_ascii=False, indent=2) + '\n')
            return res
        with patch.object(files.course_moves, 'start_move', side_effect=edit_after_first):
            with self.assertRaises(files.BatchImportError) as ctx:
                files.import_materials_batch(self.root, [item1, item2], before_sha)
        report = ctx.exception.report
        self.assertEqual(report['status'], 'partial_failure')
        self.assertEqual(report['completed_count'], 1)
        self.assertFalse(report['pending_move_recovery'])
        self.assertEqual(report['remaining_items'], [item2])
        self.assertEqual(self.manifest().get('manual_note'), 'keep-my-manual-edit')
        self.assertFalse(f1.exists())
        self.assertTrue(f2.exists())
        # Retry remaining_items using the updated registry SHA succeeds and keeps the manual note.
        res_resume = files.import_materials_batch(self.root, report['remaining_items'], self.version())
        self.assertEqual(res_resume['count'], 1)
        self.assertEqual(self.manifest().get('manual_note'), 'keep-my-manual-edit')
        self.assertFalse(f2.exists())

        # 3) Pending move journal on item #2 of a 3-item batch:
        #    - remaining_after_finish skips failed_item (because finish completes it)
        #    - remaining_after_abort includes failed_item (because abort restores it)
        f3 = self.write('a3.pdf', b'Alpha three', external=True)
        f4 = self.write('a4.pdf', b'Alpha four', external=True)
        f5 = self.write('a5.pdf', b'Alpha five', external=True)
        item3, item4, item5 = self.item(f3, 'lectures'), self.item(f4, 'exercises'), self.item(f5, 'revision')
        calls2 = {'n': 0}
        def crash_pending_on_second(root, plan):
            calls2['n'] += 1
            if calls2['n'] == 2:
                files.course_moves._write_plan(root, plan)
                raise OSError('Simulated interrupt after journal write')
            return real_start(root, plan)
        with patch.object(files.course_moves, 'start_move', side_effect=crash_pending_on_second):
            with self.assertRaises(files.BatchImportError) as ctx2:
                files.import_materials_batch(self.root, [item3, item4, item5], self.version())
        report2 = ctx2.exception.report
        self.assertTrue(report2['pending_move_recovery'])
        self.assertEqual(report2['completed_count'], 1)
        self.assertEqual(report2['remaining_after_finish'], [item5])
        self.assertEqual(report2['remaining_after_abort'], [item4, item5])
        self.assertIn('remaining_after_finish', report2['recovery_hint'])
        self.assertIn('remaining_after_abort', report2['recovery_hint'])
        # 3a) move-recover --decision finish completes item4, then remaining_after_finish moves item5.
        files.recover_moves(self.root, 'finish')
        self.assertFalse(f3.exists())
        self.assertFalse(f4.exists())
        self.assertTrue(f5.exists())
        res_finish_resume = files.import_materials_batch(self.root, report2['remaining_after_finish'], self.version())
        self.assertEqual(res_finish_resume['count'], 1)
        self.assertFalse(f5.exists())

        # 3b) move-recover --decision abort restores failed item, then remaining_after_abort moves both.
        f6 = self.write('a6.pdf', b'Alpha six', external=True)
        f7 = self.write('a7.pdf', b'Alpha seven', external=True)
        f8 = self.write('a8.pdf', b'Alpha eight', external=True)
        item6, item7, item8 = self.item(f6, 'lectures'), self.item(f7, 'exercises'), self.item(f8, 'revision')
        calls3 = {'n': 0}
        def crash_pending_on_second_abort(root, plan):
            calls3['n'] += 1
            if calls3['n'] == 2:
                files.course_moves._write_plan(root, plan)
                raise OSError('Simulated interrupt before abort')
            return real_start(root, plan)
        with patch.object(files.course_moves, 'start_move', side_effect=crash_pending_on_second_abort):
            with self.assertRaises(files.BatchImportError) as ctx3:
                files.import_materials_batch(self.root, [item6, item7, item8], self.version())
        report3 = ctx3.exception.report
        files.recover_moves(self.root, 'abort')
        self.assertFalse(f6.exists())
        self.assertTrue(f7.exists() and f8.exists())
        res_abort_resume = files.import_materials_batch(self.root, report3['remaining_after_abort'], self.version())
        self.assertEqual(res_abort_resume['count'], 2)
        self.assertFalse(f7.exists() or f8.exists())

    def test_cli_import_batch_partial_failure_outputs_resumable_json(self):
        f1 = self.write('p1.pdf', b'Part one', external=True)
        f2 = self.write('p2.pdf', b'Part two', external=True)
        payload = json.dumps([self.item(f1, 'lectures'), self.item(f2, 'exercises')])
        code = '\n'.join([
            'import json, sys',
            'from unittest.mock import patch',
            'sys.path.insert(0, ' + repr(str(SCRIPT.parent)) + ')',
            'import course_files',
            'real_start = course_files.course_moves.start_move',
            'n = {"v": 0}',
            'def fail_second(root, plan):',
            '    n["v"] += 1',
            '    if n["v"] == 2: raise OSError("disk error")',
            '    return real_start(root, plan)',
            'with patch.object(course_files.course_moves, "start_move", side_effect=fail_second):',
            '    course_files.main()',
        ])
        proc = subprocess.run(
            [sys.executable, '-B', '-c', code, 'import-batch',
             '--root', str(self.root), '--items-json', '-', '--expected', self.version()],
            input=payload, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)
        out = json.loads(proc.stdout)
        self.assertEqual(out['completed_count'], 1)
        self.assertEqual(len(out['remaining_items']), 1)
        self.assertIn('disk error', proc.stderr)

    def test_import_batch_same_filename_different_bytes_in_one_batch(self):
        f1 = self.write('dir1/notes.pdf', b'Version A', external=True)
        f2 = self.write('dir2/notes.pdf', b'Version B', external=True)
        res = files.import_materials_batch(
            self.root, [self.item(f1, 'lectures'), self.item(f2, 'lectures')], self.version())
        self.assertEqual(res['count'], 2)
        self.assertEqual(res['moved_count'], 2)
        paths = [Path(r['path']) for r in res['results']]
        self.assertEqual(len({str(p) for p in paths}), 2)
        self.assertTrue(all(p.is_file() for p in paths))

    def test_build_indexes_missing_material_marks_both_sections_without_broken_links(self):
        p1 = self.write('kept.pdf', b'Kept file', external=True)
        p2 = self.write('missing_later.pdf', b'Will be deleted', external=True)
        self.intake(p1, 'lectures')
        r2 = self.intake(p2, 'supplements')
        Path(r2['path']).unlink()
        visible_link = self.base / 'visible_records_link'
        visible_link.symlink_to(self.root)
        res = files.build_indexes(visible_link, self.version(), self.targets())
        self.assertEqual(res['index'], str(visible_link / 'index.html'))
        html = (self.root / 'index.html').read_text()
        self.assertNotIn('missing_later.pdf">', html)
        self.assertNotIn('C01 · pp.1-3</a> — ' + r2['id'], html)
        self.assertIn('缺失，需复核', (self.root / 'materials-index.md').read_text())
        self.assertNotIn('missing_later.pdf)', (self.root / 'materials-index.md').read_text())

    def test_import_batch_last_item_pending_hint_says_no_retry_after_finish(self):
        f1 = self.write('last1.pdf', b'Last one', external=True)
        f2 = self.write('last2.pdf', b'Last two', external=True)
        item1, item2 = self.item(f1, 'lectures'), self.item(f2, 'exercises')
        real_start = files.course_moves.start_move
        calls = {'n': 0}
        def crash_last(root, plan):
            calls['n'] += 1
            if calls['n'] == 2:
                files.course_moves._write_plan(root, plan)
                raise OSError('Simulated interrupt on last item')
            return real_start(root, plan)
        with patch.object(files.course_moves, 'start_move', side_effect=crash_last):
            with self.assertRaises(files.BatchImportError) as ctx:
                files.import_materials_batch(self.root, [item1, item2], self.version())
        self.assertEqual(ctx.exception.report['remaining_after_finish'], [])
        self.assertIn('no retry needed', ctx.exception.report['recovery_hint'])
        files.recover_moves(self.root, 'finish')


if __name__ == '__main__':
    unittest.main()
