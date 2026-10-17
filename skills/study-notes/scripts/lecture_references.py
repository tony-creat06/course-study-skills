"""Strict, source-bound terminology and equation references for lecture notes.

Authored placeholders are replaced with opaque text before the shared fragment
sanitizer runs. Only this registry can then inject generated anchors and links;
no user-authored IDs, classes or browser behaviors are admitted by the sanitizer.
"""
import hashlib
from html import escape
import secrets
import xml.etree.ElementTree as ET

MATH_NS = 'http://www.w3.org/1998/Math/MathML'
TERM_REQUIRED = {'id', 'term_zh', 'term_en', 'meaning_html', 'section_id', 'source_refs'}
TERM_FIELDS = TERM_REQUIRED | {'symbol_html', 'units_html', 'conditions_html', 'aliases'}
EQUATION_REQUIRED = {'id', 'title', 'section_id', 'source_refs', 'math_html'}
EQUATION_FIELDS = EQUATION_REQUIRED | {'conditions_html'}
INLINE_TAGS = {'p', 'span', 'a', 'strong', 'em', 'b', 'i', 'h3', 'h4'}


def anchor(kind, identity):
    return kind + '-' + hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20]


def local_tag(tag):
    if tag.startswith('{' + MATH_NS + '}'):
        return tag.split('}', 1)[1]
    if '}' in tag or ':' in tag:
        raise ValueError('Unsupported XML namespace')
    return tag


