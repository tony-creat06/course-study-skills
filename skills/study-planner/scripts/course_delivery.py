#!/usr/bin/env python3
"""Declare a course task, then verify its actual delivery. No routine full-course scan."""
import argparse
from datetime import datetime, timezone
from html import escape, unescape
import json
import os
from pathlib import Path
import posixpath
import re
from urllib.parse import quote, unquote
import uuid

import course_files as files
import course_records as records

ACTIVITIES = {'setup', 'intake', 'lesson', 'analysis', 'practice', 'notes', 'review', 'aside'}
REQUIRED = {'lesson': {'lesson', 'notes'}, 'analysis': {'analysis_brief', 'analysis_detail'},
            'practice': {'prompt', 'solution'}, 'notes': {'notes'}, 'review': {'review'}, 'aside': {'side_note'}}
KINDS = {'lesson', 'notes', 'prompt', 'solution', 'analysis_brief', 'analysis_detail', 'feedback',
         'checkpoint', 'course', 'review', 'side_note', 'material_map'}
SETUP_FILES = ('course.md', 'materials.md', 'course-map.md', 'study-plan.md', 'current.md')
PORTAL = '课程入口.html'


def now():
    return datetime.now(timezone.utc).isoformat()


def visible_home(value):
    return files.ensure_visible_dir(value, 'course-home')


def metadata(root):
    path = root / '.course-delivery'
    files.plain_path(path)
    return path


def private_path(root, run):
    if not isinstance(run, str) or len(run) != 32 or any(c not in '0123456789abcdef' for c in run):
        raise ValueError('Use the exact run id returned by begin')
    return files.plain_path(metadata(root) / 'runs' / (run + '.json'))


def state_bytes(path):
    return path.read_bytes() if path.exists() else None


def save_json(path, value):
    records.atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def capture(path):
    path = files.plain_path(path)
    if not path.is_file():
        raise ValueError('Declared source is not a readable file: ' + str(path))
    before = path.stat()
    digest = files.sha_file(path)
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('Source changed while recording task scope: ' + str(path))
    return {'path': str(path), 'sha256': digest, 'size': after.st_size}


def collect_sources(paths, root, materials, excluded=()):
    """Enumerate only the supplied setup/intake batch. Never used for ordinary lessons."""
    result = {}
    excluded_paths = [Path(p) for p in excluded]

    def is_excluded(path):
        return files.beneath(path, root) or any(files.beneath(path, ex) for ex in excluded_paths)

    for value in paths:
        source = files.plain_path(value)
        if source.is_file():
            if is_excluded(source):
                raise ValueError('Learning outputs cannot be supplied as raw course material')
            result[str(source)] = capture(source)
        elif source.is_dir():
            include_managed = files.beneath(source, materials)
            for directory, dirs, names in os.walk(source, followlinks=False):
                base = Path(directory)
                dirs[:] = [d for d in dirs if not d.startswith('.')
                           and not is_excluded(base / d)
                           and (include_managed or not files.beneath(base / d, materials))]
                for d in dirs:
                    if (base / d).is_symlink():
                        raise ValueError('Supplied batch contains a directory symlink: ' + str(base / d))
                for name in sorted(names):
                    if name.startswith('.') or name in {'AGENTS.md', 'PROJECT.md', PORTAL}:
                        continue
                    path = base / name
                    if is_excluded(path) or (not include_managed and files.beneath(path, materials)):
                        continue
                    if path.is_symlink():
                        raise ValueError('Supplied batch contains a file symlink: ' + str(path))
                    if path.is_file():
                        result[str(path)] = capture(path)
        else:
            raise ValueError('Supplied material path is missing: ' + str(source))
    return list(result.values())


