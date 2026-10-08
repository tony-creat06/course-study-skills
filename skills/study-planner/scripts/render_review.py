#!/usr/bin/env python3
"""Render completed-question records as an offline HTML document with native MathML."""
import argparse
import importlib.util
import base64
from html import escape
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

ATTEMPTS = {'independent_correct': '独立完成且正确', 'independent_incorrect': '独立尝试后需订正',
            'hinted': '使用提示后完成', 'partial': '部分完成', 'shown_solution': '已查看完整解析'}
HTML_TAGS = {'p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i', 'h3', 'h4',
             'table', 'thead', 'tbody', 'tr', 'td', 'th', 'code', 'pre', 'blockquote', 'span', 'div', 'img', 'a'}
MATH_TAGS = {'math', 'mrow', 'mi', 'mn', 'mo', 'mfrac', 'msup', 'msub', 'msubsup', 'msqrt', 'mroot',
             'mtext', 'mspace', 'mover', 'munder', 'munderover', 'mfenced', 'menclose', 'mtable', 'mtr', 'mtd', 'mpadded', 'mphantom'}
MATH_ATTRS = {'display', 'mathvariant', 'stretchy', 'symmetric', 'fence', 'separator', 'separators',
              'accent', 'accentunder', 'columnalign', 'rowalign', 'columnspacing', 'rowspacing', 'notation',
              'minsize', 'maxsize', 'linethickness', 'lspace', 'rspace', 'width', 'height', 'depth', 'open', 'close'}
HTML_ATTRS = {'img': {'src', 'alt', 'width', 'height'}, 'a': {'href', 'title'},
              'td': {'colspan', 'rowspan'}, 'th': {'colspan', 'rowspan', 'scope'}}
VOID = {'br', 'img'}
RAW_TEX = re.compile(r'\\(?:frac|sqrt|begin|end|partial|hbar|psi|lambda|alpha|beta|left|right)\b|\\[()\[\]]|\$[^$\n]+\$')


def image_data(value, base):
    relative = Path(value)
    if urlsplit(value).scheme or relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Images must be local paths beneath the input JSON folder')
    path = (base / relative).resolve()
    path.relative_to(base.resolve())
    data = path.read_bytes()
    if len(data) > 20 * 1024 * 1024:
        raise ValueError('Image exceeds 20 MB')
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        mime = 'image/png'
    elif data.startswith(b'\xff\xd8\xff'):
        mime = 'image/jpeg'
    elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        mime = 'image/webp'
    else:
        raise ValueError('Only PNG/JPEG/WebP image files are supported')
    return 'data:' + mime + ';base64,' + base64.b64encode(data).decode('ascii')


def local_tag(tag):
    if tag.startswith('{http://www.w3.org/1998/Math/MathML}'):
        return tag.split('}', 1)[1]
    if '}' in tag or ':' in tag:
        raise ValueError('Unsupported XML namespace')
    return tag


def render_fragment(fragment, base):
    if not isinstance(fragment, str) or not fragment.strip():
        raise ValueError('Question and solution fragments must be nonempty')
    try:
        wrapper = ET.fromstring('<fragment>' + fragment + '</fragment>')
    except ET.ParseError as exc:
        raise ValueError('Use well-formed fragments: close tags, <br/>, escape ampersands') from exc
    if not ''.join(wrapper.itertext()).strip() and not any(local_tag(n.tag) == 'img' for n in wrapper.iter()):
        raise ValueError('Question/solution fragment has no visible content')

    def text_node(value, code=False):
        if not code and RAW_TEX.search(value or ''):
            raise ValueError('Raw LaTeX detected: typeset it with MathML')
        return escape(value or '')

    def node(element, in_math=False, in_code=False):
        tag = local_tag(element.tag)
        math_mode = in_math or tag == 'math'
        code_mode = in_code or tag in {'code', 'pre'}
        if (math_mode and tag not in MATH_TAGS) or (not math_mode and tag not in HTML_TAGS):
            raise ValueError('Unsupported element: ' + tag)
        if tag in MATH_TAGS and not math_mode:
            raise ValueError('MathML elements must be inside <math>')
        allowed = MATH_ATTRS if math_mode else HTML_ATTRS.get(tag, set())
        attrs = {}
        for key, value in element.attrib.items():
            if key not in allowed:
                raise ValueError('Unsupported attribute: ' + key)
            attrs[key] = value
        if tag == 'math':
            attrs['xmlns'] = 'http://www.w3.org/1998/Math/MathML'
        if tag == 'img':
            if not attrs.get('src') or not attrs.get('alt', '').strip():
                raise ValueError('Images require src and meaningful alt text')
            attrs['src'] = image_data(attrs['src'], base)
        if tag == 'a':
            address = attrs.get('href', '')
            if urlsplit(address).scheme not in {'https', 'http'}:
                raise ValueError('Source links must use http(s)')
            attrs['rel'] = 'noopener noreferrer'
        attr_text = ''.join(' ' + key + '="' + escape(value, quote=True) + '"' for key, value in attrs.items())
        if tag in VOID:
            if len(element) or (element.text or '').strip():
                raise ValueError('Void elements cannot contain children')
            return '<' + tag + attr_text + '>'
        inner = text_node(element.text, code_mode)
        for child in element:
            inner += node(child, math_mode, code_mode) + text_node(child.tail, code_mode)
        rendered = '<' + tag + attr_text + '>' + inner + '</' + tag + '>'
        if tag == 'math' and attrs.get('display') == 'block':
            return '<div class="equation">' + rendered + '</div>'
        return rendered

    result = text_node(wrapper.text)
    for child in wrapper:
        result += node(child) + text_node(child.tail)
    return result


