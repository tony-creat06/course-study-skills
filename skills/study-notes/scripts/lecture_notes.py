"""Render version 3 notes as continuous lectures with optional revision views."""
import base64
import hashlib
import importlib.util
from html import escape
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


ASSETS = Path(__file__).resolve().parents[1] / 'assets'
ROOT_FIELDS = {'schema_version', 'course', 'unit', 'kind', 'scope', 'sources',
               'items', 'lesson_links', 'coverage', 'intro_html', 'terms', 'equations'}
REQUIRED_ITEM_FIELDS = {'id', 'title', 'source', 'source_refs', 'body_html', 'summary_html'}
ITEM_FIELDS = REQUIRED_ITEM_FIELDS | {'aliases', 'related', 'recall', 'hints',
                                     'answer_html', 'supplement_html', 'supplement_title',
                                     'exam_basis', 'exam_reference'}
BASES = {'requirement': '课程明确要求', 'past-paper': '真题中出现过', 'reference': '自拟参考表达'}


def prepare(data, base, source_list, fragment, text, content):
    """Validate the entire v3 draft before rendering or entering a write lock."""
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 3:
        raise ValueError('Lecture notes require schema_version 3')
    if set(data) - ROOT_FIELDS:
        raise ValueError('Unsupported note metadata; learner evidence belongs to the planner')
    if not isinstance(data.get('kind'), str) or data['kind'] not in {'lesson', 'chapter', 'course'}:
        raise ValueError('Version 3 kind must be lesson, chapter or course')
    title = text(data.get('course'), 'course') + ' · ' + text(data.get('unit'), 'unit')
    scope = text(data.get('scope'), 'scope')
    sources = source_list(data)
    source_paths = {source['path'] for source in sources}
    items = data.get('items')
    if not isinstance(items, list) or not items:
        raise ValueError('items must contain taught sections')
    references = None
    if 'terms' in data or 'equations' in data:
        spec = importlib.util.spec_from_file_location('lecture_references', Path(__file__).with_name('lecture_references.py'))
        reference_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reference_module)
        references = reference_module.Registry(data, items, source_paths, base, fragment, text, content.anchor)

    def section_fragment(value, section_id, field):
        return references.fragment(value, section_id, field) if references else fragment(value, base)

    seen, prepared = set(), []
    for item in items:
        if not isinstance(item, dict) or not REQUIRED_ITEM_FIELDS <= set(item) or set(item) - ITEM_FIELDS:
            raise ValueError('Lecture sections require id/title/source/source_refs/body_html/summary_html')
        text(item['id'], 'section id')
        if item['id'] in seen:
            raise ValueError('Duplicate section id')
        seen.add(item['id'])
        item_title = text(item['title'], 'section title')
        source = text(item['source'], 'source locator')
        refs = item['source_refs']
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in source_paths for ref in refs):
            raise ValueError('source_refs must refer to declared module feedback')
        body = section_fragment(item['body_html'], item['id'], 'body_html')
        summary = section_fragment(item['summary_html'], item['id'], 'summary_html')
        recall = item.get('recall', [])
        if not isinstance(recall, list):
            raise ValueError('recall must be a list')
        prompts = [text(prompt, 'recall prompt') for prompt in recall]
        for key in ('aliases', 'related'):
            values = item.get(key, [])
            if not isinstance(values, list):
                raise ValueError(key + ' must be a string list')
            for value in values:
                text(value, key)
        hints = item.get('hints', [])
        if not isinstance(hints, list):
            raise ValueError('hints must contain title/html objects')
        hint_panels = []
        for hint in hints:
            if not isinstance(hint, dict) or set(hint) != {'title', 'html'}:
                raise ValueError('hints must contain title/html objects')
            hint_panels.append((text(hint['title'], 'hint title'), section_fragment(hint['html'], item['id'], 'hint_html')))
        answer = section_fragment(item['answer_html'], item['id'], 'answer_html') if 'answer_html' in item else ''
        if (hint_panels or answer) and not prompts:
            raise ValueError('Hints and reference answers require a recall prompt')
        supplement = section_fragment(item['supplement_html'], item['id'], 'supplement_html') if 'supplement_html' in item else ''
        if 'supplement_title' in item and not supplement:
            raise ValueError('supplement_title requires supplement_html')
        supplement_title = text(item.get('supplement_title', '补充说明'), 'supplement title')
        basis = ''
        if 'exam_basis' in item or 'exam_reference' in item:
            basis_key = item.get('exam_basis')
            if not isinstance(basis_key, str) or basis_key not in BASES:
                raise ValueError('Exam expressions require a declared basis')
            if basis_key != 'reference' and not any(source['module'] == 'exam-analysis' and source['path'] in refs for source in sources):
                raise ValueError('Exam requirements/past papers require exam-analysis feedback')
            basis = '<p class="source-note">' + BASES[basis_key] + ' · ' + text(item.get('exam_reference'), 'exam reference') + '</p>'
        search_aliases = list(item.get('aliases', []))
        if references:
            for term in references.terms.values():
                if term['section_id'] == item['id']:
                    search_aliases.extend([term['term_zh'], term['term_en'], *term.get('aliases', [])])
        prepared.append(dict(item=item, title=item_title, source=source, body=body, search_aliases=search_aliases,
                             summary=summary, prompts=prompts, hints=hint_panels,
                             answer=answer, supplement=supplement,
                             supplement_title=supplement_title, basis=basis))
    if not isinstance(data.get('coverage'), list) or not data['coverage']:
        raise ValueError('Version 3 notes require a feedback-topic coverage inventory')
    coverage = content.validate(data, source_paths)
    for entry in coverage:
        for key in ('id', 'topic', 'reason', 'source_location'):
            if key in entry:
                text(entry[key], 'coverage ' + key)
    lesson_links = data.get('lesson_links', [])
    if not isinstance(lesson_links, list):
        raise ValueError('lesson_links must be a list')
    links = []
    for link in lesson_links:
        if not isinstance(link, dict) or set(link) != {'title', 'path'}:
            raise ValueError('Lesson links require title and path')
        path = link['path']
        if not isinstance(path, str) or not re.fullmatch(r'[A-Za-z0-9_\-/]+\.html', path) or '..' in Path(path).parts or Path(path).is_absolute():
            raise ValueError('Lesson links must be local HTML paths inside notes')
        links.append('<li><a href="' + escape(path, quote=True) + '">' + text(link['title'], 'lesson link title') + '</a></li>')
    intro = section_fragment(data['intro_html'], None, 'intro_html') if 'intro_html' in data else ''
    if references:
        references.finish()
    return dict(title=title, scope=scope, sources=sources, coverage=coverage,
                sections=prepared, lesson_links=links, intro=intro,
                terminology=references.glossary_html() if references else '')