def resolve_delivery_root(home, root_arg):
    raw = Path(root_arg or home / '学习产出').expanduser()
    if not raw.is_absolute() or '..' in raw.parts:
        raise ValueError('Use an absolute path without ..')
    for parent in raw.parents:
        if parent.is_symlink():
            raise ValueError('Material paths cannot traverse symlinks: ' + str(raw))
    if raw.is_symlink():
        resolved = files.plain_path(raw.resolve())
        if not records.is_existing_course_root(resolved):
            raise ValueError('Material paths cannot traverse symlinks: ' + str(raw))
        records.check_visible_root(resolved)
        return resolved, True, str(raw) if files.beneath(raw, home) else None
    resolved = files.plain_path(raw)
    if resolved != home and files.beneath(resolved, home):
        records.check_visible_root(resolved)
        return resolved, False, None
    if records.is_existing_course_root(resolved):
        records.check_visible_root(resolved)
        default_entry = home / '学习产出'
        entry = str(default_entry) if default_entry.is_symlink() and default_entry.resolve() == resolved else None
        return resolved, True, entry
    raise ValueError('Materials and learner outputs must live under the visible course-home; migrate old records explicitly')


def artifact_spec(root, item):
    if not isinstance(item, dict) or set(item) - {'path', 'kind', 'freshness', 'source_paths'}:
        raise ValueError('Each expected artifact uses path, kind, freshness and optional source_paths')
    path = item.get('path')
    if not isinstance(path, str) or item.get('kind') not in KINDS:
        raise ValueError('Expected artifacts need a relative path and supported kind')
    _, target = records.target_path(root, path)
    if target.suffix not in {'.md', '.html', '.json', '.pdf'}:
        raise ValueError('Unsupported delivery artifact format')
    kind = item['kind']
    prefixes = {'lesson': 'lessons/', 'notes': 'notes/', 'prompt': 'questions/prompts/',
                'solution': 'questions/solutions/', 'analysis_detail': 'exam/',
                'feedback': 'practice/', 'review': 'reviews/', 'side_note': 'side-notes/'}
    if kind in prefixes and not path.startswith(prefixes[kind]):
        raise ValueError('Artifact kind does not match its owned output directory: ' + path)
    if kind == 'analysis_brief' and path != 'exam/brief.md':
        raise ValueError('Visible analysis brief must be exam/brief.md')
    if kind == 'checkpoint' and path != 'current.md':
        raise ValueError('Checkpoint must be the existing current.md')
    if kind == 'notes' and target.suffix not in {'.html', '.pdf'}:
        raise ValueError('Deliver a readable note, not its internal draft JSON')
    mode = item.get('freshness', 'changed')
    if mode not in {'new', 'changed', 'reuse', 'present'}:
        raise ValueError('freshness must be new, changed, reuse or present')
    dependencies = item.get('source_paths', [])
    if not isinstance(dependencies, list):
        raise ValueError('source_paths must be an absolute-path list')
    return {'path': str(target.relative_to(root)), 'kind': item['kind'], 'freshness': mode,
            'before': records.digest(state_bytes(target)), 'sources': [capture(p) for p in dependencies]}


