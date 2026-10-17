#!/usr/bin/env python3
"""Small version-checked course record writer. Role guards prevent mistakes, not bypasses."""
import argparse
import contextlib
try:
    import fcntl
except ImportError:  # Read-only tools can load on other platforms.
    fcntl = None
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import math
import uuid

MAIN_FILES = {'course.md', 'current.md', 'study-plan.md', 'materials.md', 'course-map.md', 'materials.json', 'materials-index.md', 'index.md', 'index.html'}
ROLE_FORMATS = {'main': {'lessons': {'.md'}, 'practice': {'.md'}, 'reviews': {'.json', '.html'}, 'transcripts': {'.md', '.json'}},
                'aside': {'side-notes': {'.md'}}, 'analyst': {'exam': {'.md', '.json'}},
                'questions': {'questions': {'.md', '.json'}},
                'notes': {'notes': {'.html', '.json'}}}
ROLE_DIRS = {role: set(directories) for role, directories in ROLE_FORMATS.items()}
PENDING = '.course-records.pending.json'


def journal_path(root):
    path = root / PENDING
    if path.is_symlink():
        raise ValueError('Pending journal cannot be a symlink')
    return path


def check_pending(root):
    if journal_path(root).exists():
        raise ValueError('Incomplete record bundle; main or its analyst owner must run recover before reading or writing shared records')


