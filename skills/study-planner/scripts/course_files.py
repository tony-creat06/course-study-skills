#!/usr/bin/env python3
"""Inventory, archive and navigate a material-backed course. No semantic classification."""
import argparse
import copy
import hashlib
from html import escape
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote
import uuid

import course_records as records
import course_moves

MOVE_PENDING = course_moves.MOVE_PENDING

CATEGORIES = ('syllabus', 'lectures', 'transcripts', 'exercises', 'solutions',
              'exams', 'revision', 'textbooks', 'supplements', 'unclassified')
LABELS = dict(zip(CATEGORIES, ('课程要求', '讲义与课件', '课堂字幕', '老师习题', '老师答案与评分',
                              '试卷', '复习资料', '教材', '补充材料', '待确认类别')))
INDEX_PATHS = ('index.md', 'index.html', 'materials-index.md')


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def plain_path(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Use an absolute path without ..')
    # Do not follow source aliases into unrelated directories.
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('Material paths cannot traverse symlinks: ' + str(path))
    return path


def beneath(path, root):
    return path == root or root in path.parents


def ensure_visible_dir(value, label='course-home'):
    path = plain_path(value)
    if any(part.startswith('.') for part in path.parts if part not in ('.', '..')):
        raise ValueError('Choose a visible ' + label + ', not a hidden Skill/Workspace directory: ' + str(path))
    records.check_visible_root(path)
    return path


def resolve_record_root(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Use an absolute path without ..')
    for parent in path.parents:
        if parent.is_symlink():
            raise ValueError('Material paths cannot traverse symlinks: ' + str(path))
    if path.is_symlink():
        resolved = plain_path(path.resolve())
        if not records.is_existing_course_root(resolved):
            raise ValueError('Material paths cannot traverse symlinks: ' + str(path))
        records.check_visible_root(resolved)
        return resolved
    return plain_path(path)


def recover_moves(root, decision='finish'):
    return course_moves.recover_moves(resolve_record_root(root), decision)


def validate_registry(data):
    """Check fields consumed here without rewriting or dropping registry content."""
    def invalid(field, requirement):
        raise ValueError('Invalid materials.json: ' + field + ' ' + requirement)

    def text(value, field):
        if not isinstance(value, str):
            invalid(field, 'must be text')

    def digest(value, field):
        if (not isinstance(value, str) or len(value) != 64
                or any(c not in '0123456789abcdef' for c in value)):
            invalid(field, 'must be a lowercase SHA256 digest')

    def sequence(value, field):
        if not isinstance(value, list):
            invalid(field, 'must be a list')

    def locations(value, field):
        sequence(value, field)
        for i, location in enumerate(value):
            prefix = field + '[' + str(i) + ']'
            if not isinstance(location, dict):
                invalid(prefix, 'must be an object')
            text(location.get('path'), prefix + '.path')
            digest(location.get('sha256'), prefix + '.sha256')

    if not isinstance(data, dict):
        invalid('registry', 'must be an object')
    if data.get('schema_version') != 1:
        invalid('schema_version', 'must be 1')
    for field in ('course_id', 'materials_root'):
        text(data.get(field), field)
    sequence(data.get('source_roots'), 'source_roots')
    for i, source in enumerate(data['source_roots']):
        text(source, 'source_roots[' + str(i) + ']')
    sequence(data.get('entries'), 'entries')
    for i, entry in enumerate(data['entries']):
        prefix = 'entries[' + str(i) + ']'
        if not isinstance(entry, dict):
            invalid(prefix, 'must be an object')
        for field in ('id', 'path', 'inspection'):
            text(entry.get(field), prefix + '.' + field)
        digest(entry.get('sha256'), prefix + '.sha256')
        if entry.get('category') not in CATEGORIES:
            invalid(prefix + '.category', 'must be a supported category')
        chapters = entry.get('chapters')
        sequence(chapters, prefix + '.chapters')
        for j, chapter in enumerate(chapters):
            chapter_prefix = prefix + '.chapters[' + str(j) + ']'
            if not isinstance(chapter, dict):
                invalid(chapter_prefix, 'must be an object')
            for field in ('chapter', 'locator'):
                text(chapter.get(field), chapter_prefix + '.' + field)
        origins = entry.get('origin_paths', [])
        sequence(origins, prefix + '.origin_paths')
        for j, origin in enumerate(origins):
            text(origin, prefix + '.origin_paths[' + str(j) + ']')
        hashes = entry.get('origin_sha256', {})
        if not isinstance(hashes, dict):
            invalid(prefix + '.origin_sha256', 'must be an object')
        for path, sha in hashes.items():
            digest(sha, prefix + '.origin_sha256[' + repr(path) + ']')
        if 'versions' in entry:
            locations(entry['versions'], prefix + '.versions')
        for field in ('unavailable_versions', 'received_sources'):
            if field in entry:
                sequence(entry[field], prefix + '.' + field)
        if 'moved_sources' in entry:
            locations(entry['moved_sources'], prefix + '.moved_sources')
        if 'import_mode' in entry and entry['import_mode'] not in ('move', 'copy'):
            invalid(prefix + '.import_mode', 'must be move or copy')
    return data


def registry(root):
    course_moves.check_pending(root)
    result = records.read_record(root, 'materials.json')
    if result['content'] is None:
        raise ValueError('Initialize the course material registry first')
    try:
        data = json.loads(result['content'])
    except ValueError as exc:
        raise ValueError('Invalid materials.json: JSON could not be parsed: ' + str(exc)) from exc
    return validate_registry(data), result['sha256']


def init_course(root, materials_root, course_id, source_roots=()):
    raw_root = Path(root).expanduser()
    if (raw_root.is_absolute() and '..' not in raw_root.parts
            and raw_root.exists() and records.is_existing_course_root(raw_root.resolve())):
        root = resolve_record_root(root)
        records.check_visible_root(root)
    else:
        root = ensure_visible_dir(root, 'course record root')
    materials_root = ensure_visible_dir(materials_root, 'materials directory')
    if beneath(root, materials_root) or beneath(materials_root, root):
        raise ValueError('Keep original materials separate from course records')
    if not isinstance(course_id, str) or not course_id.strip():
        raise ValueError('Course identity is required')
    sources = [materials_root]
    for value in source_roots:
        path = plain_path(value)
        if beneath(path, root):
            raise ValueError('Source roots cannot be inside course records')
        if path not in sources:
            sources.append(path)
    current = records.read_record(root, 'materials.json')
    if current['content'] is not None:
        existing, _ = registry(root)
        if (existing['course_id'] != course_id or existing['materials_root'] != str(materials_root)
                or existing['source_roots'] != [str(p) for p in sources]):
            raise ValueError('Existing registry differs; preserve it and merge explicitly')
        return dict(current, changed=False, inbox=str(materials_root / 'inbox'))
    data = {'schema_version': 1, 'course_id': course_id, 'materials_root': str(materials_root),
            'source_roots': [str(p) for p in sources], 'entries': []}
    # Only the defined intake/type folders; no placeholder lesson/note artifacts.
    for directory in ('inbox', *CATEGORIES):
        target = plain_path(materials_root / directory)
        target.mkdir(parents=True, exist_ok=True)
    result = records.write_record(root, 'materials.json', 'main', 'absent',
                                  json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    return dict(result, inbox=str(materials_root / 'inbox'))


def scan_course(root):
    root = resolve_record_root(root)
    if not root.is_dir():
        raise ValueError('Course record root must exist before scanning')
    with records.course_lock(root):
        data, version = registry(root)
        files, warnings = {}, []
        for value in data['source_roots']:
            source = plain_path(value)
            if not source.is_dir():
                warnings.append({'path': str(source), 'reason': 'source root missing or not a directory'})
                continue
            for directory, dirs, names in os.walk(source, followlinks=False):
                base = Path(directory)
                if beneath(base, root):
                    dirs[:] = []
                    continue
                for name in list(dirs):
                    if name.startswith('.') or (base / name).is_symlink() or beneath(base / name, root):
                        dirs.remove(name)
                        if (base / name).is_symlink():
                            warnings.append({'path': str(base / name), 'reason': 'symlink skipped'})
                for name in sorted(names):
                    if name.startswith('.') or name in {'课程入口.html', 'AGENTS.md', 'PROJECT.md'}:
                        continue
                    path = base / name
                    if path.is_symlink():
                        warnings.append({'path': str(path), 'reason': 'symlink skipped'})
                        continue
                    try:
                        if path.is_file():
                            before = path.stat()
                            digest = sha_file(path)
                            after = path.stat()
                            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                                raise OSError('file changed during scan')
                            files[str(path)] = {'path': str(path), 'sha256': digest, 'size': after.st_size}
                    except OSError as exc:
                        warnings.append({'path': str(path), 'reason': str(exc)})
        known, versions = {}, {}
        for entry in data['entries']:
            locations = [(entry['path'], entry['sha256'], 'canonical')]
            locations += [(p, entry.get('origin_sha256', {}).get(p, entry['sha256']), 'origin')
                          for p in entry.get('origin_paths', [])]
            locations += [(v['path'], v['sha256'], 'retained_version') for v in entry.get('versions', [])]
            for path, digest, kind in locations:
                known[path] = {'id': entry['id'], 'sha256': digest, 'kind': kind}
                versions.setdefault(digest, []).append(path)
        added, modified, missing, moved, duplicates = [], [], [], [], []
        unknown = {p: v for p, v in files.items() if p not in known}
        for path, old in known.items():
            if path in files:
                if files[path]['sha256'] != old['sha256']:
                    modified.append(dict(files[path], id=old['id'], previous_sha256=old['sha256'], location=old['kind']))
            else:
                candidates = [p for p, v in unknown.items() if v['sha256'] == old['sha256']]
                event = {'id': old['id'], 'path': path, 'location': old['kind']}
                if candidates:
                    moved.append(dict(event, candidates=candidates))
                else:
                    missing.append(event)
        unknown_hashes = {}
        for path, item in sorted(unknown.items()):
            matches = versions.get(item['sha256'], []) + unknown_hashes.get(item['sha256'], [])
            if matches:
                duplicates.append(dict(item, matches=matches))
            else:
                added.append(item)
            unknown_hashes.setdefault(item['sha256'], []).append(path)
        # Pending classification is visible even after a previously acknowledged scan.
        pending = [e['id'] for e in data['entries'] if e['category'] == 'unclassified']
        return {'registry_sha256': version, 'files': list(files.values()), 'added': added,
                'modified': modified, 'missing': missing, 'moved': moved, 'duplicates': duplicates,
                'warnings': warnings, 'pending_classification': pending,
                'affected_ids': sorted({x['id'] for x in modified + missing + moved})}


def validate_item(item):
    if not isinstance(item, dict):
        raise ValueError('Material item must be an object')
    if item.get('category') not in CATEGORIES:
        raise ValueError('Choose a supported category after inspecting content')
    sha = item.get('sha256')
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('Item requires the inspected source SHA256')
    chapters = item.get('chapters', [])
    if not isinstance(chapters, list):
        raise ValueError('chapters must be a list')
    for chapter in chapters:
        if (not isinstance(chapter, dict) or not isinstance(chapter.get('chapter'), str)
                or not chapter['chapter'].strip() or not isinstance(chapter.get('locator'), str)
                or not chapter['locator'].strip()):
            raise ValueError('Each chapter mapping requires chapter and page/time locator')
    if not isinstance(item.get('inspection'), str) or not item['inspection'].strip():
        raise ValueError('Describe actual inspection scope; registration is not reading')
    if 'uses' in item and (not isinstance(item['uses'], list) or any(not isinstance(x, str) for x in item['uses'])):
        raise ValueError('uses must be a list of labels')
    for key in ('version', 'academic_year', 'notes'):
        if key in item and not isinstance(item[key], str):
            raise ValueError(key + ' must be text')
    if 'related_ids' in item and (not isinstance(item['related_ids'], list) or
                                any(not isinstance(v, str) for v in item['related_ids'])):
        raise ValueError('related_ids must be a list of material IDs')
    return plain_path(item['path'])


def destination_for(base, source, digest, planned_targets=None):
    def conflicts(candidate):
        if candidate.exists() and (not candidate.is_file() or sha_file(candidate) != digest):
            return True
        if planned_targets is not None and str(candidate) in planned_targets and planned_targets[str(candidate)] != digest:
            return True
        return False

    candidate = plain_path(base / source.name)
    if conflicts(candidate):
        candidate = plain_path(base / (source.stem + '--' + digest[:12] + source.suffix))
        if conflicts(candidate):
            raise ValueError('Version destination collision; keep both files and inspect')
    return candidate


def _plan_import_entry(root, data, item, mode, planned_targets=None, dry_run=False):
    source = validate_item(item)
    managed = plain_path(data['materials_root'])
    if beneath(source, root):
        raise ValueError('Course records are not material sources')
    if not any(beneath(source, plain_path(p)) for p in data['source_roots']):
        raise ValueError('Source is outside the declared material roots')
    if not source.is_file() or sha_file(source) != item['sha256']:
        raise ValueError('Source changed after inspection or is not a file')
    entries = data['entries']
    by_id = [e for e in entries if e['id'] == item.get('id')]
    if item.get('id') and not by_id:
        raise ValueError('Unknown material id')
    matched = by_id or [e for e in entries if str(source) == e['path'] or str(source) in e.get('origin_paths', [])]
    matched = matched or [e for e in entries if e['sha256'] == item['sha256']]
    existing = matched[0] if matched else None
    target_base = plain_path(managed / item['category'])
    if not dry_run:
        target_base.mkdir(parents=True, exist_ok=True)
    if existing and existing['sha256'] == item['sha256'] and existing['category'] == item['category']:
        target = plain_path(existing['path'])
        if not target.exists() and (planned_targets is None or str(target) not in planned_targets):
            target = destination_for(target_base, source, item['sha256'], planned_targets=planned_targets)
    else:
        target = destination_for(target_base, source, item['sha256'], planned_targets=planned_targets)
    if not beneath(target, target_base):
        raise ValueError('Canonical material path is outside its category folder')
    existed = target.exists() or (planned_targets is not None and str(target) in planned_targets)
    if target.exists() and (not target.is_file() or sha_file(target) != item['sha256']):
        raise ValueError('Existing canonical source changed; rescan before importing')
    entry = dict(existing) if existing else {'id': 'M-' + uuid.uuid4().hex[:12], 'versions': []}
    old_path = entry.get('path')
    # A category correction relocates the same bytes; it is not a new version.
    if existing and existing['sha256'] != item['sha256']:
        retained = {'path': existing['path'], 'sha256': existing['sha256']}
        entry['versions'] = [*entry.get('versions', [])]
        previous_file = plain_path(existing['path'])
        if previous_file.is_file() and sha_file(previous_file) == existing['sha256']:
            if retained not in entry['versions']:
                entry['versions'].append(retained)
        else:
            entry['unavailable_versions'] = [*entry.get('unavailable_versions', []), retained]
    origins = set(entry.get('origin_paths', []))
    origin_hashes = {p: entry.get('origin_sha256', {}).get(p, entry.get('sha256')) for p in origins}
    # Origins mean live copies only. Moved locations remain provenance so a
    # later scan does not report their intentional absence as lost material.
    in_inbox = beneath(source, managed / 'inbox')
    if mode == 'copy' and not beneath(source, managed):
        origins.add(str(source))
        origin_hashes[str(source)] = item['sha256']
    provenance = {'path': str(source), 'sha256': item['sha256']}
    entry['received_sources'] = [*entry.get('received_sources', [])]
    if (source != target or not existing or existing['sha256'] != item['sha256']) and provenance not in entry['received_sources']:
        entry['received_sources'].append(provenance)
    move_sources = [{'path': str(source), 'sha256': item['sha256'],
                     'remove': mode == 'move' and source != target}]
    cleanup_paths = []
    if existing and existing['sha256'] == item['sha256'] and old_path != str(target):
        cleanup_paths.append(old_path)
    # Repair older reclassification entries which called identical bytes a
    # retained version, while keeping every genuine different-byte version.
    kept_versions = []
    for retained in entry.get('versions', []):
        if retained['sha256'] == item['sha256'] and retained['path'] != str(target):
            cleanup_paths.append(retained['path'])
        else:
            kept_versions.append(retained)
    entry['versions'] = kept_versions
    for value in cleanup_paths:
        previous = plain_path(value)
        if not beneath(previous, managed):
            raise ValueError('Canonical reclassification cannot remove an external retained version')
        if previous.exists() and str(previous) not in {s['path'] for s in move_sources}:
            if not previous.is_file() or sha_file(previous) != item['sha256']:
                raise ValueError('Previous canonical file changed; preserve it and rescan')
            move_sources.append({'path': str(previous), 'sha256': item['sha256'], 'remove': True})
    moved = [*entry.get('moved_sources', [])]
    for movement in move_sources:
        if movement['remove']:
            origins.discard(movement['path'])
            origin_hashes.pop(movement['path'], None)
            location = {'path': movement['path'], 'sha256': movement['sha256']}
            if location not in moved:
                moved.append(location)
    entry.update(path=str(target), sha256=item['sha256'], size=source.stat().st_size,
                 original_name=entry.get('original_name', source.name), origin_paths=sorted(origins),
                 origin_sha256=origin_hashes,
                 category=item['category'], chapters=item.get('chapters', []),
                 inspection=item['inspection'], uses=item.get('uses', []),
                 moved_sources=moved, import_mode=mode)
    for key in ('version', 'academic_year', 'notes', 'related_ids'):
        if key in item:
            entry[key] = item[key]
    data['entries'] = [entry if e['id'] == entry['id'] else e for e in entries] if existing else [*entries, entry]
    content = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    validate_registry(data)
    if planned_targets is not None:
        planned_targets[str(target)] = item['sha256']
    return source, entry, target, existed, move_sources, in_inbox, old_path, content


def _import_material_locked(root, item, expected, mode='move'):
    data, version = registry(root)
    if version != expected:
        raise ValueError('Stale material registry; re-read and merge')
    source, entry, target, existed, move_sources, in_inbox, old_path, content = _plan_import_entry(
        root, data, item, mode, dry_run=False)
    # The journal covers target publication, registry commit and source
    # removal; interruptions remain explicit until finish/abort recovery.
    _, registry_path = records.target_path(root, 'materials.json')
    previous = registry_path.read_bytes()
    if records.digest(previous) != expected:
        raise ValueError('Stale material registry; keep imported bytes and merge')
    stage = str(target.parent / ('.intake-move-' + uuid.uuid4().hex)) if not existed else None
    plan = {'schema_version': 1, 'mode': mode,
            'registry_before': previous.decode('utf-8'), 'registry_after': content,
            'target': {'path': str(target), 'sha256': item['sha256'], 'created': not existed},
            'stage': stage, 'sources': move_sources}
    result = course_moves.start_move(root, plan)
    consumed = str(source) in result['removed_sources']
    public_result = {'id': entry['id'], 'path': str(target), 'sha256': records.digest(content.encode('utf-8')),
                     'source_sha256': item['sha256'], 'inbox_consumed': in_inbox and consumed,
                     'source_preserved': source.exists(), 'previous_path': old_path, 'mode': mode,
                     'removed_sources': result['removed_sources']}
    rollback_info = {'target': str(target), 'sha256': item['sha256'], 'created': not existed,
                     'removed_sources': list(result['removed_sources'])}
    return public_result, rollback_info


def import_material(root, item, expected, mode='move'):
    if mode not in ('move', 'copy'):
        raise ValueError('Choose move or explicit copy for material import')
    validate_item(item)
    root = resolve_record_root(root)
    with records.course_lock(root):
        result, _ = _import_material_locked(root, item, expected, mode=mode)
        return result


def load_json_arg(value):
    text = sys.stdin.read() if value == '-' else Path(value).read_text(encoding='utf-8')
    return json.loads(text)


class BatchImportError(ValueError):
    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


def import_materials_batch(root, items, expected, mode='move'):
    if mode not in ('move', 'copy'):
        raise ValueError('Choose move or explicit copy for material import')
    if not isinstance(items, list) or not items:
        raise ValueError('Batch import requires a nonempty list of material items')
    root = resolve_record_root(root)
    seen_sources = set()
    for item in items:
        source = validate_item(item)
        if str(source) in seen_sources:
            raise ValueError('Duplicate source path in batch: ' + str(source))
        seen_sources.add(str(source))
    with records.course_lock(root):
        data, version = registry(root)
        if version != expected:
            raise ValueError('Stale material registry; re-read and merge')
        # Full dry-run preflight across all items before touching any file.
        sim_data = copy.deepcopy(data)
        planned_targets = {}
        for item in items:
            _plan_import_entry(root, sim_data, item, mode, planned_targets=planned_targets, dry_run=True)
        current_expected = expected
        results = []
        for idx, item in enumerate(items):
            try:
                res, _ = _import_material_locked(root, item, current_expected, mode=mode)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                pending_move = course_moves.pending_path(root).exists()
                after_finish = items[idx + 1:]
                if pending_move:
                    if after_finish:
                        hint = (
                            'Run course_files.py move-recover --decision finish or abort first, '
                            'then re-read materials.json: after finish, retry only remaining_after_finish '
                            '(skip the recovered failed_item); after abort, retry remaining_after_abort '
                            '(including failed_item).'
                        )
                    else:
                        hint = (
                            'Run course_files.py move-recover --decision finish or abort first, '
                            'then re-read materials.json: after finish, the batch is complete '
                            '(remaining_after_finish is empty, no retry needed); after abort, retry '
                            'remaining_after_abort (including failed_item).'
                        )
                else:
                    hint = (
                        'Re-read materials.json (preserving any manual edits) and retry '
                        'remaining_items with the current registry SHA.'
                    )
                report = {
                    'status': 'partial_failure' if results else 'failed',
                    'error': str(exc),
                    'pending_move_recovery': pending_move,
                    'recovery_hint': hint,
                    'completed_count': len(results),
                    'completed': results,
                    'failed_item': item,
                    'remaining_items': items[idx:],
                    'last_committed_registry_sha256': current_expected,
                }
                if pending_move:
                    report['remaining_after_finish'] = after_finish
                    report['remaining_after_abort'] = items[idx:]
                raise BatchImportError(str(exc), report) from exc
            results.append(res)
            current_expected = res['sha256']
    return {
        'count': len(results),
        'moved_count': sum(1 for r in results if not r['source_preserved'] and r['removed_sources']),
        'removed_sources_count': sum(len(r['removed_sources']) for r in results),
        'registry_sha256': current_expected,
        'mode': mode,
        'results': results,
    }


def relative_url(target, root):
    return quote(os.path.relpath(target, root).replace(os.sep, '/'), safe='/')


def _collect_output_sections(root, show_solutions=False):
    sections = []
    groups = [('课后与章节笔记', 'notes', {'.html', '.pdf'}),
              ('课堂原记录', 'lessons', {'.md'}), ('临时答疑', 'side-notes', {'.md'}), ('练习题', 'questions/prompts', {'.md'}),
              ('作答与反馈', 'practice', {'.md'}), ('已展示的题解集', 'reviews', {'.html'}),
              ('题目与考试分析简报', 'exam', {'.md'}), ('字幕阅读与疑点', 'transcripts', {'.md'})]
    if show_solutions:
        groups.append(('答案解析（按请求展示）', 'questions/solutions', {'.md'}))
    else:
        sections.append(('作者答案解析', []))
    for label, directory, suffixes in groups:
        paths = []
        base = root / directory
        if base.is_symlink():
            raise ValueError('Output folders cannot be symlinks')
        if base.exists():
            for path in sorted(base.rglob('*')):
                if directory == 'exam' and path.relative_to(base).as_posix() != 'brief.md':
                    continue
                if path.suffix in suffixes and path.is_file() and not any(x.startswith('.') for x in path.relative_to(root).parts):
                    _, path = records.target_path(root, str(path.relative_to(root)))
                    title = '查看分析简报' if directory == 'exam' else str(path.relative_to(base))
                    paths.append((title, relative_url(path, root), ''))
        sections.append((label, paths))
    return sections


def _format_md_row(text, url, detail):
    mdtext = text.replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('\n', ' ')
    suffix = (' — ' + detail.replace('\n', ' ')) if detail else ''
    if url:
        return '- [' + mdtext + '](' + url + ')' + suffix + '\n'
    return '- ' + mdtext + suffix + '\n'


def _render_navigation(course_id, notice, sections):
    md = '# ' + course_id + ' · 课程文件导航\n\n' + notice + '\n'
    body = '<h1>' + escape(course_id) + ' · 课程文件导航</h1><p>' + escape(notice) + '</p>'
    for label, rows in sections:
        md += '\n## ' + label + '\n\n'
        body += '<section><h2>' + escape(label) + '</h2>'
        if not rows:
            empty = ('作者解析单独保存在 questions/solutions/；按作答反馈或明确请求打开，当前总览不展开。'
                     if label == '作者答案解析' else '尚未生成或登记。')
            md += empty + '\n'
            body += '<p>' + escape(empty) + '</p>'
        else:
            body += '<ul>'
            for text, url, detail in rows:
                md += _format_md_row(text, url, detail)
                if url:
                    body += '<li><a href="' + escape(url, quote=True) + '">' + escape(text) + '</a>'
                else:
                    body += '<li><span>' + escape(text) + '</span>'
                if detail:
                    body += ' — ' + escape(detail)
                body += '</li>'
            body += '</ul>'
        body += '</section>'
    html = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>' + escape(course_id) + ' · 课程文件导航</title><style>'
            'body{max-width:900px;margin:40px auto;padding:0 20px;font:17px/1.8 system-ui;color:#1b2d3b;background:#fafaf7}'
            'h1{font-size:1.8em}h2{font-size:1.2em}a{color:#146d68}section{border-top:1px solid #d6ded9;margin-top:24px}'
            'li,p{overflow-wrap:anywhere}</style><main>' + body + '</main></html>')
    return md, html


def build_indexes(root, expected_manifest, expected_targets, show_solutions=False, link_base=None):
    raw_root = Path(root).expanduser()
    root = resolve_record_root(root)
    base_for_links = Path(link_base).expanduser() if link_base is not None else raw_root
    if set(expected_targets) != set(INDEX_PATHS):
        raise ValueError('Provide versions for index.md, index.html and materials-index.md')
    with records.course_lock(root):
        data, actual = registry(root)
        if actual != expected_manifest:
            raise ValueError('Material registry changed; re-read before publishing indexes')
        material_rows = []
        chapter_rows = []
        for entry in data['entries']:
            source = plain_path(entry['path'])
            exists = source.is_file()
            label = entry['id'] + ' · ' + LABELS[entry['category']] + ' · ' + source.name
            url = relative_url(source, base_for_links) if exists else None
            availability = '已登记（内容按本次任务核对）' if exists else '缺失，需复核'
            material_rows.append((label, url, availability + '；' + entry['inspection']))
            chapter_detail = entry['id'] if exists else entry['id'] + ' · 缺失，需复核'
            for chapter in entry['chapters']:
                chapter_rows.append((chapter['chapter'] + ' · ' + chapter['locator'], url, chapter_detail))
        sections = [('资料分类', material_rows), ('章节索引', sorted(chapter_rows, key=lambda row: (row[0], row[1] or '', row[2])))]
        sections.extend(_collect_output_sections(root, show_solutions=show_solutions))
        inbox = str(Path(data['materials_root']) / 'inbox')
        notice = ('新增资料放入 ' + inbox + '；明确接收新资料或当前任务涉及它时检查并分类，不在后台监控。'
                  '题目与作者解析分别保存；完整答案按作答反馈或明确请求展示。'
                  '旧题目路径保留，不把未知是否含答案的旧文件直接加入题目入口。')
        md, html = _render_navigation(data['course_id'], notice, sections)
        source_md = '# 材料分类与章节索引\n\n由 materials.json 派生；实际阅读范围以登记正文为准。\n'
        for label, rows in sections[:2]:
            source_md += '\n## ' + label + '\n\n' + ''.join(_format_md_row(t, u, d) for t, u, d in rows)
        payload = {'index.md': md, 'index.html': html, 'materials-index.md': source_md}
        # Prepare within the lock. write_bundle acquires it itself, so publish below;
        # include unchanged registry to detect intervening intake changes.
        updates = [{'path': p, 'expected': expected_targets[p], 'content': payload[p]} for p in INDEX_PATHS]
        updates.append({'path': 'materials.json', 'expected': actual,
                        'content': records.read_record(root, 'materials.json')['content']})
    result = records.write_bundle(root, 'main', updates)
    return dict(result, index=str(base_for_links / 'index.html'), inbox=inbox)


def build_legacy_indexes(root, course_id, expected_targets, show_solutions=False, link_base=None):
    raw_root = Path(root).expanduser()
    root = resolve_record_root(root)
    base_for_links = Path(link_base).expanduser() if link_base is not None else raw_root
    records.check_visible_root(root)
    if not records.is_existing_course_root(root):
        raise ValueError('Existing course records are required for legacy navigation')
    if set(expected_targets) != {'index.md', 'index.html'}:
        raise ValueError('Provide versions for index.md and index.html')
    with records.course_lock(root):
        sections = _collect_output_sections(root, show_solutions=show_solutions)
        notice = ('既有课程沿用原只读资料来源（尚未建立资料归档清单 materials.json）。'
                  '题目与作者解析分别保存；完整答案按作答反馈或明确请求展示。')
        md, html = _render_navigation(course_id, notice, sections)
        payload = {'index.md': md, 'index.html': html}
        updates = [{'path': p, 'expected': expected_targets[p], 'content': payload[p]} for p in ('index.md', 'index.html')]
    result = records.write_bundle(root, 'main', updates)
    return dict(result, index=str(base_for_links / 'index.html'), inbox=None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--root', required=True)
    init.add_argument('--materials-root', required=True)
    init.add_argument('--course', required=True)
    init.add_argument('--source-root', action='append', default=[])
    scan = sub.add_parser('scan'); scan.add_argument('--root', required=True)
    intake = sub.add_parser('import'); intake.add_argument('--root', required=True)
    intake.add_argument('--item-json', required=True); intake.add_argument('--expected', required=True)
    intake.add_argument('--copy', action='store_true', help='Explicitly preserve the input as a separate copy')
    batch = sub.add_parser('import-batch'); batch.add_argument('--root', required=True)
    batch.add_argument('--items-json', required=True); batch.add_argument('--expected', required=True)
    batch.add_argument('--copy', action='store_true', help='Explicitly preserve the inputs as separate copies')
    recovery = sub.add_parser('move-recover'); recovery.add_argument('--root', required=True)
    recovery.add_argument('--decision', choices=('finish', 'abort'), default='finish')
    index = sub.add_parser('index'); index.add_argument('--root', required=True)
    index.add_argument('--expected-manifest', required=True)
    index.add_argument('--expected-targets-json', required=True)
    index.add_argument('--show-solutions', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'init':
            result = init_course(args.root, args.materials_root, args.course, args.source_root)
        elif args.command == 'scan':
            result = scan_course(args.root)
        elif args.command == 'import':
            result = import_material(args.root, load_json_arg(args.item_json),
                                     args.expected, mode='copy' if args.copy else 'move')
        elif args.command == 'import-batch':
            result = import_materials_batch(args.root, load_json_arg(args.items_json),
                                            args.expected, mode='copy' if args.copy else 'move')
        elif args.command == 'move-recover':
            result = recover_moves(args.root, args.decision)
        else:
            result = build_indexes(args.root, args.expected_manifest,
                                   load_json_arg(args.expected_targets_json), args.show_solutions)
        print(json.dumps(result, ensure_ascii=False))
    except BatchImportError as exc:
        if exc.report.get('completed_count', 0) > 0:
            print(json.dumps(exc.report, ensure_ascii=False))
        parser.exit(2, str(exc) + '\n')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
