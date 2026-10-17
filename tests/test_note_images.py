"""Focused portable-image safety tests; all feedback is synthetic."""
import base64
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_study_notes import notes, seed
from test_study_notes_v3 import fixture_v3

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jmZ8AAAAASUVORK5CYII=')
PNG_URL = 'data:image/png;base64,' + base64.b64encode(PNG).decode('ascii')
review = notes.helper('image_test_shared_review', 'render_review.py')


class PortableImageTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)
        self.root = self.base / 'course'
        seed(self.root)

    def draft(self, source):
        data = fixture_v3()
        data['items'][0]['body_html'] += '<figure><img src="' + source + '" alt="Synthetic portable image"/><figcaption>Format test only.</figcaption></figure>'
        return data

    def assert_rejected_both(self, label, source):
        data = self.draft(source)
        relative = 'notes/chapters/rejected.html'
        with self.subTest(case=label, entry='render'), self.assertRaises(ValueError):
            notes.render(data, self.base)
        with self.subTest(case=label, entry='review'), self.assertRaises(ValueError):
            review.render_fragment('<img src="' + source + '" alt="Synthetic test"/>', self.base)
        with self.subTest(case=label, entry='publish'), self.assertRaises(ValueError):
            notes.publish(self.root, relative, 'absent', data, '<html>not published</html>')
        self.assertFalse((self.root / relative).exists())

    def test_embedded_png_json_relocates_and_rebuilds_identically(self):
        original, relocated = self.base / 'original', self.base / 'relocated'
        original.mkdir(); relocated.mkdir()
        source = original / 'draft.json'
        source.write_text(json.dumps(self.draft(PNG_URL), ensure_ascii=False))
        command = [sys.executable, '-B', str(ROOT / 'skills/study-notes/scripts/render_notes.py')]
        first = original / 'note.html'
        result = subprocess.run(command + ['--input', str(source), '--output', str(first)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = first.read_bytes()
        source.rename(relocated / 'draft.json')
        first.unlink(); original.rmdir()
        second = relocated / 'note.html'
        result = subprocess.run(command + ['--input', str(relocated / 'draft.json'), '--output', str(second)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(expected, second.read_bytes())
        self.assertIn(PNG_URL, second.read_text())
        data = json.loads((relocated / 'draft.json').read_text())
        receipt = notes.publish(self.root, 'notes/chapters/portable.html', 'absent', data, second.read_text())
        self.assertTrue(receipt['changed'])
        self.assertEqual(second.read_bytes(), (self.root / receipt['path']).read_bytes())

    def test_valid_format_signatures_share_render_and_publish_validation(self):
        # These intentionally minimal signatures test the format gate, not image decoding.
        for mime, data in [('image/png', PNG), ('image/jpeg', b'\xff\xd8\xff\xe0signature-fixture'),
                           ('image/webp', b'RIFF\x08\x00\x00\x00WEBPsignature-fixture')]:
            with self.subTest(mime=mime):
                source = 'data:' + mime + ';base64,' + base64.b64encode(data).decode('ascii')
                self.assertEqual(notes.images.image_data(source, self.base), source)
                self.assertEqual(notes.images.validate_reference(source), source)
                self.assertIn(source, review.render_fragment('<img src="' + source + '" alt="Synthetic test"/>', self.base))
                value = self.draft(source)
                html = notes.render(value, self.base)
                notes.publish(self.root, 'notes/chapters/' + mime.split('/')[1] + '.html', 'absent', value, html)

    def test_bad_and_noncanonical_base64_rejected_both(self):
        for label, payload in [('bad-character', 'AAAA!'), ('whitespace', 'iVBORw0K Ggo='),
                               ('non-ascii', '汉字'), ('extra-padding', 'iVBORw0KGgo==='),
                               ('noncanonical-pad-bits', 'iVBORw0KGgp=')]:
            self.assert_rejected_both(label, 'data:image/png;base64,' + payload)

    def test_mime_mismatch_and_unsupported_data_rejected_both(self):
        for label, source in [('mime-mismatch', PNG_URL.replace('image/png', 'image/jpeg')),
                              ('wrong-magic', 'data:image/png;base64,' + base64.b64encode(b'not-an-image').decode()),
                              ('svg', 'data:image/svg+xml;base64,PHN2Zy8+'),
                              ('gif', 'data:image/gif;base64,R0lGODlh'),
                              ('html', 'data:text/html;base64,PGI+eDwvYj4='),
                              ('non-base64', 'data:image/png,plain'),
                              ('parameter', PNG_URL.replace(';base64', ';charset=utf-8;base64'))]:
            self.assert_rejected_both(label, source)

    def test_decoded_size_limit_rejected_both(self):
        payload = b'\x89PNG\r\n\x1a\n' + b'\0' * (notes.images.MAX_IMAGE_BYTES - 7)
        self.assertEqual(len(payload), 20 * 1024 * 1024 + 1)
        source = 'data:image/png;base64,' + base64.b64encode(payload).decode('ascii')
        self.assert_rejected_both('20MB-plus-one', source)

    def test_exact_limit_is_accepted_by_byte_validator(self):
        payload = b'\x89PNG\r\n\x1a\n' + b'\0' * (notes.images.MAX_IMAGE_BYTES - 8)
        source = 'data:image/png;base64,' + base64.b64encode(payload).decode('ascii')
        self.assertEqual(notes.images.validate_reference(source), source)

    def test_external_absolute_and_parent_escape_rejected_both(self):
        for source in ('https://example.com/x.png', 'file:///tmp/x.png', '//example.com/x.png',
                       '/tmp/x.png', '../x.png', 'images/../../x.png', 'javascript:alert(1)'):
            self.assert_rejected_both(source, source)

    def test_safe_relative_file_still_embeds_and_symlink_escape_stops_render(self):
        images = self.base / 'images'; images.mkdir()
        (images / 'tiny.png').write_bytes(PNG)
        value = self.draft('images/tiny.png')
        html = notes.render(value, self.base)
        self.assertIn(PNG_URL, html)
        notes.publish(self.root, 'notes/chapters/relative.html', 'absent', value, html)
        outside = self.base / 'outside.png'; outside.write_bytes(PNG)
        inside = self.base / 'input'; inside.mkdir()
        (inside / 'linked.png').symlink_to(outside)
        with self.assertRaises(ValueError):
            notes.render(self.draft('linked.png'), inside)

    def test_shared_review_saved_json_rebuilds_without_scratch_assets(self):
        original = self.base / 'scratch'
        original.mkdir()
        (original / 'tiny.png').write_bytes(PNG)
        item = {'id': 'q1', 'title': 'Synthetic image persistence', 'source': 'Test fixture',
                'question_html': '<p>Describe the synthetic image.</p><img src="tiny.png" alt="Synthetic portable image"/>',
                'solution_html': '<p>Format test only.</p>', 'personal_review': '',
                'evidence': {'assistance': 'solution', 'outcome': 'not_attempted'}}
        data = {'course': 'Synthetic', 'unit': 'Persistence', 'items': [item]}
        source = original / 'draft.json'
        source.write_text(json.dumps(data), encoding='utf-8')
        command = [sys.executable, '-B', str(ROOT / 'skills/study-planner/scripts/render_review.py')]
        first = original / 'preview.html'
        result = subprocess.run(command + ['--input', str(source), '--output', str(first)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = first.read_bytes()
        # The saved shared JSON embeds the checked bytes; no binary write role is needed.
        embedded = review.image_data('tiny.png', original)
        self.assertEqual(embedded, PNG_URL)
        item['question_html'] = item['question_html'].replace('tiny.png', embedded)
        notes.records.write_record(self.root, 'reviews/U01.json', 'main', 'absent', json.dumps(data))
        shutil.rmtree(original)
        formal = self.root / 'reviews/U01.json'
        result = subprocess.run(command + ['--input', str(formal), '--root', str(self.root),
                                '--path', 'reviews/U01.html', '--expected', 'absent'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(expected, (self.root / 'reviews/U01.html').read_bytes())
        relocated = self.base / 'relocated-course'
        self.root.rename(relocated)
        second = relocated / 'preview.html'
        result = subprocess.run(command + ['--input', str(relocated / 'reviews/U01.json'),
                                '--output', str(second)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(expected, second.read_bytes())
        self.assertEqual(sorted(entry.suffix for entry in (relocated / 'reviews').iterdir()), ['.html', '.json'])

    def test_shared_review_keeps_semantic_tag_boundary(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported element: figure'):
            review.render_fragment('<figure><img src="' + PNG_URL + '" alt="Synthetic test"/></figure>', self.base)

    def test_shared_review_legacy_relative_images_keep_identical_html(self):
        local = self.base / 'tiny.png'
        local.write_bytes(PNG)
        source = '<p>Format test only.</p><img src="tiny.png" alt="Synthetic test"/>'
        self.assertEqual(review.render_fragment(source, self.base),
                         '<p>Format test only.</p><img src="' + PNG_URL + '" alt="Synthetic test">')
        outside = self.base / 'outside.png'
        outside.write_bytes(PNG)
        inside = self.base / 'input'
        inside.mkdir()
        (inside / 'linked.png').symlink_to(outside)
        with self.assertRaises(ValueError):
            review.render_fragment('<img src="linked.png" alt="Synthetic test"/>', inside)


if __name__ == '__main__':
    unittest.main(verbosity=2)