def target_path(root, relative):
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts or rel.parts[0].startswith('.'):
        raise ValueError('Use a course-relative public record path without ..')
    root = Path(root).resolve()
    candidate = root / rel
    # Reject symlink records, including internal links, to avoid replacing the link itself.
    for parent in [candidate, *candidate.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError('Record paths cannot traverse symlinks')
    candidate.resolve().relative_to(root)
    return root, candidate


def digest(data):
    return 'absent' if data is None else hashlib.sha256(data).hexdigest()


def read_record(root, relative):
    root, target = target_path(root, relative)
    check_pending(root)
    data = target.read_bytes() if target.exists() else None
    check_pending(root)
    return {'path': relative, 'sha256': digest(data),
            'content': None if data is None else data.decode('utf-8')}


def read_records(root, relatives, lock_timeout=2.0):
    """Read related files while holding the same lock as cooperating writers."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Record root must already exist for read-set')
    if not isinstance(relatives, list) or not relatives or any(not isinstance(p, str) for p in relatives):
        raise ValueError('Read-set requires a nonempty list of record paths')
    paths = [str(target_path(root, p)[1].relative_to(root)) for p in relatives]
    if len(set(paths)) != len(paths):
        raise ValueError('Duplicate read-set record path')
    with course_lock(root, lock_timeout):
        check_pending(root)
        result = []
        for relative in paths:
            _, target = target_path(root, relative)
            data = target.read_bytes() if target.exists() else None
            result.append({'path': relative, 'sha256': digest(data),
                           'content': None if data is None else data.decode('utf-8')})
        check_pending(root)
        return {'records': result}


def check_role(role, relative):
    rel = Path(relative)
    if role not in ROLE_FORMATS:
        raise ValueError('Unsupported role')
    if role == 'main' and relative in MAIN_FILES:
        return
    if len(rel.parts) < 2 or rel.parts[0] not in ROLE_FORMATS[role]:
        raise ValueError('Role cannot write this record path')
    if rel.suffix not in ROLE_FORMATS[role][rel.parts[0]]:
        raise ValueError('Unsupported record type for this role/path')


@contextlib.contextmanager
def course_lock(root, timeout=2.0):
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 <= timeout <= 30:
        raise ValueError('Lock timeout must be between 0 and 30 seconds')
    if fcntl is None:
        raise ValueError('Record writing and read-set require POSIX flock (macOS/Linux); Windows coordination is not supported')
    root.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(root / '.course-records.lock', flags, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError('Course records busy; re-read and retry after lock timeout') from exc
                time.sleep(min(.05, remaining))
        yield
    finally:
        os.close(fd)


def atomic_write(target, data):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + target.name + '.', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def backup_record(root, target, previous):
    if previous is None:
        return None
    history = root / '.history'
    if history.is_symlink():
        raise ValueError('History directory cannot be a symlink')
    history.mkdir(exist_ok=True)
    backup = history / (uuid.uuid4().hex + '-' + target.name)
    atomic_write(backup, previous)
    return str(backup.relative_to(root))


def write_record(root, relative, role, expected, content, lock_timeout=2.0):
    check_role(role, relative)
    root, target = target_path(root, relative)
    data = content.encode('utf-8')
    if target.suffix == '.json':
        json.loads(content)  # Reject malformed source data before creating any record.
    with course_lock(root, lock_timeout):
        check_pending(root)
        # Recheck after acquiring the lock; protect cooperating writers and manual edits.
        _, target = target_path(root, relative)
        previous = target.read_bytes() if target.exists() else None
        if digest(previous) != expected:
            raise ValueError('Stale record version; re-read and merge before writing')
        if role == 'aside' and previous is not None:
            raise ValueError('Aside notes are append-only independent files')
        if previous == data:
            return {'path': relative, 'sha256': digest(data), 'changed': False, 'backup': None}
        backup = backup_record(root, target, previous)
        atomic_write(target, data)
        if target.read_bytes() != data:
            raise OSError('Read-back verification failed')
        return {'path': relative, 'sha256': digest(data), 'changed': True,
                'backup': backup}


def bundle_entries(root, updates, role='main'):
    if not isinstance(updates, list) or not updates:
        raise ValueError('Bundle requires a nonempty updates list')
    entries, seen = [], set()
    for update in updates:
        if not isinstance(update, dict) or set(update) != {'path', 'expected', 'content'}:
            raise ValueError('Each bundle update requires path, expected, content only')
        relative, expected, content = update['path'], update['expected'], update['content']
        if not all(isinstance(value, str) for value in (relative, expected, content)):
            raise ValueError('Bundle fields must be strings')
        check_role(role, relative)
        _, target = target_path(root, relative)
        canonical = str(target.relative_to(root))
        if canonical in seen:
            raise ValueError('Duplicate bundle record path')
        seen.add(canonical)
        if expected != 'absent' and (len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected)):
            raise ValueError('Expected version must be a SHA256 or absent')
        if target.suffix == '.json':
            json.loads(content)
        entries.append(dict(path=canonical, expected=expected, content=content))
    # Publish the resume checkpoint only after the records it describes.
    return sorted(entries, key=lambda entry: entry['path'] == 'current.md')


def apply_journal(root, journal):
    decision, entries = journal['decision'], journal['updates']
    preserved = []
    # Preflight the entire recovery before overwriting any public record.
    for entry in entries:
        _, target = target_path(root, entry['path'])
        actual = digest(target.read_bytes() if target.exists() else None)
        if actual not in {entry['expected'], digest(entry['content'].encode('utf-8'))}:
            if decision == 'finish':
                raise ValueError('Recovery conflicts with a manual edit at ' + entry['path'] + '; preserve it, then abort and re-read/merge')
            preserved.append(entry['path'])
    for entry in entries:
        _, target = target_path(root, entry['path'])
        current = target.read_bytes() if target.exists() else None
        desired = entry['content'].encode('utf-8') if decision == 'finish' else (
            None if entry['previous'] is None else entry['previous'].encode('utf-8'))
        if digest(current) not in {entry['expected'], digest(entry['content'].encode('utf-8'))}:
            if decision == 'finish':
                raise ValueError('Record changed during recovery; journal retained')
            if entry['path'] not in preserved:
                preserved.append(entry['path'])
            continue
        if current != desired:
            if desired is None:
                target.unlink()
            else:
                atomic_write(target, desired)
        if (target.read_bytes() if target.exists() else None) != desired:
            raise OSError('Bundle read-back verification failed; journal retained')
    # Retain canceled content as well, including new records that were rolled back.
    if decision == 'abort':
        backup_record(root, journal_path(root), json.dumps(journal, ensure_ascii=False).encode('utf-8'))
    journal_path(root).unlink()
    return {'decision': decision, 'paths': [entry['path'] for entry in entries],
            'preserved_manual_edits': preserved, 'recovered': True}


def write_bundle(root, role, updates, lock_timeout=2.0):
    if role not in {'main', 'analyst'}:
        raise ValueError('Only main or analyst can bundle shared records')
    root = Path(root).resolve()
    entries = bundle_entries(root, updates, role)
    with course_lock(root, lock_timeout):
        check_pending(root)
        changed = []
        for entry in entries:
            _, target = target_path(root, entry['path'])
            previous = target.read_bytes() if target.exists() else None
            if digest(previous) != entry['expected']:
                raise ValueError('Stale bundle version at ' + entry['path'] + '; re-read and merge')
            if previous != entry['content'].encode('utf-8'):
                changed.append(dict(entry, previous=None if previous is None else previous.decode('utf-8')))
        if not changed:
            return {'changed': False, 'paths': [], 'recovered': False}
        for entry in changed:
            backup_record(root, root / entry['path'], None if entry['previous'] is None else entry['previous'].encode('utf-8'))
        journal = {'version': 2, 'role': role, 'decision': 'finish', 'updates': changed}
        atomic_write(journal_path(root), (json.dumps(journal, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        return dict(apply_journal(root, journal), changed=True, recovered=False)


def recover_bundle(root, role, decision=None, lock_timeout=2.0):
    if role not in {'main', 'analyst'}:
        raise ValueError('Only main or analyst can recover shared records')
    root = Path(root).resolve()
    with course_lock(root, lock_timeout):
        path = journal_path(root)
        if not path.exists():
            return {'recovered': False, 'paths': []}
        journal = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(journal, dict) or type(journal.get('version')) is not int:
            raise ValueError('Unsupported pending journal; preserve it for inspection')
        version = journal['version']
        if version == 1 and set(journal) == {'version', 'decision', 'updates'}:
            owner = 'main'  # Recover bundles saved by v0.2.7 and earlier.
        elif version == 2 and set(journal) == {'version', 'role', 'decision', 'updates'} and isinstance(journal['role'], str) and journal['role'] in {'main', 'analyst'}:
            owner = journal['role']
        else:
            raise ValueError('Unsupported pending journal; preserve it for inspection')
        if not isinstance(journal['decision'], str) or journal['decision'] not in {'finish', 'abort'}:
            raise ValueError('Unsupported pending journal; preserve it for inspection')
        if role == 'analyst' and owner != 'analyst':
            raise ValueError('Analyst cannot recover a main bundle')
        raw_entries = journal['updates']
        if not isinstance(raw_entries, list) or any(not isinstance(e, dict) or set(e) != {'path', 'expected', 'content', 'previous'} for e in raw_entries):
            raise ValueError('Invalid pending entries')
        entries = bundle_entries(root, [{k: e[k] for k in ('path', 'expected', 'content')} for e in raw_entries], owner)
        if any(str(target_path(root, e['path'])[1].relative_to(root)) != e['path'] for e in raw_entries):
            raise ValueError('Pending journal paths must be canonical')
        originals = {e['path']: e['previous'] for e in raw_entries}
        for entry in entries:
            previous = originals[entry['path']]
            if previous is not None and not isinstance(previous, str):
                raise ValueError('Invalid previous record content')
            if digest(None if previous is None else previous.encode('utf-8')) != entry['expected']:
                raise ValueError('Pending original content/version mismatch')
            entry['previous'] = previous
        if decision not in {None, 'finish', 'abort'} or (journal['decision'] == 'abort' and decision == 'finish'):
            raise ValueError('Cannot change an abort recovery back to finish')
        journal = dict(journal, updates=entries)
        if decision == 'abort' and journal['decision'] != 'abort':
            journal['decision'] = 'abort'
            atomic_write(path, (json.dumps(journal, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        return apply_journal(root, journal)


def add_note(root, role, content, kind=None, lock_timeout=2.0):
    if role == 'aside':
        if kind not in (None, 'aside'):
            raise ValueError('Aside role only creates aside notes')
        directory = 'side-notes'
    elif role == 'main' and kind in ('lesson', 'practice'):
        directory = {'lesson': 'lessons', 'practice': 'practice'}[kind]
    else:
        raise ValueError('Main notes require --kind lesson or practice')
    note_id = uuid.uuid4().hex
    body = '<!-- record-id: ' + note_id + ' -->\n\n' + content
    result = write_record(root, directory + '/' + note_id + '.md', role, 'absent', body, lock_timeout)
    return dict(result, id=note_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for action in ('read', 'read-set', 'write', 'note', 'bundle', 'recover'):
        cmd = sub.add_parser(action)
        cmd.add_argument('--root', required=True)
        if action in ('read', 'write'):
            cmd.add_argument('--path', required=True)
        if action == 'read-set':
            cmd.add_argument('--paths', required=True, nargs='+')
        if action not in ('read', 'read-set'):
            cmd.add_argument('--role', required=True, choices=list(ROLE_DIRS))
            if action != 'recover':
                cmd.add_argument('--body-file', required=True)
        if action != 'read':
            cmd.add_argument('--lock-timeout', type=float, default=2.0)
        if action == 'write':
            cmd.add_argument('--expected', required=True)
        if action == 'note':
            cmd.add_argument('--kind', choices=['aside', 'lesson', 'practice'])
        if action == 'recover':
            cmd.add_argument('--decision', choices=['finish', 'abort'])
    args = parser.parse_args()
    try:
        if args.command == 'read':
            result = read_record(args.root, args.path)
        elif args.command == 'read-set':
            result = read_records(args.root, args.paths, args.lock_timeout)
        elif args.command == 'recover':
            result = recover_bundle(args.root, args.role, args.decision, args.lock_timeout)
        else:
            body = Path(args.body_file).read_text(encoding='utf-8')
            if args.command == 'write':
                result = write_record(args.root, args.path, args.role, args.expected, body, args.lock_timeout)
            elif args.command == 'note':
                result = add_note(args.root, args.role, body, args.kind, args.lock_timeout)
            else:
                payload = json.loads(body)
                if not isinstance(payload, dict) or set(payload) != {'updates'}:
                    raise ValueError('Bundle body requires updates only')
                result = write_bundle(args.root, args.role, payload['updates'], args.lock_timeout)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, UnicodeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
