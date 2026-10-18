#!/usr/bin/env python3
"""Render module feedback into self-contained notes; protect sources and destination versions."""
import argparse
import hashlib
from html import escape
import importlib.util
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def helper(name, filename):
    path = Path(__file__).resolve().parents[2] / 'study-planner' / 'scripts' / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


records = helper('notes_records', 'course_records.py')
math_text = helper('notes_math_text', 'math_text.py')
fragments = helper('notes_fragments', 'render_review.py')
IMAGE_SPEC = importlib.util.spec_from_file_location('notes_images', Path(__file__).with_name('note_images.py'))
images = importlib.util.module_from_spec(IMAGE_SPEC)
IMAGE_SPEC.loader.exec_module(images)
fragments.image_data = images.image_data
# This private helper instance permits semantic note figures without changing the shared renderer.
fragments.HTML_TAGS.update({'figure', 'figcaption', 'caption'})
fragments.MATH_ATTRS.add('form')
# Language annotations keep bilingual passages accessible in this renderer only.
for tag in fragments.HTML_TAGS:
    fragments.HTML_ATTRS[tag] = fragments.HTML_ATTRS.get(tag, set()) | {'lang'}
KINDS = {'concept': '核心概念', 'term': '术语与表达', 'derivation': '推导', 'exam': '考试表达'}
BASES = {'requirement': '课程明确要求', 'past-paper': '真题中出现过', 'reference': '自拟参考表达'}
MODULE_PATHS = {'study-planner': {'practice'}, 'course-study': {'lessons', 'side-notes'},
                'exam-analysis': {'exam'}, 'practice-builder': {'questions'}}
RAW_MATH = re.compile(r'\\[A-Za-z]+|\\[()\[\]]|[_^]\{')


def has_raw_math(value):
    return bool(RAW_MATH.search(value) or math_text.has_math_dollars(value))


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + ' must be a nonempty string')
    if has_raw_math(value):
        raise ValueError('Raw LaTeX in ' + label + '; typeset formulas with MathML')
    return escape(value)


def source_list(data):
    sources = data.get('sources')
    if not isinstance(sources, list) or not sources:
        raise ValueError('sources must identify actual module feedback')
    seen = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != {'module', 'path', 'sha256'}:
            raise ValueError('Each source requires module, path and sha256')
        module, path, sha = source['module'], source['path'], source['sha256']
        if not isinstance(module, str) or module not in MODULE_PATHS:
            raise ValueError('Unsupported feedback module')
        if not isinstance(path, str):
            raise ValueError('Feedback path must be a string')
        rel = Path(path)
        if rel.is_absolute() or '..' in rel.parts or str(rel) != path:
            raise ValueError('Feedback path must be a canonical course-relative path')
        allowed = (module == 'study-planner' and path in records.MAIN_FILES) or (
            len(rel.parts) >= 2 and rel.parts[0] in MODULE_PATHS[module] and rel.suffix in {'.md', '.json'})
        if not allowed:
            raise ValueError('Feedback path does not belong to ' + module)
        if path in seen:
            raise ValueError('Duplicate feedback path')
        seen.add(path)
        if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha):
            raise ValueError('Feedback requires an existing SHA256, not absent')
    return sources


def fragment(value, base):
    result = fragments.render_fragment(value, base)
    # Formula code blocks must not bypass the student-facing typesetting requirement.
    wrapper = ET.fromstring('<fragment>' + value + '</fragment>')
    for element in wrapper.iter():
        if 'form' in element.attrib and (fragments.local_tag(element.tag) != 'mo' or element.attrib['form'] not in {'prefix', 'infix', 'postfix'}):
            raise ValueError('MathML form is limited to prefix/infix/postfix on mo')
    if has_raw_math(''.join(wrapper.itertext())):
        raise ValueError('Raw LaTeX detected, including code blocks; use MathML')
    return result


CONTENT_SPEC = importlib.util.spec_from_file_location('note_content', Path(__file__).with_name('note_content.py'))
sections = importlib.util.module_from_spec(CONTENT_SPEC)
CONTENT_SPEC.loader.exec_module(sections)
ASSETS = Path(__file__).resolve().parents[1] / 'assets'
CSS = (ASSETS / 'notes.css').read_text(encoding='utf-8')
SCRIPT = (ASSETS / 'notes.js').read_text(encoding='utf-8')