def begin_course(course_home, root=None, activity='setup', request=None, course_id=None,
                 materials_root=None, source_roots=()):
    if activity not in ACTIVITIES:
        raise ValueError('Unsupported course activity')
    request = {} if request is None else request
    if not isinstance(request, dict) or set(request) - {'sources', 'expected', 'material_ids', 'source_policy'}:
        raise ValueError('Request uses sources, expected, material_ids and optional explicit source_policy')
    source_policy = request.get('source_policy', 'move')
    if source_policy not in {'move', 'copy'}:
        raise ValueError('source_policy must be move or explicit copy')
    home = visible_home(course_home)
    root, legacy_root, root_entry = resolve_delivery_root(home, root)
    has_manifest = (root / 'materials.json').is_file()
    legacy_no_manifest = (not has_manifest) and records.is_existing_course_root(root) and activity not in {'setup', 'intake'}
    if legacy_no_manifest:
        materials = files.plain_path(materials_root) if materials_root is not None else None
        if materials is not None and (files.beneath(root, materials) or files.beneath(materials, root)):
            raise ValueError('Keep material files and learning outputs in separate directories')
    elif materials_root is not None:
        materials = files.plain_path(materials_root)
        if not legacy_root and (materials == home or not files.beneath(materials, home)):
            raise ValueError('Materials and learner outputs must live under the visible course-home; migrate old records explicitly')
    elif legacy_root and has_manifest:
        existing_registry, _ = files.registry(root)
        materials = files.plain_path(existing_registry['materials_root'])
    else:
        materials = files.plain_path(home / '资料')
    if materials is not None and (files.beneath(root, materials) or files.beneath(materials, root)):
        raise ValueError('Keep material files and learning outputs in separate directories')
    sources = request.get('sources', [])
    expected = request.get('expected', [])
    ids = request.get('material_ids', [])
    if not isinstance(sources, list) or not isinstance(expected, list) or not isinstance(ids, list) or any(not isinstance(x, str) for x in ids):
        raise ValueError('sources, expected and material_ids must be lists')
    if activity == 'setup' and not sources:
        sources = list(source_roots) or [str(home)]
    if activity == 'intake' and not sources:
        sources = [str(materials / 'inbox')]
    if sources and activity not in {'setup', 'intake'}:
        raise ValueError('Receive a new raw batch through setup/intake before teaching; ordinary runs do not scan raw folders')
    excluded = (Path(root_entry),) if root_entry else ()
    batch = collect_sources(sources, root, materials or (home / '资料'), excluded=excluded) if sources else []
    if activity == 'setup' and not batch and not has_manifest:
        raise ValueError('Initial setup needs the supplied course material batch')
    expected_specs = [artifact_spec(root, x) for x in expected]
    if len({e['path'] for e in expected_specs}) != len(expected_specs):
        raise ValueError('Duplicate expected artifact')
    kinds = {e['kind'] for e in expected_specs}
    missing = REQUIRED.get(activity, set()) - kinds
    if missing:
        raise ValueError('Declare this activity\'s real deliverables before work: ' + ', '.join(sorted(missing)))
    if any(e['freshness'] == 'present' and (activity != 'setup' or e['path'] not in SETUP_FILES) for e in expected_specs):
        raise ValueError('Use changed/new or a previously verified reuse; file existence is not fresh delivery')
    if activity == 'setup':
        for p in SETUP_FILES:
            if p not in {e['path'] for e in expected_specs}:
                expected_specs.append(artifact_spec(root, {'path': p, 'kind': 'course', 'freshness': 'present'}))
    if activity in {'lesson', 'practice'} and 'current.md' not in {e['path'] for e in expected_specs}:
        expected_specs.append(artifact_spec(root, {'path': 'current.md', 'kind': 'checkpoint', 'freshness': 'changed'}))
    if not has_manifest and not legacy_no_manifest:
        if activity != 'setup':
            raise ValueError('First use needs setup to actually organize supplied materials')
        declared = list(dict.fromkeys([*map(str, source_roots), *[str(Path(p).parent if Path(p).is_file() else p) for p in sources]]))
        files.init_course(root, materials, course_id or home.name, declared)
    with records.course_lock(root):
        records.check_pending(root)
        if legacy_no_manifest:
            if ids:
                raise ValueError('Legacy course without materials.json cannot reference material_ids; pass read-only source_paths in expected')
            registry_sha = 'absent'
            resolved_course_id = course_id or home.name
            dependencies = []
            index_keys = ('index.md', 'index.html')
            inbox = None
            has_manifest_flag = False
        else:
            registry, registry_sha = files.registry(root)
            if registry['materials_root'] != str(materials):
                raise ValueError('Existing material root differs; preserve and explicitly migrate it')
            available = {e['id']: e for e in registry['entries']}
            if any(x not in available for x in ids):
                raise ValueError('Unknown current-task material id')
            for material_id in ids:
                # Only relevant dependencies are hashed, never the entire course.
                entry = available[material_id]
                current = capture(entry['path'])
                if current['sha256'] != entry['sha256']:
                    raise ValueError('Relevant material changed; receive it before this task: ' + material_id)
            resolved_course_id = registry['course_id']
            dependencies = [capture(available[x]['path']) for x in ids]
            index_keys = files.INDEX_PATHS
            inbox = str(materials / 'inbox')
            has_manifest_flag = True
        run = uuid.uuid4().hex
        plan = {'version': 1, 'run': run, 'activity': activity, 'started_at': now(), 'course_home': str(home),
                'root': str(root), 'legacy_root': legacy_root, 'root_entry': root_entry,
                'has_manifest': has_manifest_flag,
                'materials_root': str(materials) if materials is not None else None,
                'course_id': resolved_course_id,
                'sources': batch, 'source_policy': source_policy, 'material_ids': ids,
                'expected': expected_specs, 'registry_before': registry_sha,
                'index_before': {p: records.digest(state_bytes(root / p)) for p in index_keys},
                'portal_before': records.digest(state_bytes(home / PORTAL)), 'status': 'pending',
                'dependencies': dependencies}
        save_json(private_path(root, run), plan)
    return {'run': run, 'root': str(root), 'materials_root': plan['materials_root'], 'inbox': inbox,
            'course_home': str(home), 'supplied_files': len(batch), 'sources': batch,
            'expected': [e['path'] for e in expected_specs],
            'legacy_no_manifest': legacy_no_manifest,
            'setup_handoffs': 'If this received batch includes exercises/exams/solutions, provide a scoped exam/brief.md and internal analysis evidence before finishing; a formal exam date is not required.',
            'next': ('Save the declared lesson/notes/checkpoint deliverables against existing read-only sources, then run finish.'
                     if legacy_no_manifest else
                     'Move and classify this supplied batch first; verify --materials-only returns applicable module handoffs; then do that scoped work and finish.')}