CSS = '''
:root {color-scheme:light; --ink:#182536; --muted:#526275; --line:#d5dfe7; --accent:#1a675e;}
* {box-sizing:border-box} body {margin:0;background:#f1f5f7;color:var(--ink);font:17px/1.8 system-ui,-apple-system,"PingFang SC",sans-serif}
main {max-width:960px;margin:auto;padding:48px 28px 80px} header {margin-bottom:30px} h1 {font-size:2rem;line-height:1.3;margin:8px 0 12px}
h2 {font-size:1.45rem;line-height:1.4;margin:0 0 12px} h3 {font-size:1.1rem;margin:24px 0 8px} p {margin:10px 0}
.eyebrow {color:var(--accent);font-size:14px;font-weight:700;letter-spacing:.08em} .muted,.source {color:var(--muted);font-size:14px;overflow-wrap:anywhere}
article {background:white;border:1px solid var(--line);border-radius:16px;padding:30px;margin:24px 0;box-shadow:0 5px 20px #16334408}
.badge {display:inline-block;background:#e9f3ef;color:#235b50;padding:3px 10px;border-radius:6px;font-size:13px}
.solution {border-top:1px solid var(--line);margin-top:24px;padding-top:8px}.personal {background:#f2f6fa;border-left:3px solid #9bb4cb;padding:14px 18px;margin-top:24px;white-space:pre-wrap}
math {font-size:1.12em} math[display="block"] {margin:0 auto} .equation {margin:20px 0;overflow-x:auto;overflow-y:hidden;padding:8px 0}
img {display:block;max-width:100%;height:auto;margin:18px auto} table {border-collapse:collapse;max-width:100%;display:block;overflow-x:auto;margin:18px 0}
th,td {padding:9px 12px;border:1px solid var(--line);text-align:left} pre {overflow-x:auto;background:#f3f6f8;padding:16px} code {font-size:.9em}
a {color:var(--accent)} footer {font-size:13px;color:var(--muted)}
@media(max-width:600px) {body {font-size:16px} main {padding:26px 14px 50px} article {padding:20px 16px;border-radius:10px} h1 {font-size:1.6rem} h2 {font-size:1.25rem}}
@media print {body {background:white} main {max-width:none;padding:0} article {box-shadow:none;break-inside:auto} h2,h3 {break-after:avoid} .personal {print-color-adjust:exact}}
'''


def render(data, base):
    for key in ('course', 'unit'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError('course and unit are required')
    items = data.get('items')
    if not isinstance(items, list) or not items:
        raise ValueError('items must contain actually attempted questions')
    seen, cards = set(), []
    for item in items:
        for key in ('id', 'title', 'source', 'personal_review'):
            if not isinstance(item.get(key), str) or (key != 'personal_review' and not item[key].strip()):
                raise ValueError('Missing item field: ' + key)
        if item['id'] in seen:
            raise ValueError('Duplicate question id')
        seen.add(item['id'])
        if item.get('attempt') not in ATTEMPTS:
            raise ValueError('Do not include future/unattempted questions')
        question = render_fragment(item.get('question_html'), base)
        solution = render_fragment(item.get('solution_html'), base)
        personal = item['personal_review'].strip()
        card = '<article><h2>' + escape(item['title']) + '</h2><span class="badge">' + ATTEMPTS[item['attempt']] + '</span>'
        card += '<p class="source">来源：' + escape(item['source']) + '</p><section><h3>完整题目</h3>' + question + '</section>'
        card += '<section class="solution"><h3>完整解析</h3>' + solution + '</section>'
        if personal:
            card += '<aside class="personal"><strong>本题复盘</strong>\n' + escape(personal) + '</aside>'
        cards.append(card + '</article>')
    title = escape(data['course'] + ' · ' + data['unit'])
    notice = escape(str(data.get('notice', '记录中的“已看解析”“提示后完成”与独立完成分别保留。')))
    return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + title + '</title><style>' + CSS + '</style></head><body><main><header><div class="eyebrow">学习题解记录</div><h1>' + title + '</h1><p class="muted">' + notice + '</p></header>' + ''.join(cards) + '<footer>公式使用浏览器原生 MathML；图片已嵌入。本文档可离线阅读与打印。</footer></main></body></html>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', help='Scratch output outside shared course records')
    parser.add_argument('--root', help='Shared course root for version-checked output')
    parser.add_argument('--path', help='Course-relative output path')
    parser.add_argument('--expected', help='SHA from course_records.py read, or absent')
    args = parser.parse_args()
    try:
        protected = args.root is not None
        if protected:
            if args.output or args.path is None or args.expected is None:
                raise ValueError('Protected output requires --root --path --expected and no --output')
            destination = Path(args.root) / args.path
        else:
            if not args.output or args.path is not None or args.expected is not None:
                raise ValueError('Use --output for scratch output, or the full protected-output options')
            destination = Path(args.output)
        source = Path(args.input)
        if source.resolve() == destination.resolve():
            raise ValueError('Output must not overwrite source records')
        output = render(json.loads(source.read_text(encoding='utf-8')), source.resolve().parent)
        if protected:
            module_path = Path(__file__).with_name('course_records.py')
            spec = importlib.util.spec_from_file_location('course_records', module_path)
            records = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(records)
            saved = records.write_record(args.root, args.path, 'main', args.expected, output)
            print(json.dumps(dict(saved, items=output.count('<article>')), ensure_ascii=False))
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.review-', dir=destination.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(output)
            os.replace(name, destination)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        print(json.dumps({'items': output.count('<article>'), 'output': str(destination)}, ensure_ascii=False))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