def lecture_renderer():
    spec = importlib.util.spec_from_file_location('lecture_notes', Path(__file__).with_name('lecture_notes.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render(data, base):
    if isinstance(data, dict) and type(data.get('schema_version')) is int and data['schema_version'] == 3:
        return lecture_renderer().render(data, base, source_list, fragment, text, sections)
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] not in {1, 2}:
        raise ValueError('schema_version must be 1 or 2')
    if not isinstance(data.get('kind'), str) or data['kind'] not in {'lesson', 'chapter'}:
        raise ValueError('kind must be lesson or chapter')
    fields = {'schema_version', 'course', 'unit', 'kind', 'scope', 'sources', 'items', 'lesson_links', 'coverage', 'intro_html'}
    if set(data) - fields:
        raise ValueError('Unsupported note metadata; learner evidence belongs to the planner')
    title = text(data.get('course'), 'course') + ' · ' + text(data.get('unit'), 'unit')
    scope = text(data.get('scope'), 'scope')
    sources = source_list(data)
    source_paths = {source['path'] for source in sources}
    items = data.get('items')
    if not isinstance(items, list) or not items:
        raise ValueError('items must contain taught topics')
    seen, prepared = set(), []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Each item must be an object')
        item_id = text(item.get('id'), 'item id')
        if item_id in seen:
            raise ValueError('Duplicate topic id')
        seen.add(item_id)
        kind = item.get('kind')
        if not isinstance(kind, str) or kind not in KINDS:
            raise ValueError('Unsupported topic kind')
        item_title = text(item.get('title'), 'title')
        source = text(item.get('source'), 'source locator')
        refs = item.get('source_refs')
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in source_paths for ref in refs):
            raise ValueError('source_refs must refer to declared module feedback')
        summary, detail = fragment(item.get('summary_html'), base), fragment(item.get('detail_html'), base)
        recall = item.get('recall', [])
        if not isinstance(recall, list):
            raise ValueError('recall must be a list')
        prompts = ''.join('<li>' + text(prompt, 'recall prompt') + '</li>' for prompt in recall)
        basis = ''
        if kind == 'exam':
            if not isinstance(item.get('exam_basis'), str) or item['exam_basis'] not in BASES:
                raise ValueError('Exam expressions require a declared basis')
            if item['exam_basis'] != 'reference' and not any(source['module'] == 'exam-analysis' and source['path'] in refs for source in sources):
                raise ValueError('Exam requirements/past papers require exam-analysis feedback')
            basis = '<p class="source">' + BASES[item['exam_basis']] + ' · ' + text(item.get('exam_reference'), 'exam reference') + '</p>'
        prepared.append((item, item_title, source, summary, detail, prompts, basis))
    coverage = sections.validate(data, source_paths)
    by_id = {item['id']: item for item in items}
    cards, toc, glossary = [], [], []
    for index, (item, item_title, source, summary, detail, prompts, basis) in enumerate(prepared):
        topic_anchor = sections.anchor(item['id'])
        toc.append('<li><a href="#' + topic_anchor + '">' + item_title + '</a></li>')
        definition = sections.definition_html(item.get('definition'), fragment, text, base)
        steps = sections.steps_html(item.get('key_steps', []), by_id, fragment, text, base)
        aliases = ' '.join(item.get('aliases', []))
        text(aliases, 'aliases') if aliases else None
        card = '<article class="topic topic-' + item['kind'] + '" id="' + topic_anchor + '" data-aliases="' + escape(aliases, quote=True) + '">'
        # Preserve old numeric bookmarks while new references use a stable item-derived anchor.
        card += '<span id="topic-' + str(index + 1) + '" aria-hidden="true"></span>'
        card += '<header class="topic-heading"><h2>' + item_title + '</h2><span class="kind">' + KINDS[item['kind']] + '</span></header>'
        card += basis + '<div class="overview">' + summary + '</div>'
        if item.get('goal_html') is not None:
            card += '<div class="recall-goal">' + fragment(item['goal_html'], base) + '</div>'
        if prompts:
            card += '<aside class="recall"><p>先回忆，再展开核对 · 可跳过</p><ul>' + prompts + '</ul></aside>'
        hints = item.get('hints', [])
        if hints:
            panels = []
            for number, hint in enumerate(hints, 1):
                panels.append('<section class="hint-panel" id="' + topic_anchor + '-hint-' + str(number) + '" hidden><h3>' + text(hint['title'], 'hint title') + '</h3>' + fragment(hint['html'], base) + '</section>')
            card += '<div class="hint-set" hidden><div class="hint-panels" aria-live="polite">' + ''.join(panels) + '</div><button class="hint-reveal" aria-controls="' + ' '.join(topic_anchor + '-hint-' + str(number) for number in range(1, len(hints) + 1)) + '">看一条提示</button></div>'
        card += '<details class="explanation"><summary>展开详细解释 / 核对答案</summary><div class="detail">' + definition + steps + detail + '</div></details>'
        if item.get('related'):
            card += '<p class="related">相关概念：' + sections.links(item['related'], by_id, text) + '</p>'
        card += '<p class="source">来源：' + source + '</p></article>'
        cards.append(card)
        if item['kind'] in {'concept', 'term'}:
            if item.get('definition'):
                value = item['definition']
                label = text(value['term_zh'], 'glossary term')
                english = text(value['term_en'], 'glossary English term')
                glossary.append('<li><a href="#' + topic_anchor + '">' + label + '<small lang="en">' + english + '</small></a></li>')
            else:
                glossary.append('<li><a href="#' + topic_anchor + '">' + item_title + '</a></li>')
    links = data.get('lesson_links', [])
    if not isinstance(links, list):
        raise ValueError('lesson_links must be a list')
    lesson_links = []
    for link in links:
        if not isinstance(link, dict) or set(link) != {'title', 'path'}:
            raise ValueError('Lesson links require title and path')
        path = link['path']
        if not isinstance(path, str) or not re.fullmatch(r'[A-Za-z0-9_\-/]+\.html', path) or '..' in Path(path).parts or Path(path).is_absolute():
            raise ValueError('Lesson links must be local HTML paths inside notes')
        lesson_links.append('<li><a href="' + escape(path, quote=True) + '">' + text(link['title'], 'lesson link title') + '</a></li>')
    if lesson_links:
        cards.append('<section><h2>本章课笔记</h2><ul>' + ''.join(lesson_links) + '</ul></section>')
    pending = []
    for entry in coverage:
        text(entry['topic'], 'coverage topic')
        if 'reason' in entry:
            text(entry['reason'], 'coverage reason')
        if entry['status'] in {'omitted', 'unresolved'}:
            pending.append('<li><strong>' + text(entry['topic'], 'pending topic') + '</strong>：' + text(entry['reason'], 'pending reason') + '</li>')
    if pending:
        cards.append('<section class="pending"><h3>本次未展开的内容</h3><ul>' + ''.join(pending) + '</ul></section>')
    intro = '<div class="intro">' + fragment(data['intro_html'], base) + '</div>' if 'intro_html' in data else ''
    import base64
    script_hash = base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
    csp = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'sha256-" + script_hash + "'; base-uri 'none'; form-action 'none'"
    versions = json.dumps(sources, ensure_ascii=False)
    mapping = json.dumps(coverage, ensure_ascii=False)
    sidebar = '<aside class="sidebar"><details id="contents" open><summary>本页目录与术语</summary><nav aria-label="笔记目录"><ul>' + ''.join(toc) + '</ul></nav>'
    if glossary:
        sidebar += '<section class="glossary"><h3>术语索引</h3><ul>' + ''.join(glossary) + '</ul></section>'
    sidebar += '</details></aside>'
    controls = '<div class="controls"><div class="mode-switch" role="group" aria-label="阅读模式"><button id="reading-mode" aria-pressed="true">阅读</button><button id="recall-mode" aria-pressed="false">回忆</button></div><button id="print">打印 / 保存 PDF</button></div>'
    search = '<details id="find-tools" class="find-tools" open><summary>查找与阅读选项</summary><div class="search-row"><label for="note-search">查找知识点</label><input id="note-search" type="search" placeholder="中文、英文术语或正文关键词" autocomplete="off"/><p id="search-status" class="search-status" role="status" aria-live="polite"></p></div><div class="document-actions"><button id="expand">展开全部解释</button><button id="collapse">收起解释</button></div></details>'
    return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="' + escape(csp, quote=True) + '"><meta name="feedback-versions" content="' + escape(versions, quote=True) + '"><meta name="note-coverage" content="' + escape(mapping, quote=True) + '"><title>' + title + '</title><style>' + CSS + '</style></head><body data-mode="reading"><main class="notebook"><header class="note-header"><h1>' + title + '</h1><p class="scope">' + scope + '</p>' + intro + controls + search + '</header><div class="layout">' + sidebar + '<div class="content">' + ''.join(cards) + '<footer>可离线阅读。打印时会展开全部详细解释。</footer></div></div></main><script>' + SCRIPT + '</script></body></html>'