def validate_for_publish(data, source_list, text, content, helper, raw_math):
    """Check all v3 fields and safe markup without needing the original asset folder.

    Embedded images receive the same byte checks as rendering. The existing API
    has no asset base path, so legacy local files retain syntax-only validation
    here; rendering resolves and checks those files before embedding them.
    """
    validator = helper('lecture_publish_fragments', 'render_review.py')
    validator.HTML_TAGS.update({'figure', 'figcaption', 'caption'})
    validator.MATH_ATTRS.add('form')
    for tag in validator.HTML_TAGS:
        validator.HTML_ATTRS[tag] = validator.HTML_ATTRS.get(tag, set()) | {'lang'}

    image_spec = importlib.util.spec_from_file_location('publish_note_images', Path(__file__).with_name('note_images.py'))
    images = importlib.util.module_from_spec(image_spec)
    image_spec.loader.exec_module(images)

    def image_path(value, _base):
        return images.validate_reference(value)

    validator.image_data = image_path

    def check_fragment(value, base):
        rendered = validator.render_fragment(value, base)
        wrapper = ET.fromstring('<fragment>' + value + '</fragment>')
        for element in wrapper.iter():
            if 'form' in element.attrib and (validator.local_tag(element.tag) != 'mo' or element.attrib['form'] not in {'prefix', 'infix', 'postfix'}):
                raise ValueError('MathML form is limited to prefix/infix/postfix on mo')
        if raw_math(''.join(wrapper.itertext())):
            raise ValueError('Raw LaTeX detected, including code blocks; use MathML')
        return rendered

    prepare(data, Path('.'), source_list, check_fragment, text, content)