def source_entry(source, entries):
    for entry in entries:
        refs = [{'path': entry['path'], 'sha256': entry['sha256']}, *entry.get('received_sources', []),
                *entry.get('moved_sources', [])]
        if any(isinstance(r, dict) and r.get('path') == source['path'] and r.get('sha256') == source['sha256'] for r in refs):
            return entry
    return None


def inspect_artifact(root, spec, prior):
    _, path = records.target_path(root, spec['path'])
    if not path.is_file() or path.stat().st_size == 0:
        return None, 'Missing/empty delivery: ' + spec['path']
    data = path.read_bytes()
    digest = records.digest(data)
    mode = spec['freshness']
    if mode == 'new' and spec['before'] != 'absent':
        return None, 'Expected a new artifact, but it predated this run: ' + spec['path']
    if mode in {'new', 'changed'} and digest == spec['before']:
        return None, 'Artifact was not updated for this run: ' + spec['path']
    for source in spec['sources']:
        p = files.plain_path(source['path'])
        if not p.is_file() or files.sha_file(p) != source['sha256']:
            return None, 'Artifact dependency changed: ' + source['path']
    if mode == 'reuse':
        old = prior.get(spec['path'])
        if not old or old.get('sha256') != digest or old.get('sources') != spec['sources']:
            return None, 'Reuse has no matching prior verified artifact/source receipt: ' + spec['path']
    if path.suffix in {'.md', '.html', '.json'}:
        try:
            text = data.decode('utf-8')
            if path.suffix == '.json':
                json.loads(text)
        except (ValueError, UnicodeError):
            return None, 'Unreadable delivery format: ' + spec['path']
        if text.strip().lower() in {'todo', 'placeholder', '待生成', '待补充', '{}', '[]'}:
            return None, 'Placeholder is not a delivery: ' + spec['path']
        if path.suffix == '.html' and ('<html' not in text.lower() or '<body' not in text.lower() and '<main' not in text.lower()):
            return None, 'Expected a readable complete HTML artifact: ' + spec['path']
    return {'path': spec['path'], 'kind': spec['kind'], 'sha256': digest, 'sources': spec['sources']}, None