def parse_fragment(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Note fragments must be nonempty strings')
    try:
        return ET.fromstring('<fragment>' + value + '</fragment>')
    except ET.ParseError as exc:
        raise ValueError('Use well-formed note fragments') from exc


def serialize_fragment(wrapper):
    """Serialize only the interior, keeping MathML namespaces valid for the sanitizer."""
    return escape(wrapper.text or '') + ''.join(ET.tostring(child, encoding='unicode') for child in wrapper)


class Registry:
    def __init__(self, data, sections, source_paths, base, fragment, text, section_anchor):
        self.base, self.safe_fragment, self.text = base, fragment, text
        self.section_anchor = section_anchor
        self.sections = {}
        for section in sections:
            if not isinstance(section, dict) or not isinstance(section.get('id'), str):
                raise ValueError('Reference sections require a valid section id')
            text(section['id'], 'section id')
            if section['id'] in self.sections:
                raise ValueError('Duplicate section id')
            refs = section.get('source_refs')
            if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in source_paths for ref in refs):
                raise ValueError('source_refs must refer to declared module feedback')
            self.sections[section['id']] = section
        self.terms, self.equations = {}, {}
        self.placements = {}
        for field, required, allowed, destination in (
                ('terms', TERM_REQUIRED, TERM_FIELDS, self.terms),
                ('equations', EQUATION_REQUIRED, EQUATION_FIELDS, self.equations)):
            values = data.get(field, [])
            if not isinstance(values, list):
                raise ValueError(field + ' must be a list')
            for value in values:
                if not isinstance(value, dict) or not required <= set(value) or set(value) - allowed:
                    raise ValueError('Unsupported or missing ' + field + ' fields')
                identity = value['id']
                text(identity, field + ' id')
                if identity in destination:
                    raise ValueError('Duplicate ' + field + ' id')
                section_id = value['section_id']
                if not isinstance(section_id, str) or section_id not in self.sections:
                    raise ValueError(field + ' section_id must identify an included section')
                refs = value['source_refs']
                if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in source_paths for ref in refs):
                    raise ValueError(field + ' source_refs must identify declared feedback')
                if not set(refs) & set(self.sections[section_id]['source_refs']):
                    raise ValueError(field + ' and its section must share feedback provenance')
                item = dict(value)
                item['anchor'] = anchor('term' if field == 'terms' else 'eq', identity)
                if field == 'terms':
                    item['label'] = text(value['term_zh'], 'Chinese term')
                    item['english'] = text(value['term_en'], 'English term')
                    aliases = value.get('aliases', [])
                    if not isinstance(aliases, list):
                        raise ValueError('Term aliases must be a string list')
                    for alias in aliases:
                        text(alias, 'term alias')
                    for key in ('meaning_html', 'symbol_html', 'units_html', 'conditions_html'):
                        if key in value:
                            item[key] = fragment(value[key], base)
                else:
                    item['title'] = text(value['title'], 'equation title')
                    math = parse_fragment(value['math_html'])
                    if len(math) != 1 or (math.text or '').strip() or (math[0].tail or '').strip() or local_tag(math[0].tag) != 'math' or math[0].get('display') != 'block':
                        raise ValueError('math_html must contain exactly one display=block MathML math element')
                    item['math_html'] = fragment(value['math_html'], base)
                    if 'conditions_html' in value:
                        item['conditions_html'] = fragment(value['conditions_html'], base)
                    item['number'] = len(destination) + 1
                    self.placements[identity] = 0
                destination[identity] = item

    def _equation_html(self, item):
        label = '（' + str(item['number']) + '）'
        result = '<div class="numbered-equation" id="' + item['anchor'] + '" tabindex="-1" aria-label="' + item['title'] + '，式' + label + '">' + item['math_html']
        result += '<span class="eq-label">' + label + '</span></div>'
        if 'conditions_html' in item:
            result += '<div class="equation-conditions"><strong>成立条件：</strong>' + item['conditions_html'] + '</div>'
        return result

    def fragment(self, value, section_id, field):
        wrapper = parse_fragment(value)
        if not any(local_tag(node.tag) in {'note-equation', 'note-ref'} for node in wrapper.iter()):
            # Keep the exact legacy sanitizer output when there is no placeholder.
            return self.safe_fragment(value, self.base)
        replacements = {}

        def replace_children(parent, ancestors):
            for node in list(parent):
                tag = local_tag(node.tag)
                if tag not in {'note-equation', 'note-ref'}:
                    replace_children(node, ancestors + [tag])
                    continue
                if node.tag != tag:
                    raise ValueError('Note reference placeholders cannot use XML namespaces')
                if any(name in {'math', 'code', 'pre', 'a'} for name in ancestors):
                    raise ValueError('Note references cannot be inside math, code or links')
                if len(node) or (node.text or '').strip():
                    raise ValueError('Note reference placeholders must be empty')
                if tag == 'note-equation':
                    if set(node.attrib) != {'ref'}:
                        raise ValueError('note-equation requires only ref')
                    identity = node.get('ref')
                    if identity not in self.equations:
                        raise ValueError('Unknown equation placement reference')
                    item = self.equations[identity]
                    if field != 'body_html' or item['section_id'] != section_id:
                        raise ValueError('Canonical equations must appear in their matching section body_html')
                    if any(name in INLINE_TAGS for name in ancestors):
                        raise ValueError('Block equation placeholders cannot be inside inline prose')
                    self.placements[identity] += 1
                    if self.placements[identity] != 1:
                        raise ValueError('Every canonical equation must be placed exactly once')
                    html = self._equation_html(item)
                else:
                    if set(node.attrib) != {'kind', 'ref'} or node.get('kind') not in {'equation', 'term'}:
                        raise ValueError('note-ref requires kind=equation|term and ref')
                    registry = self.equations if node.get('kind') == 'equation' else self.terms
                    identity = node.get('ref')
                    if identity not in registry:
                        raise ValueError('Unknown note reference')
                    item = registry[identity]
                    label = '式（' + str(item['number']) + '）' if node.get('kind') == 'equation' else item['label'] + ' · ' + item['english']
                    html = '<a href="#' + item['anchor'] + '" data-note-target="' + item['anchor'] + '">' + label + '</a>'
                token = 'NOTEREF' + secrets.token_hex(24)
                while token in value:
                    token = 'NOTEREF' + secrets.token_hex(24)
                replacements[token] = html
                index = list(parent).index(node)
                tail = node.tail or ''
                parent.remove(node)
                if index:
                    previous = parent[index - 1]
                    previous.tail = (previous.tail or '') + token + tail
                else:
                    parent.text = (parent.text or '') + token + tail

        replace_children(wrapper, [])
        rendered = self.safe_fragment(serialize_fragment(wrapper), self.base)
        for token, html in replacements.items():
            if rendered.count(token) != 1:
                raise ValueError('Reference placeholder did not survive strict fragment validation')
            rendered = rendered.replace(token, html)
        return rendered

    def finish(self):
        if any(count != 1 for count in self.placements.values()):
            raise ValueError('Every declared equation must be placed exactly once in its section body_html')

    def glossary_html(self):
        if not self.terms:
            return ''
        symbols = any('symbol_html' in item or 'units_html' in item for item in self.terms.values())
        conditions = any('conditions_html' in item for item in self.terms.values())
        html = '<section class="term-index" id="note-terms" tabindex="-1"><details><summary>术语与符号速查</summary><table><thead><tr><th scope="col" class="term-name">术语</th>'
        if symbols:
            html += '<th scope="col" class="term-symbol">符号与单位</th>'
        html += '<th scope="col" class="term-meaning">本章含义</th>'
        if conditions:
            html += '<th scope="col" class="term-condition">条件与范围</th>'
        html += '</tr></thead><tbody>'
        for item in self.terms.values():
            html += '<tr id="' + item['anchor'] + '" tabindex="-1"><th scope="row" class="term-name"><strong>' + item['label'] + '</strong><small lang="en">' + item['english'] + '</small></th>'
            if symbols:
                value = item.get('symbol_html', '')
                if 'units_html' in item:
                    value += '<div class="term-units">单位：' + item['units_html'] + '</div>'
                html += '<td class="term-symbol">' + (value or '—') + '</td>'
            html += '<td class="term-meaning">' + item['meaning_html'] + '<p><a href="#' + self.section_anchor(item['section_id']) + '" data-open-section="' + self.section_anchor(item['section_id']) + '">回到正文解释</a></p></td>'
            if conditions:
                html += '<td class="term-condition">' + item.get('conditions_html', '—') + '</td>'
            html += '</tr>'
        return html + '</tbody></table></details></section>'
