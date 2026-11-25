#!/usr/bin/env python3
"""Recoverable material intake. Callers hold the course-record lock."""
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil

import course_records as records

MOVE_PENDING = '.course-moves.pending.json'


def safe_path(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Move paths must be absolute without ..')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Move paths cannot traverse symlinks')
    return path


def beneath(path, root):
    return path == root or root in path.parents


def file_hash(path):
    path = safe_path(path)
    if not path.is_file():
        raise ValueError('Move file is missing or not a regular file: ' + str(path))
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns')
    if any(getattr(before, key) != getattr(after, key) for key in fields):
        raise ValueError('File changed while checking material move: ' + str(path))
    return digest.hexdigest()


def pending_path(root):
    return safe_path(safe_path(root) / MOVE_PENDING)


def check_pending(root):
    if pending_path(root).exists():
        raise ValueError('Incomplete material move; run move-recover --decision finish or abort before continuing')


def _record_bundle_pending(root):
    # Ordinary record operations reject our journal too; recovery only checks
    # the separate bundle journal, so it can repair its own pending move.
    if records.journal_path(root).exists():
        raise ValueError('Recover the incomplete course record bundle before material moves')


def _write_plan(root, plan):
    records.atomic_write(pending_path(root),
                         (json.dumps(plan, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def identity(path):
    stat = safe_path(path).stat()
    return [stat.st_dev, stat.st_ino]


def publish_target(source, target, digest, copy=False, stage=None):
    """Publish complete bytes without replacement; hidden stage proves ownership.

    Same-filesystem moves use links until the registry commits, then unlink the
    source. Cross-filesystem intake stages a verified copy before the same commit.
    Explicit copies always use independent bytes rather than a shared inode.
    """
    source, target = safe_path(source), safe_path(target)
    if stage is None:
        if file_hash(target) != digest:
            raise ValueError('Existing target changed during material move')
        return False
    stage = safe_path(stage)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not stage.exists():
        if file_hash(source) != digest:
            raise ValueError('Source changed during material move')
        linked = False
        if not copy:
            try:
                os.link(source, stage)
                linked = True
            except OSError as exc:
                if exc.errno not in (errno.EXDEV, errno.EPERM, errno.EOPNOTSUPP, errno.ENOTSUP):
                    raise
        if not linked:
            # Exclusive creation prevents replacing a conflicting staging file.
            with stage.open('xb') as stream, source.open('rb') as incoming:
                shutil.copyfileobj(incoming, stream, 1024 * 1024)
                stream.flush()
                os.fsync(stream.fileno())
            shutil.copystat(source, stage)
    if file_hash(stage) != digest or (source.exists() and file_hash(source) != digest):
        raise ValueError('Source or staged bytes changed during material move')
    if target.exists():
        if not os.path.samefile(stage, target) or file_hash(target) != digest:
            raise ValueError('Material target collision; preserve files and recover explicitly')
    else:
        os.link(stage, target)  # atomic no-replace publication
    if file_hash(target) != digest:
        raise ValueError('Material target read-back failed')
    return True


def commit_registry(root, before_bytes, after_bytes):
    _record_bundle_pending(root)
    _, path = records.target_path(root, 'materials.json')
    current = path.read_bytes()
    if current == after_bytes:
        return
    if current != before_bytes:
        raise ValueError('Material registry changed; keep pending move and merge explicitly')
    if current != after_bytes:
        records.backup_record(root, path, current)
        records.atomic_write(path, after_bytes)
    if path.read_bytes() != after_bytes:
        raise OSError('Material registry read-back failed')


def remove_source(path, digest):
    path = safe_path(path)
    if not path.exists():
        return False
    before = path.stat()
    if file_hash(path) != digest:
        raise ValueError('Source changed; will not remove it: ' + str(path))
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('Source changed; will not remove it: ' + str(path))
    path.unlink()
    return True


def _validated_plan(root, plan):
    from course_files import validate_registry

    root = safe_path(root)
    if not isinstance(plan, dict) or plan.get('schema_version') != 1:
        raise ValueError('Invalid material move journal')
    before = plan.get('registry_before')
    after = plan.get('registry_after')
    if not isinstance(before, str) or not isinstance(after, str):
        raise ValueError('Move journal requires exact registry versions')
    old, new = validate_registry(json.loads(before)), validate_registry(json.loads(after))
    if any(old[key] != new[key] for key in ('course_id', 'materials_root', 'source_roots')):
        raise ValueError('Move journal cannot change course identity or source roots')
    managed = safe_path(old['materials_root'])
    if beneath(managed, root) or beneath(root, managed):
        raise ValueError('Move materials must be separate from course records')
    source_roots = [safe_path(p) for p in old['source_roots']]
    target_info = plan.get('target')
    sources = plan.get('sources')
    if not isinstance(target_info, dict) or not isinstance(sources, list) or not sources:
        raise ValueError('Invalid move source/target plan')
    target = safe_path(target_info.get('path', ''))
    digest = target_info.get('sha256')
    entries = [e for e in new['entries'] if e['path'] == str(target) and e['sha256'] == digest]
    if len(entries) != 1 or target.parent != managed / entries[0]['category']:
        raise ValueError('Move target must match one canonical registry entry')
    entry = entries[0]
    if not isinstance(target_info.get('created'), bool):
        raise ValueError('Move target ownership must be explicit')
    stage = plan.get('stage')
    if stage is not None:
        stage = safe_path(stage)
        if stage.parent != target.parent or not stage.name.startswith('.intake-move-'):
            raise ValueError('Invalid move staging path')
    if target_info['created'] != (stage is not None):
        raise ValueError('New material target requires an owned staging path')
    target_identity = target_info.get('identity')
    if target_identity is not None and (not isinstance(target_identity, list) or
            len(target_identity) != 2 or any(type(x) is not int for x in target_identity)):
        raise ValueError('Invalid move target identity')
    paths = set()
    known = {(e['path'], e['sha256']) for e in old['entries']}
    known.update((v['path'], v['sha256']) for e in old['entries'] for v in e.get('versions', []))
    received = {(x.get('path'), x.get('sha256')) for x in entry.get('received_sources', []) if isinstance(x, dict)}
    for source in sources:
        if not isinstance(source, dict) or source.get('sha256') != digest or type(source.get('remove')) is not bool:
            raise ValueError('Invalid move source version')
        path = safe_path(source.get('path', ''))
        if path in paths or beneath(path, root) or not any(beneath(path, p) for p in source_roots):
            raise ValueError('Move source is repeated or outside declared material roots')
        paths.add(path)
        if source['remove'] and path == target:
            raise ValueError('Move cannot remove its canonical target')
        if (str(path), digest) not in received and (str(path), digest) not in known:
            raise ValueError('Move source has no matching registry provenance')
        if any(v['path'] == str(path) for e in new['entries'] for v in e.get('versions', [])) and source['remove']:
            raise ValueError('Move cannot remove a retained historical version')
    return before.encode('utf-8'), after.encode('utf-8'), target, stage, digest


def _preflight(root, plan):
    before, after, target, stage, digest = _validated_plan(root, plan)
    _record_bundle_pending(root)
    _, path = records.target_path(root, 'materials.json')
    if path.read_bytes() not in (before, after):
        raise ValueError('Material registry changed; pending move needs explicit conflict repair')
    # Fail before any recovery mutation if a source, target or owned stage changed.
    for source in plan['sources']:
        p = safe_path(source['path'])
        if p.exists() and file_hash(p) != digest:
            raise ValueError('Source changed; preserve it and pending move: ' + str(p))
    if target.exists() and file_hash(target) != digest:
        raise ValueError('Target changed; preserve it and pending move: ' + str(target))
    if stage is not None and stage.exists() and file_hash(stage) != digest:
        raise ValueError('Staged file changed; preserve it and pending move')
    if target.exists() and plan['target']['created']:
        owned = (stage is not None and stage.exists() and os.path.samefile(stage, target))
        owned = owned or plan['target'].get('identity') == identity(target)
        if not owned:
            raise ValueError('Target ownership conflict; preserve it and pending move')
    return before, after, target, stage, digest


def _complete(root, plan, decision):
    before, after, target, stage, digest = _preflight(root, plan)
    if decision == 'finish':
        if not target.exists():
            source = next((safe_path(s['path']) for s in plan['sources'] if safe_path(s['path']).exists()), None)
            if source is None and (stage is None or not stage.exists()):
                raise ValueError('No matching bytes remain to finish material move')
            # A surviving stage may be the only bytes after an external deletion.
            source = source or stage
            publish_target(source, target, digest, copy=plan.get('mode') == 'copy', stage=stage)
        elif stage is not None and stage.exists() and not os.path.samefile(stage, target):
            raise ValueError('Staging/target ownership conflict')
        plan['target']['identity'] = identity(target)
        _write_plan(root, plan)
        commit_registry(root, before, after)
        # Recheck the whole deletion set after publication; edits are never removed.
        _preflight(root, plan)
        removed = []
        for source in plan['sources']:
            if source['remove'] and remove_source(source['path'], digest):
                removed.append(source['path'])
    elif decision == 'abort':
        # Restore missing originals before reverting the registry or target. No
        # existing file is overwritten, including a user edit made after a crash.
        originals = [safe_path(s['path']) for s in plan['sources'] if s['remove']]
        for original in originals:
            if not original.exists():
                donor = target if target.exists() else stage
                if donor is None or not donor.exists():
                    raise ValueError('No matching bytes remain to restore a moved source')
                original.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(donor, original)
                except OSError as exc:
                    if exc.errno not in (errno.EXDEV, errno.EPERM, errno.EOPNOTSUPP, errno.ENOTSUP):
                        raise
                    with original.open('xb') as stream, donor.open('rb') as incoming:
                        shutil.copyfileobj(incoming, stream, 1024 * 1024)
                        stream.flush()
                        os.fsync(stream.fileno())
                if file_hash(original) != digest:
                    raise ValueError('Restored move source failed verification')
        commit_registry(root, after, before)
        if plan['target']['created'] and target.exists():
            remove_source(target, digest)
        removed = []
    else:
        raise ValueError('Choose finish or abort for move recovery')
    if stage is not None and stage.exists():
        remove_source(stage, digest)
    pending_path(root).unlink()
    return {'decision': decision, 'removed_sources': removed, 'recovered': True,
            'registry_sha256': records.digest(after if decision == 'finish' else before)}


def start_move(root, plan):
    check_pending(root)
    _validated_plan(root, plan)
    _preflight(root, plan)
    _write_plan(root, plan)  # persisted before creating target or removing any bytes
    # Keep the initial publication as a separate patch point for interruption tests.
    target = safe_path(plan['target']['path'])
    source = safe_path(plan['sources'][0]['path'])
    publish_target(source, target, plan['target']['sha256'],
                   copy=plan.get('mode') == 'copy', stage=plan.get('stage'))
    return _complete(root, plan, 'finish')


def recover_moves(root, decision='finish'):
    root = safe_path(root)
    if decision not in ('finish', 'abort'):
        raise ValueError('Choose finish or abort for move recovery')
    with records.course_lock(root):
        path = pending_path(root)
        if not path.exists():
            return {'decision': decision, 'recovered': False, 'removed_sources': []}
        try:
            plan = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, UnicodeError) as exc:
            raise ValueError('Invalid material move journal; preserve it for explicit repair') from exc
        return _complete(root, plan, decision)
