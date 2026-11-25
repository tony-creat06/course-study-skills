"""Task-scoped delivery checks, using real temporary files and helper CLI calls."""
from html import unescape
import importlib.util
import json
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote, unquote

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/study-planner/scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('delivery_tests_module', SCRIPTS / 'course_delivery.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
files = delivery.files
records = delivery.records


class CourseDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / 'Visible-course'
        self.home.mkdir()
        self.root = self.home / '学习产出'
        self.materials = self.home / '资料'
        self.source = self.home / 'lecture.md'
        self.source.write_text('Synthetic Chapter 1 lecture: a contextual source, not learner data.')
        self.captions = self.home / 'L01.srt'
        self.captions.write_text('1\n00:00:01,000 --> 00:00:02,000\nSynthetic teacher transcript.\n')

    def begin(self, activity='setup', expected=None, **extra):
        request = dict(extra)
        if expected is not None:
            request['expected'] = expected
        return delivery.begin_course(self.home, activity=activity, request=request, course_id='SYNTHETIC')

    def move(self, source, category='lectures'):
        item = {'path': str(source), 'sha256': files.sha_file(source), 'category': category,
                'chapters': [{'chapter': 'C01', 'locator': 'Section 1 / cue 1'}],
                'inspection': 'Synthetic source actually inspected.'}
        return files.import_material(self.root, item, files.sha_file(self.root / 'materials.json'))

    def core(self):
        for p in delivery.SETUP_FILES:
            records.write_record(self.root, p, 'main', records.read_record(self.root, p)['sha256'],
                                 '# Synthetic ' + p + '\nActual fixture scope: first chapter, no student answers.')

    def output(self, path, text='Synthetic substantive saved artifact for current task.'):
        role = 'notes' if path.startswith('notes/') else 'questions' if path.startswith('questions/') else 'analyst' if path.startswith('exam/') else 'main'
        records.write_record(self.root, path, role, records.read_record(self.root, path)['sha256'], text)

    def setup(self):
        run = self.begin()
        self.assertEqual(run['supplied_files'], 2)
        self.first = self.move(self.source)
        self.move(self.captions, 'transcripts')
        self.core()
        result = delivery.finish_course(self.root, run['run'])
        self.assertFalse(result['errors'], result)
        return result

    def notes_expectation(self, freshness='changed'):
        return [{'path': 'notes/chapters/C01.html', 'kind': 'notes', 'freshness': freshness,
                 'source_paths': [self.first['path']]}]

    def test_setup_fails_for_unmoved_batch_and_records_failure_then_repair_passes(self):
        run = self.begin()
        self.core()
        failure = delivery.finish_course(self.root, run['run'])
        self.assertEqual(failure['status'], 'incomplete')
        self.assertTrue(self.source.exists())
        self.assertIn('尚未完成', (self.root / 'delivery.md').read_text())
        self.move(self.source)
        self.move(self.captions, 'transcripts')
        result = delivery.finish_course(self.root, run['run'])
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['moved_count'], 2)
        self.assertFalse(self.source.exists())
        self.assertTrue((self.home / delivery.PORTAL).is_file())
        self.assertIn('delivery.md', (self.home / delivery.PORTAL).read_text())
        self.assertIn(str(self.materials / 'inbox'), (self.root / 'index.md').read_text())
        self.assertIn('materials-index.md', [p.name for p in self.root.iterdir()])
        self.assertIn('C01', (self.root / 'materials-index.md').read_text())

    def test_question_batch_handoff_announces_required_analysis_before_finish(self):
        run = self.begin()
        self.move(self.source)
        self.move(self.captions, 'exercises')
        self.core()
        handoff = delivery.verify_course(self.root, run['run'], materials_only=True)
        self.assertEqual(handoff['status'], 'verified')
        self.assertEqual(handoff['required_handoffs'][0]['module'], 'exam-analysis')
        self.assertEqual(delivery.finish_course(self.root, run['run'])['status'], 'incomplete')
        self.output('exam/brief.md', 'Teacher tutorial: inspected bounded scope, not formal exam evidence.')
        self.output('exam/profile.md', 'Internal source anchors and required ability chain of this tutorial.')
        self.assertEqual(delivery.finish_course(self.root, run['run'])['status'], 'verified')

    def test_material_handoff_can_verify_before_teaching_or_analysis_outputs(self):
        run = self.begin()
        self.move(self.source)
        self.move(self.captions, 'transcripts')
        report = delivery.verify_course(self.root, run['run'], materials_only=True)
        self.assertEqual(report['status'], 'verified')
        self.assertEqual(report['verification_phase'], 'material_handoff')
        self.assertEqual(report['artifacts_checked'], [])
        self.assertTrue((self.root / 'materials-index.md').exists())
        self.assertIn('C01', (self.root / 'materials-index.md').read_text())
        self.assertFalse((self.root / 'lessons').exists())
        self.assertEqual(delivery.finish_course(self.root, run['run'])['status'], 'incomplete')

    def test_existing_stale_note_does_not_count_as_current_changed_output(self):
        self.setup()
        self.output('notes/chapters/C01.html', '<html><main>Previous saved chapter.</main></html>')
        run = self.begin('notes', self.notes_expectation())
        old = delivery.finish_course(self.root, run['run'])
        self.assertEqual(old['status'], 'incomplete')
        self.assertTrue(any('not updated' in e for e in old['errors']))
        self.output('notes/chapters/C01.html', '<html><main>New context and derivation for this task.</main></html>')
        current = delivery.finish_course(self.root, run['run'])
        self.assertEqual(current['status'], 'verified', current)
        self.assertIn('notes/chapters/C01.html', (self.root / 'index.html').read_text())
        self.assertEqual(delivery.finish_course(self.root, run['run'])['status'], 'verified')

    def test_ordinary_notes_check_hashes_only_current_source_and_outputs(self):
        self.setup()
        unrelated = self.materials / 'textbooks/large-book.txt'
        unrelated.write_text('Unrelated old source must not be rehashed')
        real_hash = files.sha_file
        def bounded(path):
            self.assertNotEqual(Path(path), unrelated, 'Ordinary task rehashed unrelated material')
            return real_hash(path)
        with patch.object(files, 'scan_course', side_effect=AssertionError('Full scan forbidden')):
            with patch.object(files, 'sha_file', side_effect=bounded):
                run = self.begin('notes', self.notes_expectation(), material_ids=[self.first['id']])
                self.output('notes/chapters/C01.html', '<html><main>Current task notes.</main></html>')
                result = delivery.finish_course(self.root, run['run'])
        self.assertEqual(result['status'], 'verified', result)
        self.assertEqual(result['checked_supplied_files'], 0)

    def test_inbox_intake_is_bounded_and_new_file_is_moved(self):
        self.setup()
        incoming = self.materials / 'inbox/L02.srt'
        incoming.write_text('Synthetic new cue for lesson two.')
        run = self.begin('intake')
        self.assertEqual(run['supplied_files'], 1)
        self.move(incoming, 'transcripts')
        result = delivery.finish_course(self.root, run['run'])
        self.assertEqual(result['status'], 'verified', result)
        self.assertEqual(result['moved_count'], 1)

    def test_reuse_requires_a_prior_verified_artifact_and_unchanged_dependencies(self):
        self.setup()
        run = self.begin('notes', self.notes_expectation())
        self.output('notes/chapters/C01.html', '<html><main>Verified chapter body.</main></html>')
        self.assertEqual(delivery.finish_course(self.root, run['run'])['status'], 'verified')
        rerun = self.begin('notes', self.notes_expectation('reuse'))
        self.assertEqual(delivery.finish_course(self.root, rerun['run'])['status'], 'verified')
        source = Path(self.first['path'])
        source.write_text('Source materially changed after prior verified note')
        newrun = self.begin('notes', self.notes_expectation('reuse'))
        result = delivery.finish_course(self.root, newrun['run'])
        self.assertEqual(result['status'], 'incomplete')
        self.assertTrue(any('Reuse' in e for e in result['errors']))

    def test_missing_outputs_are_not_replaced_with_placeholder_success(self):
        self.setup()
        run = self.begin('notes', self.notes_expectation())
        failure = delivery.finish_course(self.root, run['run'])
        self.assertEqual(failure['status'], 'incomplete')
        self.assertIn('notes/chapters/C01.html', str(failure['errors']))
        self.output('notes/chapters/C01.html', 'TODO')
        self.assertEqual(delivery.finish_course(self.root, run['run'])['status'], 'incomplete')

    def test_practice_requires_paired_author_solution_but_hides_solution_link(self):
        self.setup()
        with self.assertRaisesRegex(ValueError, 'solution'):
            self.begin('practice', [{'path': 'questions/prompts/P01.md', 'kind': 'prompt'}])
        run = self.begin('practice', [{'path': 'questions/prompts/P01.md', 'kind': 'prompt'},
                                     {'path': 'questions/solutions/P01.md', 'kind': 'solution'}])
        self.output('questions/prompts/P01.md', 'Synthetic independent question with complete conditions.')
        self.output('questions/solutions/P01.md', 'Synthetic private author solution, not student evidence.')
        self.output('current.md', 'P01 assigned but unanswered; no learner outcome inferred.')
        result = delivery.finish_course(self.root, run['run'])
        self.assertEqual(result['status'], 'verified', result)
        for p in ['index.html', 'delivery.md']:
            self.assertNotIn('questions/solutions/P01.md', (self.root / p).read_text())

    def test_analysis_delivery_requires_detail_and_visible_brief(self):
        self.setup()
        run = self.begin('analysis', [{'path': 'exam/brief.md', 'kind': 'analysis_brief'},
                                     {'path': 'exam/profile.md', 'kind': 'analysis_detail'}])
        self.output('exam/profile.md', 'Synthetic detailed bounded analysis of a single teacher question.')
        self.assertEqual(delivery.finish_course(self.root, run['run'])['status'], 'incomplete')
        self.output('exam/brief.md', 'Synthetic analyzed scope, topic and ability requirements; no predictions.')
        result = delivery.finish_course(self.root, run['run'])
        self.assertEqual(result['status'], 'verified', result)
        self.assertIn('exam/brief.md', (self.root / 'index.html').read_text())
        self.assertNotIn('exam/profile.md', (self.root / 'index.html').read_text())

    def test_manual_portal_edit_is_preserved(self):
        self.setup()
        run = self.begin('notes', self.notes_expectation())
        self.output('notes/chapters/C01.html', '<html><main>New chapter content.</main></html>')
        (self.home / delivery.PORTAL).write_text('Manual entry edit')
        result = delivery.finish_course(self.root, run['run'])
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual((self.home / delivery.PORTAL).read_text(), 'Manual entry edit')

    def test_final_publication_detects_changed_artifact_then_repair_can_retry(self):
        self.setup()
        run = self.begin('notes', self.notes_expectation())
        self.output('notes/chapters/C01.html', '<html><main>New chapter content.</main></html>')
        real = delivery.publish_portal
        def edit_after_portal(plan, root):
            p = real(plan, root)
            (root / 'notes/chapters/C01.html').write_text('<html><main>Changed during publish.</main></html>')
            return p
        with patch.object(delivery, 'publish_portal', edit_after_portal):
            self.assertEqual(delivery.finish_course(self.root, run['run'])['status'], 'incomplete')
        self.output('notes/chapters/C01.html', '<html><main>Repaired complete chapter content.</main></html>')
        self.assertEqual(delivery.finish_course(self.root, run['run'])['status'], 'verified')

    def test_source_changed_during_publication_cannot_be_reported_verified(self):
        self.setup()
        run = self.begin('notes', self.notes_expectation())
        self.output('notes/chapters/C01.html', '<html><main>Chapter using the old source.</main></html>')
        real = delivery.publish_portal
        def edit_source(plan, root):
            result = real(plan, root)
            Path(self.first['path']).write_text('Different source content during final publication')
            return result
        with patch.object(delivery, 'publish_portal', edit_source):
            result = delivery.finish_course(self.root, run['run'])
        self.assertEqual(result['status'], 'incomplete')
        self.assertTrue(any('Dependency changed' in e for e in result['errors']))

    def test_explicit_source_audit_excludes_learner_outputs_and_generated_course_portal(self):
        self.setup()
        report = files.scan_course(self.root)
        self.assertFalse(report['added'], report['added'])
        self.assertFalse(report['missing'], report['missing'])

    def test_expected_output_kind_cannot_point_at_wrong_folder(self):
        self.setup()
        with self.assertRaisesRegex(ValueError, 'owned output'):
            self.begin('notes', [{'path': 'lessons/L01.md', 'kind': 'notes'}])

    def test_move_journal_blocks_course_delivery_and_ordinary_writes(self):
        self.setup()
        run = self.begin('notes', self.notes_expectation())
        (self.root / files.MOVE_PENDING).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'move'):
            delivery.finish_course(self.root, run['run'])
        with self.assertRaises(ValueError):
            self.output('current.md')

    def test_hidden_workspace_and_missing_note_obligation_are_rejected_before_creation(self):
        with self.assertRaises(ValueError):
            delivery.begin_course(self.base / '.hidden/workspace', activity='setup')
        self.assertFalse((self.base / '.hidden').exists())
        codex_home = self.base / 'codex_home_dir'
        with patch.dict('os.environ', {'CODEX_HOME': str(codex_home)}):
            with self.assertRaisesRegex(ValueError, 'CODEX_HOME'):
                delivery.begin_course(codex_home / 'course', activity='setup')
        skill_dir = self.base / 'skill_dir'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text('---\nname: x\n---\n')
        with self.assertRaisesRegex(ValueError, 'Skill directory'):
            delivery.begin_course(skill_dir / 'course', activity='setup')
        with self.assertRaisesRegex(ValueError, 'notes'):
            self.begin('lesson', [{'path': 'lessons/L01.md', 'kind': 'lesson'}])
        self.assertFalse(self.root.exists())

    def test_supplied_same_byte_duplicate_is_deduplicated_but_both_sources_removed(self):
        self.captions.write_bytes(self.source.read_bytes())
        run = self.begin()
        self.move(self.source)
        self.move(self.captions)
        self.core()
        result = delivery.finish_course(self.root, run['run'])
        self.assertEqual(result['status'], 'verified', result)
        self.assertEqual(result['moved_count'], 2)
        self.assertEqual(len(result['materials_checked']), 1)

    def test_cli_finish_reports_nonzero_for_missing_delivery(self):
        run = self.begin()
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'course_delivery.py'),
                                 'finish', '--root', str(self.root), '--run', run['run']],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'incomplete')

    def test_legacy_course_in_codex_continues_begin_to_finish_via_symlink_and_real_path(self):
        legacy_home = self.base / 'PHAS0042'
        legacy_materials = legacy_home / '资料'
        for sub in ('inbox', *files.CATEGORIES):
            (legacy_materials / sub).mkdir(parents=True, exist_ok=True)
        lec = legacy_materials / 'lectures/lec1.md'
        lec.write_text('Legacy lecture 1 content.')
        # Use a different directory depth from legacy_home/学习产出 to verify logical link resolution.
        legacy_real = self.base / '.codex' / 'deep' / 'workspace' / 'PHAS0042'
        legacy_real.mkdir(parents=True)
        (legacy_real / 'course.md').write_text('# PHAS0042\nLegacy established course.')
        (legacy_real / 'current.md').write_text('Lesson 1 completed.')
        manifest = {
            'schema_version': 1,
            'course_id': 'PHAS0042',
            'materials_root': str(legacy_materials),
            'source_roots': [str(legacy_materials)],
            'entries': [{
                'id': 'M-legacy1',
                'path': str(lec),
                'sha256': files.sha_file(lec),
                'category': 'lectures',
                'chapters': [{'chapter': 'C01', 'locator': 'Section 1'}],
                'inspection': 'Inspected section 1',
            }],
        }
        (legacy_real / 'materials.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        visible_link = legacy_home / '学习产出'
        visible_link.symlink_to(legacy_real)

        # A brand-new symlink pointing to an empty .codex folder must still be rejected.
        empty_home = self.base / 'EMPTY_NEW'
        empty_home.mkdir()
        empty_codex = self.base / '.codex' / 'workspace' / 'EMPTY_NEW'
        empty_codex.mkdir(parents=True)
        (empty_home / '学习产出').symlink_to(empty_codex)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            delivery.begin_course(empty_home, activity='setup')

        # 1) Legacy course continuation via visible symlink entry.
        run = delivery.begin_course(legacy_home, activity='lesson', request={
            'expected': [
                {'path': 'lessons/L02.md', 'kind': 'lesson', 'freshness': 'new'},
                {'path': 'notes/chapters/C01.html', 'kind': 'notes', 'freshness': 'changed'},
            ],
        })
        records.write_record(visible_link, 'lessons/L02.md', 'main', 'absent', 'Legacy L02 lesson.')
        records.write_record(visible_link, 'notes/chapters/C01.html', 'notes', 'absent',
                             '<html><main>Legacy chapter 1 notes.</main></html>')
        records.write_record(visible_link, 'current.md', 'main',
                             records.read_record(visible_link, 'current.md')['sha256'],
                             'Lesson 2 completed.')
        res = delivery.finish_course(visible_link, run['run'])
        self.assertEqual(res['status'], 'verified', res)
        self.assertEqual(res['index'], str(visible_link / 'index.html'))
        delivery_json = json.loads((legacy_real / 'delivery.json').read_text())
        self.assertEqual(delivery_json['index'], str(visible_link / 'index.html'))
        index_html = Path(res['index']).read_text()
        self.assertIn('lessons/L02.md', index_html)
        self.assertIn('notes/chapters/C01.html', index_html)
        self.assertIn(quote('../资料/lectures/lec1.md', safe='/'), index_html)
        self.assertIn(quote('学习产出/index.html', safe='/'), (legacy_home / delivery.PORTAL).read_text())
        # Opening the index path returned by finish directly must resolve every href logically.
        for href in re.findall(r'<a\s+href="([^"]+)"', index_html):
            resolved = Path(posixpath.normpath(posixpath.join(str(Path(res['index']).parent), unquote(unescape(href)))))
            self.assertTrue(resolved.is_file(), f'Broken link {href} -> {resolved}')

        # 2) Legacy course continuation via explicit real .codex path still returns visible index path.
        run2 = delivery.begin_course(legacy_home, root=legacy_real, activity='notes', request={
            'expected': [{'path': 'notes/chapters/C01.html', 'kind': 'notes', 'freshness': 'changed'}],
        })
        records.write_record(legacy_real, 'notes/chapters/C01.html', 'notes',
                             records.read_record(legacy_real, 'notes/chapters/C01.html')['sha256'],
                             '<html><main>Updated legacy chapter 1 notes.</main></html>')
        res2 = delivery.finish_course(legacy_real, run2['run'])
        self.assertEqual(res2['status'], 'verified', res2)
        self.assertEqual(res2['index'], str(visible_link / 'index.html'))

    def test_finish_fails_when_index_link_is_broken_from_portal_entry(self):
        self.setup()
        run = self.begin('notes', self.notes_expectation())
        self.output('notes/chapters/C01.html', '<html><main>Body.</main></html>')
        real_build = files.build_indexes
        def build_with_broken_link(root, expected_manifest, expected_targets, show_solutions=False, link_base=None):
            res = real_build(root, expected_manifest, expected_targets, show_solutions, link_base=link_base)
            html_path = Path(root) / 'index.html'
            broken = html_path.read_text().replace(
                quote('../资料/lectures/lecture.md', safe='/'), '../nonexistent/lecture.md', 1)
            self.assertIn('../nonexistent/lecture.md', broken)
            html_path.write_text(broken)
            return res
        with patch.object(files, 'build_indexes', side_effect=build_with_broken_link):
            res = delivery.finish_course(self.root, run['run'])
        self.assertEqual(res['status'], 'incomplete')
        self.assertTrue(any('Broken index link' in e for e in res['errors']), res['errors'])

    def test_legacy_course_without_materials_json_continues_against_readonly_sources(self):
        legacy_home = self.base / 'PHAS0049'
        legacy_home.mkdir()
        raw_dir = self.base / 'readonly-phas0049'
        raw_dir.mkdir()
        raw_lec = raw_dir / 'lecture1.pdf'
        raw_lec.write_bytes(b'Read-only legacy lecture PDF bytes.')
        legacy_real = self.base / '.codex' / 'legacy-courses' / 'PHAS0049'
        legacy_real.mkdir(parents=True)
        (legacy_real / 'course.md').write_text('# PHAS0049\nExisting legacy course without materials.json.')
        (legacy_real / 'study-plan.md').write_text('# Study Plan\nNext: L03.')
        (legacy_real / 'current.md').write_text('Completed L02.')
        visible_link = legacy_home / '学习产出'
        visible_link.symlink_to(legacy_real)

        run = delivery.begin_course(legacy_home, activity='lesson', request={
            'expected': [
                {'path': 'lessons/L03.md', 'kind': 'lesson', 'freshness': 'new', 'source_paths': [str(raw_lec)]},
                {'path': 'notes/chapters/C02.html', 'kind': 'notes', 'freshness': 'new', 'source_paths': [str(raw_lec)]},
            ],
        })
        self.assertTrue(run['legacy_no_manifest'])
        self.assertIsNone(run['inbox'])
        records.write_record(visible_link, 'lessons/L03.md', 'main', 'absent', 'PHAS0049 Lesson 3.')
        records.write_record(visible_link, 'notes/chapters/C02.html', 'notes', 'absent',
                             '<html><main>PHAS0049 Chapter 2 notes.</main></html>')
        records.write_record(visible_link, 'current.md', 'main',
                             records.read_record(visible_link, 'current.md')['sha256'],
                             'Completed L03.')
        res = delivery.finish_course(visible_link, run['run'])
        self.assertEqual(res['status'], 'verified', res)
        self.assertEqual(res['index'], str(visible_link / 'index.html'))
        self.assertFalse((legacy_real / 'materials.json').exists())
        self.assertFalse((legacy_home / '资料').exists())
        self.assertTrue(raw_lec.is_file() and raw_lec.read_bytes() == b'Read-only legacy lecture PDF bytes.')
        self.assertIn('lessons/L03.md', (legacy_real / 'index.html').read_text())
        self.assertIn(quote('学习产出/index.html', safe='/'), (legacy_home / delivery.PORTAL).read_text())
        self.assertNotIn('inbox', (legacy_home / delivery.PORTAL).read_text())
        with self.assertRaisesRegex(ValueError, 'materials-only'):
            delivery.verify_course(visible_link, run['run'], materials_only=True)

    def test_unrelated_missing_material_does_not_fail_current_note_delivery_but_dependent_missing_does(self):
        extra = self.home / 'old_extra.md'
        extra.write_text('Unrelated chapter 2 source.')
        run_setup = self.begin()
        self.first = self.move(self.source)
        self.move(self.captions, 'transcripts')
        extra_entry = files.import_material(self.root, {
            'path': str(extra), 'sha256': files.sha_file(extra), 'category': 'supplements',
            'chapters': [{'chapter': 'C02', 'locator': 'Section 2'}],
            'inspection': 'Synthetic chapter 2 supplement.',
        }, files.sha_file(self.root / 'materials.json'))
        self.core()
        self.assertEqual(delivery.finish_course(self.root, run_setup['run'])['status'], 'verified')

        # Delete the unrelated C02 material externally; C01 notes delivery must still pass.
        Path(extra_entry['path']).unlink()
        run_c01 = self.begin('notes', self.notes_expectation(), material_ids=[self.first['id']])
        self.output('notes/chapters/C01.html', '<html><main>Chapter 1 notes only.</main></html>')
        res = delivery.finish_course(self.root, run_c01['run'])
        self.assertEqual(res['status'], 'verified', res)
        for nav in ('index.html', 'index.md', 'materials-index.md'):
            text = (self.root / nav).read_text()
            self.assertIn('缺失，需复核', text)
        # Neither 资料分类 nor 章节索引 should emit a clickable link to missing old_extra.md.
        self.assertNotIn('old_extra.md">', (self.root / 'index.html').read_text())
        self.assertNotIn('C02 · Section 2</a>', (self.root / 'index.html').read_text())
        self.assertNotIn('C02 · Section 2](', (self.root / 'materials-index.md').read_text())
        self.assertIn('C02 · Section 2', (self.root / 'materials-index.md').read_text())

        # Depending on the missing material must fail at begin, and deleting a dependency mid-run must fail at finish.
        with self.assertRaisesRegex(ValueError, 'readable file'):
            self.begin('notes', self.notes_expectation(), material_ids=[extra_entry['id']])
        run_dep = self.begin('notes', self.notes_expectation(), material_ids=[self.first['id']])
        self.output('notes/chapters/C01.html', '<html><main>Chapter 1 notes v2.</main></html>')
        Path(self.first['path']).unlink()
        res_missing_dep = delivery.finish_course(self.root, run_dep['run'])
        self.assertEqual(res_missing_dep['status'], 'incomplete')
        self.assertTrue(any('changed after begin' in e or 'Dependency changed' in e for e in res_missing_dep['errors']))


if __name__ == '__main__':
    unittest.main()