def _verify_course(root, run, materials_only=False):
    root = files.resolve_record_root(root)
    if not root.is_dir():
        raise ValueError('Course root must exist')
    with records.course_lock(root):
        records.check_pending(root)
        path = private_path(root, run)
        plan = json.loads(path.read_text(encoding='utf-8'))
        if plan.get('version') != 1 or plan.get('run') != run or plan.get('root') != str(root):
            raise ValueError('Delivery run does not match the selected course')
        home = visible_home(plan['course_home'])
        has_manifest = plan.get('has_manifest', True)
        if has_manifest:
            registry, current_sha = files.registry(root)
            material_home = files.plain_path(plan['materials_root'])
            if plan.get('legacy_root'):
                records.check_visible_root(root)
                valid_locations = (records.is_existing_course_root(root)
                                   and not files.beneath(root, material_home)
                                   and not files.beneath(material_home, root))
            else:
                valid_locations = files.beneath(root, home) and files.beneath(material_home, home)
            if (not valid_locations
                    or registry['materials_root'] != str(material_home)
                    or not REQUIRED.get(plan['activity'], set()).issubset({e['kind'] for e in plan['expected']})):
                raise ValueError('Delivery scope/locations changed; preserve the original task obligations')
            inbox = str(Path(plan['materials_root']) / 'inbox')
        else:
            records.check_visible_root(root)
            if materials_only:
                raise ValueError('Legacy course without materials.json cannot run --materials-only verification')
            if (not records.is_existing_course_root(root)
                    or plan['sources']
                    or not REQUIRED.get(plan['activity'], set()).issubset({e['kind'] for e in plan['expected']})):
                raise ValueError('Delivery scope/locations changed; preserve the original task obligations')
            if plan.get('materials_root'):
                material_home = files.plain_path(plan['materials_root'])
                if files.beneath(root, material_home) or files.beneath(material_home, root):
                    raise ValueError('Keep material files and learning outputs in separate directories')
            registry, current_sha = {'entries': []}, 'absent'
            inbox = None
        errors, pending, materials_checked, artifacts = [], [], [], []
        moved_count = 0
        source_paths = set()
        for source in plan['sources']:
            entry = source_entry(source, registry['entries'])
            if not entry:
                errors.append('Supplied material not received/classified: ' + source['path']);continue
            canonical = files.plain_path(entry['path'])
            category_root = files.plain_path(Path(plan['materials_root']) / entry['category'])
            if not files.beneath(canonical, category_root) or not canonical.is_file() or files.sha_file(canonical) != source['sha256']:
                errors.append('Archived material bytes/category do not match supplied batch: ' + source['path']);continue
            original = files.plain_path(source['path'])
            if plan.get('source_policy', 'move') == 'move' and original != canonical and original.exists():
                errors.append('Source still remains; a copy does not satisfy move: ' + source['path'])
            elif plan.get('source_policy', 'move') == 'move' and original != canonical:
                moved_count += 1
            for previous in entry.get('versions', []):
                if previous['sha256'] == source['sha256'] and previous['path'] != str(canonical) and Path(previous['path']).exists():
                    errors.append('Identical previous category copy remains: ' + previous['path'])
            if entry['category'] == 'unclassified':
                pending.append({'id': entry['id'], 'reason': '用途仍待确认', 'path': str(canonical)})
            if not entry.get('chapters'):
                pending.append({'id': entry['id'], 'reason': '章节定位仍待确认', 'path': str(canonical)})
            if str(canonical) not in source_paths:
                materials_checked.append({'id': entry['id'], 'path': str(canonical), 'sha256': source['sha256'], 'category': entry['category']})
                source_paths.add(str(canonical))
        for source in plan['dependencies']:
            original = files.plain_path(source['path'])
            if not original.is_file() or files.sha_file(original) != source['sha256']:
                errors.append('Current task source changed after begin: ' + source['path'])
        prior_path = metadata(root) / 'artifacts.json'
        prior = json.loads(prior_path.read_text()) if prior_path.exists() else {}
        for spec in ([] if materials_only else plan['expected']):
            try:
                item, error = inspect_artifact(root, spec, prior)
            except (OSError, ValueError) as exc:
                item, error = None, str(exc)
            if error: errors.append(error)
            elif item: artifacts.append(item)
        needs_analysis = plan['activity'] == 'setup' and any(e['category'] in {'exams', 'exercises', 'solutions'} for e in materials_checked)
        if not materials_only and needs_analysis:
            brief = root / 'exam/brief.md'
            if not brief.is_file() or not brief.read_text(encoding='utf-8').strip():
                errors.append('Supplied questions need a scoped analysis brief: exam/brief.md')
            details = [p for p in (root / 'exam').rglob('*') if p.is_file() and p.name != 'brief.md' and p.suffix in {'.md', '.json'}]
            if not details:
                errors.append('Supplied questions need internal analysis evidence as well as a brief')
            for candidate, kind in [(brief, 'analysis_brief'), *[(p, 'analysis_detail') for p in sorted(details)[:1]]]:
                relative = str(candidate.relative_to(root))
                if any(e['path'] == relative for e in artifacts) or not candidate.is_file():
                    continue
                evidence = {'path': relative, 'kind': kind, 'freshness': 'present', 'before': 'absent',
                            'sources': [capture(e['path']) for e in materials_checked if e['category'] in {'exams', 'exercises', 'solutions'}]}
                item, error = inspect_artifact(root, evidence, prior)
                if error:
                    errors.append(error)
                else:
                    artifacts.append(item)
        report = {'run': run, 'activity': plan['activity'], 'checked_at': now(),
                  'verification_phase': 'material_handoff' if materials_only else 'full_delivery', 'root': str(root),
                  'course_home': plan['course_home'], 'registry_sha256': current_sha,
                  'status': 'incomplete' if errors else ('verified_with_pending' if pending else 'verified'),
                  'errors': errors, 'pending': pending, 'materials_checked': materials_checked,
                  'artifacts_checked': artifacts, 'checked_supplied_files': len(plan['sources']),
                  'inbox': inbox,
                  'moved_count': moved_count, 'pending_count': len(pending),
                  'required_handoffs': ([{'module': 'exam-analysis', 'outputs': ['exam/brief.md', 'exam/内部依据'],
                                         'scope': 'Only this received batch; teacher tutorials and mock papers count too, without requiring a scheduled exam.'}] if needs_analysis else []),
                  'source_policy': plan.get('source_policy', 'move'),
                  'scope': 'This task batch and declared outputs only; no full-course rescan or pedagogical correctness proof.'}
        plan['last_check'] = report
        save_json(path, plan)
        return report


