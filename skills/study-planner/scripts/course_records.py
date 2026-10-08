#!/usr/bin/env python3
"""Small version-checked course record writer. Role guards prevent mistakes, not bypasses."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import math
import uuid

MAIN_FILES = {'course.md', 'current.md', 'study-plan.md', 'materials.md', 'course-map.md'}
ROLE_FORMATS = {'main': {'lessons': {'.md'}, 'practice': {'.md'}, 'reviews': {'.json', '.html'}},
                'aside': {'side-notes': {'.md'}}, 'analyst': {'exam': {'.md', '.json'}},
                'questions': {'questions': {'.md', '.json'}}}
ROLE_DIRS = {role: set(directories) for role, directories in ROLE_FORMATS.items()}


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
    _, target = target_path(root, relative)
    data = target.read_bytes() if target.exists() else None
    return {'path': relative, 'sha256': digest(data),
            'content': None if data is None else data.decode('utf-8')}


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


def write_record(root, relative, role, expected, content, lock_timeout=2.0):
    check_role(role, relative)
    root, target = target_path(root, relative)
    data = content.encode('utf-8')
    if target.suffix == '.json':
        json.loads(content)  # Reject malformed source data before creating any record.
    with course_lock(root, lock_timeout):
        # Recheck after acquiring the lock; protect cooperating writers and manual edits.
        _, target = target_path(root, relative)
        previous = target.read_bytes() if target.exists() else None
        if digest(previous) != expected:
            raise ValueError('Stale record version; re-read and merge before writing')
        if role == 'aside' and previous is not None:
            raise ValueError('Aside notes are append-only independent files')
        if previous == data:
            return {'path': relative, 'sha256': digest(data), 'changed': False, 'backup': None}
        backup = None
        if previous is not None:
            history = root / '.history'
            if history.is_symlink():
                raise ValueError('History directory cannot be a symlink')
            history.mkdir(exist_ok=True)
            backup = history / (uuid.uuid4().hex + '-' + target.name)
            atomic_write(backup, previous)
        atomic_write(target, data)
        if target.read_bytes() != data:
            raise OSError('Read-back verification failed')
        return {'path': relative, 'sha256': digest(data), 'changed': True,
                'backup': None if backup is None else str(backup.relative_to(root))}


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
    for action in ('read', 'write', 'note'):
        cmd = sub.add_parser(action)
        cmd.add_argument('--root', required=True)
        if action != 'note':
            cmd.add_argument('--path', required=True)
        if action != 'read':
            cmd.add_argument('--role', required=True, choices=list(ROLE_DIRS))
            cmd.add_argument('--body-file', required=True)
            cmd.add_argument('--lock-timeout', type=float, default=2.0)
        if action == 'write':
            cmd.add_argument('--expected', required=True)
        if action == 'note':
            cmd.add_argument('--kind', choices=['aside', 'lesson', 'practice'])
    args = parser.parse_args()
    try:
        if args.command == 'read':
            result = read_record(args.root, args.path)
        else:
            body = Path(args.body_file).read_text(encoding='utf-8')
            if args.command == 'write':
                result = write_record(args.root, args.path, args.role, args.expected, body, args.lock_timeout)
            else:
                result = add_note(args.root, args.role, body, args.kind, args.lock_timeout)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, UnicodeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