def render(data, base, source_list, fragment, text, content):
    prepared = prepare(data, base, source_list, fragment, text, content)
    by_id = {section['item']['id']: section for section in prepared['sections']}
    full, summaries, recall_tasks, toc = [], [], [], []

    def back_link(anchor, label='返回正文'):
        return '<a href="#' + anchor + '" data-open-section="' + anchor + '">' + label + '</a>'

    for section_number, section in enumerate(prepared['sections'], 1):
        item = section['item']
        anchor = content.anchor(item['id'])
        toc.append('<li><a href="#' + anchor + '" data-recall-label="第 ' + str(section_number) + ' 节">' + section['title'] + '</a></li>')
        aliases = escape(' '.join(section['search_aliases']), quote=True)
        body = '<section class="note-section" id="' + anchor + '" data-search-aliases="' + aliases + '"><h2>' + section['title'] + '</h2>'
        body += section['basis'] + section['body']
        if section['supplement']:
            body += '<details class="supplement"><summary>' + section['supplement_title'] + '</summary><div>' + section['supplement'] + '</div></details>'
        if item.get('related'):
            related = '、'.join(back_link(content.anchor(ref), by_id[ref]['title']) for ref in item['related'])
            body += '<p class="source-note">相关小节：' + related + '</p>'
        body += '<p class="source-note">来源：' + section['source'] + '</p></section>'
        full.append(body)
        summaries.append('<section class="summary-section"><h2>' + section['title'] + '</h2>' + section['summary'] + '<p>' + back_link(anchor, '阅读这一节的完整解释') + '</p></section>')
        if section['prompts']:
            # A neutral label keeps an answer-bearing section title out of recall prompts.
            task = '<section class="recall-task"><h2>回忆 ' + str(len(recall_tasks) + 1) + '</h2><ol>' + ''.join('<li>' + prompt + '</li>' for prompt in section['prompts']) + '</ol>'
            if section['hints']:
                hint_ids = []
                task += '<div class="hint-set">'
                for hint_number, (hint_title, hint_html) in enumerate(section['hints'], 1):
                    hint_id = anchor + '-hint-' + str(hint_number)
                    hint_ids.append(hint_id)
                    task += '<div class="hint" id="' + hint_id + '" hidden><h3>' + hint_title + '</h3>' + hint_html + '</div>'
                task += '<button type="button" data-reveal-hint="' + hint_ids[0] + '" aria-controls="' + ' '.join(hint_ids) + '" aria-expanded="false">看一条提示</button></div>'
            if section['answer']:
                task += '<details class="answer"><summary>核对参考答案</summary><div>' + section['answer'] + '</div></details>'
            task += '<p>' + back_link(anchor, '回到正文核对') + '</p></section>'
            recall_tasks.append(task)
    if prepared['terminology']:
        full.append(prepared['terminology'])
        toc.append('<li><a href="#note-terms" data-note-target="note-terms">术语与符号速查</a></li>')
    if prepared['lesson_links']:
        heading = {'lesson': '相关笔记', 'chapter': '本章课笔记', 'course': '章节笔记索引'}[data['kind']]
        full.append('<section class="note-index"><h2>' + heading + '</h2><ul>' + ''.join(prepared['lesson_links']) + '</ul></section>')
    pending = ['<li><strong>' + text(entry['topic'], 'pending topic') + '</strong>：' + text(entry['reason'], 'pending reason') + '</li>'
               for entry in prepared['coverage'] if entry['status'] in {'omitted', 'unresolved'}]
    if pending:
        full.append('<section class="pending"><h2>本次未展开的内容</h2><ul>' + ''.join(pending) + '</ul></section>')
    recall_html = ''.join(recall_tasks) or '<p>本次没有单独整理回忆题。可阅读正文或切换到精简视图复习。</p>'
    css = (ASSETS / 'lecture.css').read_text(encoding='utf-8')
    script = (ASSETS / 'lecture.js').read_text(encoding='utf-8')
    script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'sha256-" + script_hash + "'; base-uri 'none'; form-action 'none'"
    versions = json.dumps(prepared['sources'], ensure_ascii=False)
    mapping = json.dumps(prepared['coverage'], ensure_ascii=False)
    intro = '<div class="intro">' + prepared['intro'] + '</div>' if prepared['intro'] else ''
    controls = '<div class="toolbar"><div class="view-switch" role="group" aria-label="阅读视图"><button type="button" data-view-choice="full" aria-pressed="true">完整正文</button><button type="button" data-view-choice="summary" aria-pressed="false">精简复习</button><button type="button" data-view-choice="recall" aria-pressed="false">回忆</button></div><button type="button" id="print-notes">打印 / 保存 PDF</button></div>'
    search = '<details id="reading-tools"><summary>查找正文</summary><label for="chapter-search">关键词</label><input id="chapter-search" type="search" placeholder="中文、英文术语或正文关键词" autocomplete="off"/><p id="search-status" role="status" aria-live="polite">输入关键词筛选正文小节；清空搜索可恢复全文。</p></details>'
    sidebar = '<aside class="sidebar"><details id="chapter-contents" open><summary>正文目录</summary><nav id="chapter-nav" aria-label="笔记目录"><ul>' + ''.join(toc) + '</ul></nav></details></aside>'
    panels = '<div id="chapter-content"><article class="view-panel" data-panel="full">' + ''.join(full) + '</article><div class="view-panel" data-panel="summary" hidden>' + ''.join(summaries) + '</div><div class="view-panel" data-panel="recall" hidden>' + recall_html + '</div></div>'
    return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="' + escape(csp, quote=True) + '"><meta name="feedback-versions" content="' + escape(versions, quote=True) + '"><meta name="note-coverage" content="' + escape(mapping, quote=True) + '"><title>' + prepared['title'] + '</title><style>' + css + '</style></head><body data-view="full"><a class="skip-link" href="#chapter-content">跳到笔记正文</a><main class="notebook"><header class="chapter-header"><h1>' + prepared['title'] + '</h1><p class="subtitle">' + prepared['scope'] + '</p>' + intro + controls + search + '</header><div class="page-layout">' + sidebar + panels + '</div><footer class="chapter-footer"><p>可离线阅读。打印时包含完整正文和补充说明；结束打印后恢复原来的阅读视图。</p></footer></main><script>' + script + '</script></body></html>'