def verify_course(root, run, materials_only=False):
    root = files.resolve_record_root(root)
    report = _verify_course(root, run, materials_only)
    if materials_only and not report['errors']:
        path = private_path(root, run)
        plan = json.loads(path.read_text(encoding='utf-8'))
        try:
            # The readable material/chapter index must already exist at handoff,
            # before teaching/analysis, not only at the final lesson publication.
            link_base = Path(plan['root_entry']) if plan.get('root_entry') and files.beneath(Path(plan['root_entry']), Path(plan['course_home'])) else root
            files.build_indexes(root, report['registry_sha256'], plan['index_before'], link_base=link_base)
            with records.course_lock(root):
                records.check_pending(root)
                plan = json.loads(path.read_text(encoding='utf-8'))
                plan['index_before'] = {p: records.digest(state_bytes(root / p)) for p in files.INDEX_PATHS}
                report['material_index'] = str(link_base / 'materials-index.md')
                plan['material_handoff'] = report
                plan['last_check'] = report
                save_json(path, plan)
        except (OSError, ValueError) as exc:
            report['errors'].append(str(exc))
            report['status'] = 'incomplete'
    return report


def publish_portal(plan, root):
    home = visible_home(plan['course_home'])
    target = files.plain_path(home / PORTAL)
    expected = plan['portal_before']
    current = state_bytes(target)
    if records.digest(current) != expected:
        raise ValueError('Course entry changed during this run; preserve and merge it')
    entry_base = Path(plan['root_entry']) if plan.get('root_entry') and files.beneath(Path(plan['root_entry']), home) else root
    index = quote(os.path.relpath(entry_base / 'index.html', home), safe='/')
    receipt = quote(os.path.relpath(entry_base / 'delivery.md', home), safe='/')
    if plan.get('has_manifest', True):
        inbox_path = str(Path(plan['materials_root']) / 'inbox')
        inbox = quote(os.path.relpath(inbox_path, home), safe='/')
        inbox_line = '<p>以后新资料放入：<a href="' + escape(inbox, quote=True) + '">' + escape(inbox_path) + '</a></p>'
    else:
        inbox_line = '<p>资料来源：沿用既有课程原只读资料（未建资料箱）。</p>'
    html = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>' + escape(plan['course_id']) + ' · 课程入口</title><main><h1>' + escape(plan['course_id']) + '</h1>'
            '<p><a href="' + escape(index, quote=True) + '">查看课程资料与学习产出</a></p>'
            + inbox_line +
            '<p><a href="' + escape(receipt, quote=True) + '">查看本次实际交付核验</a></p>'
            '<p>本页是课程入口，具体内容与本次交付状态见学习产出。</p></main></html>')
    if current != html.encode():
        records.backup_record(root, target, current)
        records.atomic_write(target, html.encode())
    return target