def publish(root, relative, expected, data, html, lock_timeout=2.0, *, input_path=None, input_sha256=None):
    records.check_role('notes', relative)
    if Path(relative).suffix != '.html':
        raise ValueError('Rendered note destination must be HTML')
    if (input_path is None) != (input_sha256 is None):
        raise ValueError('Note input path and SHA256 must be supplied together')
    if input_sha256 is not None and (not isinstance(input_sha256, str) or not re.fullmatch('[0-9a-f]{64}', input_sha256)):
        raise ValueError('Note input requires its captured SHA256')
    root, target = records.target_path(root, relative)
    if not root.is_dir():
        raise ValueError('An existing course record root is required')
    sources = source_list(data)
    if isinstance(data, dict) and type(data.get('schema_version')) is int and data['schema_version'] == 3:
        lecture_renderer().validate_for_publish(data, source_list, text, sections, helper, has_raw_math)
    else:
        sections.validate(data, {source['path'] for source in sources})
    with records.course_lock(root, lock_timeout):
        records.check_pending(root)
        if input_path is not None:
            try:
                current_input = Path(input_path).read_bytes()
            except OSError as exc:
                raise ValueError('Note input is unavailable; re-read the saved JSON and rebuild') from exc
            if records.digest(current_input) != input_sha256:
                raise ValueError('Stale note input; re-read the saved JSON and rebuild before publishing')
        _, target = records.target_path(root, relative)
        previous = target.read_bytes() if target.exists() else None
        if records.digest(previous) != expected:
            raise ValueError('Stale note version; re-read and merge manual changes')
        for source in sources:
            _, origin = records.target_path(root, source['path'])
            actual = records.digest(origin.read_bytes() if origin.exists() else None)
            if actual != source['sha256']:
                raise ValueError('Stale feedback at ' + source['path'] + '; re-read before compiling notes')
        content = html.encode('utf-8')
        if previous == content:
            return {'path': relative, 'sha256': records.digest(content), 'changed': False, 'backup': None}
        backup = records.backup_record(root, target, previous)
        records.atomic_write(target, content)
        if target.read_bytes() != content:
            raise OSError('Note read-back verification failed')
        return {'path': relative, 'sha256': records.digest(content), 'changed': True, 'backup': backup}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='Internal module draft, not a student input form')
    parser.add_argument('--output', help='New .html scratch file outside shared records; existing paths are refused')
    parser.add_argument('--root', help='Existing course record root')
    parser.add_argument('--path', help='Course-relative notes HTML path')
    parser.add_argument('--expected', help='Destination SHA or absent')
    parser.add_argument('--lock-timeout', type=float, default=2.0)
    args = parser.parse_args()
    try:
        source = Path(args.input)
        if args.root is not None:
            if args.output or args.path is None or args.expected is None:
                raise ValueError('Protected notes require --root --path --expected and no --output')
            destination = Path(args.root) / args.path
        else:
            if not args.output or args.path is not None or args.expected is not None:
                raise ValueError('Use --output for a preview, or the full protected-output options')
            destination = Path(args.output)
        if source.resolve() == destination.resolve() or (destination.exists() and source.samefile(destination)):
            raise ValueError('Output must not overwrite source records')
        source = source.resolve()
        input_bytes = source.read_bytes()
        data = json.loads(input_bytes.decode('utf-8'))
        html = render(data, source.parent)
        if args.root is not None:
            # Root-relative lesson index paths must work from any notes subdirectory.
            prefix = '../' * (len(Path(args.path).parts) - 2)
            for link in data.get('lesson_links', []):
                html = html.replace('href="' + link['path'] + '"', 'href="' + prefix + link['path'] + '"')
            result = publish(args.root, args.path, args.expected, data, html, args.lock_timeout,
                             input_path=source, input_sha256=records.digest(input_bytes))
        else:
            records.write_preview(destination, html.encode('utf-8'), '.html')
            result = {'path': str(destination), 'preview': True}
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, UnicodeError, TypeError, KeyError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
