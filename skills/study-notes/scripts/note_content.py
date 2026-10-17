"""Validate note-only content mappings and render optional academic sections."""
import hashlib
from html import escape


def anchor(item_id):
    return 'topic-' + hashlib.sha256(item_id.encode('utf-8')).hexdigest()[:20]


def validate(data, source_paths):
    items = data['items']
    ids = {item['id'] for item in items}
    for item in items:
        hints = item.get('hints', [])
        if not isinstance(hints, list) or any(not isinstance(h, dict) or set(h) != {'title', 'html'} for h in hints):
            raise ValueError('hints must contain title/html objects')
        for key in ('aliases', 'related'):
            values = item.get(key, [])
            if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError(key + ' must be a string list')
        if any(v not in ids or v == item['id'] for v in item.get('related', [])):
            raise ValueError('Related concepts must reference another item in this self-contained note')
        steps = item.get('key_steps', [])
        if not isinstance(steps, list):
            raise ValueError('key_steps must be a list')
        for step in steps:
            required = {'title', 'action_html', 'why_html'}
            allowed = required | {'conditions_html', 'prerequisites'}
            if not isinstance(step, dict) or not required <= set(step) or set(step) - allowed:
                raise ValueError('Key steps require title, action_html and why_html')
            refs = step.get('prerequisites', [])
            if not isinstance(refs, list) or any(not isinstance(r, str) or r not in ids or r == item['id'] for r in refs):
                raise ValueError('Step prerequisites must reference another included topic')
        definition = item.get('definition')
        if definition is not None:
            required = {'term_zh', 'term_en', 'meaning_html', 'definition_en_html'}
            allowed = required | {'conditions_html', 'symbols_html', 'contrast_html', 'command', 'explain_html'}
            if not isinstance(definition, dict) or not required <= set(definition) or set(definition) - allowed:
                raise ValueError('Definitions require Chinese/English terms, meaning and English definition')
            if 'command' in definition and (not isinstance(definition['command'], str) or definition['command'] not in {'state', 'define', 'explain'}):
                raise ValueError('Definition command must be state, define or explain')
    coverage = data.get('coverage')
    if coverage is None and data['schema_version'] == 1:
        return []
    if not isinstance(coverage, list) or not coverage:
        raise ValueError('Version 2 notes require a feedback-topic coverage inventory')
    seen, covered = set(), set()
    for entry in coverage:
        required = {'id', 'topic', 'source_refs', 'status', 'item_ids'}
        if not isinstance(entry, dict) or not required <= set(entry) or set(entry) - (required | {'reason', 'source_location'}):
            raise ValueError('Coverage entries require id/topic/source_refs/status/item_ids')
        for field in ('id', 'topic'):
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise ValueError('Coverage ' + field + ' must be nonempty')
        for field in ('reason', 'source_location'):
            if field in entry and (not isinstance(entry[field], str) or not entry[field].strip()):
                raise ValueError('Coverage ' + field + ' must be nonempty when supplied')
        if entry['id'] in seen:
            raise ValueError('Duplicate feedback-topic coverage id')
        seen.add(entry['id'])
        refs, targets = entry['source_refs'], entry['item_ids']
        if not isinstance(refs, list) or not refs or any(not isinstance(r, str) or r not in source_paths for r in refs):
            raise ValueError('Coverage source_refs must identify declared feedback')
        if not isinstance(targets, list) or any(not isinstance(t, str) or t not in ids for t in targets):
            raise ValueError('Coverage item_ids must identify included topics')
        status = entry['status']
        if not isinstance(status, str) or status not in {'included', 'merged', 'omitted', 'unresolved'}:
            raise ValueError('Unsupported content coverage status')
        if status in {'included', 'merged'}:
            if not targets:
                raise ValueError('Included/merged feedback must map to note items')
            for target in targets:
                item = next(i for i in items if i['id'] == target)
                if not set(refs) & set(item['source_refs']):
                    raise ValueError('Coverage mapping and note item must share feedback provenance')
            covered.update(targets)
        elif targets:
            raise ValueError('Omitted/unresolved feedback cannot claim included note items')
        if status != 'included' and (not isinstance(entry.get('reason'), str) or not entry['reason'].strip()):
            raise ValueError('Merged/omitted/unresolved feedback requires a reason')
    if ids - covered:
        raise ValueError('Every note item must map to the original feedback inventory')
    return coverage


def links(ids, by_id, text):
    return '、'.join('<a href="#' + anchor(item_id) + '">' + text(by_id[item_id]['title'], 'related title') + '</a>' for item_id in ids)


def definition_html(value, fragment, text, base):
    if value is None:
        return ''
    title = text(value['term_zh'], 'Chinese term') + ' · ' + text(value['term_en'], 'English term')
    rows = [('中文理解', 'meaning_html'), ('英文定义', 'definition_en_html'),
            ('适用条件', 'conditions_html'), ('符号与单位', 'symbols_html'),
            ('易混概念', 'contrast_html'), ('解释时补充', 'explain_html')]
    output = '<section class="definition-sheet"><h3>' + title + '</h3>'
    if value.get('command'):
        output += '<p class="command">' + escape(value['command'].capitalize()) + ' · ' + {'state': '简明陈述', 'define': '精确定义', 'explain': '说明理由'}[value['command']] + '</p>'
    output += '<dl>'
    for label, key in rows:
        if key in value:
            output += '<dt>' + label + '</dt><dd>' + fragment(value[key], base) + '</dd>'
    return output + '</dl></section>'


def steps_html(steps, by_id, fragment, text, base):
    if not steps:
        return ''
    output = '<section class="steps-section"><h3>关键步骤与理由</h3><ol class="key-steps">'
    for step in steps:
        output += '<li><p class="step-title">' + text(step['title'], 'step title') + '</p>'
        output += fragment(step['action_html'], base) + '<div class="step-reason"><strong>为什么这样做</strong>' + fragment(step['why_html'], base) + '</div>'
        if 'conditions_html' in step:
            output += '<div class="step-condition"><strong>成立条件</strong>' + fragment(step['conditions_html'], base) + '</div>'
        if step.get('prerequisites'):
            output += '<p class="related">所用基础：' + links(step['prerequisites'], by_id, text) + '</p>'
        output += '</li>'
    return output + '</ol></section>'