def verify_portal_links(portal, root, plan):
    """Walk links logically from 课程入口.html -> index.html -> targets like a browser."""
    portal_html = portal.read_text(encoding='utf-8')
    logical_index = None
    for href in re.findall(r'<a\s+href="([^"]+)"', portal_html):
        rel = unquote(unescape(href))
        logical = Path(posixpath.normpath(posixpath.join(str(portal.parent), rel)))
        if logical.name == 'delivery.md':
            if logical.parent.resolve() != root.resolve():
                raise ValueError('Broken course portal delivery link: ' + rel + ' -> ' + str(logical))
        elif logical.name == 'index.html':
            if not logical.is_file() or logical.resolve() != (root / 'index.html').resolve():
                raise ValueError('Broken course portal index link: ' + rel + ' -> ' + str(logical))
            logical_index = logical
        elif not logical.exists():
            raise ValueError('Broken course portal link: ' + rel + ' -> ' + str(logical))
    if logical_index is None:
        raise ValueError('Course portal is missing its index.html link')
    index_html = logical_index.read_text(encoding='utf-8')
    for li_html in re.findall(r'<li>.*?</li>', index_html, re.DOTALL):
        match = re.search(r'<a\s+href="([^"]+)"', li_html)
        if not match:
            continue
        rel_target = unquote(unescape(match.group(1)))
        logical_target = Path(posixpath.normpath(posixpath.join(str(logical_index.parent), rel_target)))
        if not logical_target.is_file():
            raise ValueError('Broken index link from course portal: ' + rel_target + ' -> ' + str(logical_target))
    return logical_index


def finish_course(root, run):
    root = files.resolve_record_root(root)
    report = verify_course(root, run)
    if report['errors']:
        publish_receipt(root, report)
        return report
    path = private_path(root, run)
    plan = json.loads(path.read_text(encoding='utf-8'))
    has_manifest = plan.get('has_manifest', True)
    link_base = Path(plan['root_entry']) if plan.get('root_entry') and files.beneath(Path(plan['root_entry']), Path(plan['course_home'])) else root
    index_keys = files.INDEX_PATHS if has_manifest else ('index.md', 'index.html')
    try:
        if has_manifest:
            files.build_indexes(root, report['registry_sha256'], plan['index_before'], link_base=link_base)
        else:
            files.build_legacy_indexes(root, plan['course_id'], plan['index_before'], link_base=link_base)
        plan['index_before'] = {p: records.digest(state_bytes(root / p)) for p in index_keys}
        with records.course_lock(root):
            save_json(path, plan)
        portal = publish_portal(plan, root)
        plan['portal_before'] = records.digest(state_bytes(portal))
        with records.course_lock(root):
            save_json(path, plan)
        # Actual generated indexes must contain the current relevant material/artifact links.
        index = (root / 'index.html').read_text(encoding='utf-8')
        for item in [*report['materials_checked'], *report['artifacts_checked']]:
            if item.get('kind') in {'solution', 'analysis_detail', 'checkpoint', 'course', 'material_map'}:
                continue
            if item['path'] in SETUP_FILES:
                continue
            is_abs = Path(item['path']).is_absolute()
            p = Path(item['path']) if is_abs else root / item['path']
            expected_url = files.relative_url(p, link_base if is_abs else root)
            if expected_url not in index:
                raise ValueError('Current delivered file is missing from the learner index: ' + str(p))
        for required in index_keys:
            if not (root / required).is_file() or (root / required).stat().st_size == 0:
                raise ValueError('Missing visible course navigation: ' + required)
        if has_manifest and report['inbox'] not in (root / 'index.md').read_text(encoding='utf-8'):
            raise ValueError('Future material inbox was not actually published')
        verified_index = verify_portal_links(portal, root, plan)
        report['index'] = str(verified_index)
        report['portal'] = str(portal)
    except (OSError, ValueError) as exc:
        report['status'] = 'incomplete';report['errors'].append(str(exc))
    with records.course_lock(root):
        records.check_pending(root)
        current_plan = json.loads(path.read_text(encoding='utf-8'))
        # Recheck relevant source bytes and artifacts after publication. No unrelated hashes.
        for item in [*report['materials_checked'], *report['artifacts_checked']]:
            p = Path(item['path']) if Path(item['path']).is_absolute() else root / item['path']
            if not p.is_file() or files.sha_file(p) != item['sha256']:
                report['errors'].append('Delivery changed during final publication: ' + str(p));report['status'] = 'incomplete'
        dependencies = [*plan['dependencies'], *[s for e in report['artifacts_checked'] for s in e['sources']]]
        for source in dependencies:
            p = files.plain_path(source['path'])
            if not p.is_file() or files.sha_file(p) != source['sha256']:
                report['errors'].append('Dependency changed during final publication: ' + str(p))
                report['status'] = 'incomplete'
        current_plan['status'] = report['status'];current_plan['last_check'] = report
        if not report['errors']:
            prior_path = metadata(root) / 'artifacts.json'
            prior = json.loads(prior_path.read_text()) if prior_path.exists() else {}
            for item in report['artifacts_checked']:
                prior[item['path']] = dict(item, run=run)
            save_json(prior_path, prior)
            current_plan['index_before'] = {p: records.digest(state_bytes(root / p)) for p in index_keys}
            current_plan['portal_before'] = records.digest(state_bytes(Path(plan['course_home']) / PORTAL))
        save_json(path, current_plan)
    publish_receipt(root, report)
    return report


def publish_receipt(root, report):
    # A small visible receipt is derived from the actual checker report, never a hand-ticked checklist.
    heading = '本次交付已核对' if not report['errors'] else '本次交付尚未完成'
    text = '# ' + heading + '\n\n任务：' + report['activity'] + '\n\n'
    text += '本批原资料核对：' + str(report['checked_supplied_files']) + ' 份；产出核对：' + str(len(report['artifacts_checked'])) + ' 份。\n\n'
    if report.get('inbox'):
        text += '以后新资料放入：' + report['inbox'] + '\n\n'
    else:
        text += '资料模式：沿用既有课程只读来源（未建资料清单）。\n\n'
    for item in report['artifacts_checked']:
        if item['kind'] != 'solution' and item['kind'] != 'analysis_detail':
            text += '- [' + item['path'] + '](' + quote(item['path'], safe='/') + ')\n'
    for error in report['errors']:
        text += '\n未完成：' + error + '\n'
    for item in report['pending']:
        text += '\n待确认：' + item['id'] + ' ' + item['reason'] + '\n'
    snapshot = records.read_records(root, ['delivery.md', 'delivery.json'])
    expected = {r['path']: r['sha256'] for r in snapshot['records']}
    records.write_bundle(root, 'main', [
        {'path': 'delivery.md', 'expected': expected['delivery.md'], 'content': text},
        {'path': 'delivery.json', 'expected': expected['delivery.json'], 'content': json.dumps(report, ensure_ascii=False, indent=2) + '\n'}])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    begin = sub.add_parser('begin')
    begin.add_argument('--course-home', required=True);begin.add_argument('--root')
    begin.add_argument('--materials-root');begin.add_argument('--course')
    begin.add_argument('--activity', choices=sorted(ACTIVITIES), required=True)
    begin.add_argument('--source-root', action='append', default=[])
    begin.add_argument('--request-json')
    for action in ('verify', 'finish'):
        p = sub.add_parser(action);p.add_argument('--root', required=True);p.add_argument('--run', required=True)
        if action == 'verify':
            p.add_argument('--materials-only', action='store_true', help='Verify the received batch before handing it to teaching/analysis')
    args = parser.parse_args()
    try:
        if args.command == 'begin':
            request = json.loads(Path(args.request_json).read_text(encoding='utf-8')) if args.request_json else {}
            report = begin_course(args.course_home, args.root, args.activity, request, args.course,
                                  args.materials_root, args.source_root)
        elif args.command == 'verify':
            report = verify_course(args.root, args.run, args.materials_only)
        else:
            report = finish_course(args.root, args.run)
        print(json.dumps(report, ensure_ascii=False))
        if report.get('status') == 'incomplete':
            raise SystemExit(2)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
