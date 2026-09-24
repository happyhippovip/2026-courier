import hashlib
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def owned(path):
    path = Path(path).resolve()
    def comparable(value):
        text = str(value)
        if os.name == 'nt':
            if text.startswith('\\\\?\\UNC\\'):
                text = '\\\\' + text[8:]
            elif text.startswith('\\\\?\\'):
                text = text[4:]
        return Path(text)
    candidate, root = comparable(path), comparable(ROOT.resolve())
    if not candidate.is_relative_to(root) or candidate == root:
        raise ValueError(f'Cannon path outside owned workspace: {path}; root={ROOT.resolve()}')
    return _fs_path(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def _fs_path(path):
    p = Path(path)
    if os.name == 'nt':
        s = str(p)
        if not s.startswith('\\\\?\\'):
            try:
                resolved = str(p.resolve())
            except OSError:
                resolved = os.path.abspath(s)
            if len(resolved) >= 140:
                if resolved.startswith('\\\\'):
                    return Path('\\\\?\\UNC\\' + resolved[2:])
                return Path('\\\\?\\' + resolved)
    return p


def file_hash(path):
    h = hashlib.sha256()
    with _fs_path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def atomic(path, value):
    path = owned(path)
    fs_target = _fs_path(path)
    fs_target.parent.mkdir(parents=True, exist_ok=True)
    tmp = _fs_path(path.with_name(path.name + '.tmp'))
    with tmp.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    # Windows readers can briefly deny delete-sharing on the destination.
    # Keep the old durable file intact and retry the atomic replacement only.
    for attempt in range(8):
        try:
            os.replace(tmp, fs_target)
            break
        except PermissionError as exc:
            if os.name != 'nt' or getattr(exc, 'winerror', None) not in {5, 32, 33} or attempt == 7:
                raise
            time.sleep(min(.01 * 2**attempt, .16))


def read(path, default=None):
    fs_target = _fs_path(path)
    if not fs_target.exists():
        return default
    # Corrupt operational state is never silently treated as an empty queue.
    return json.loads(fs_target.read_text(encoding='utf-8'))


class InstanceLock:
    def __init__(self, directory):
        self.directory = owned(directory)
        self.file = None

    def __enter__(self):
        fs_dir = _fs_path(self.directory)
        fs_dir.mkdir(parents=True, exist_ok=True)
        self.file = _fs_path(self.directory / 'controller.lock').open('a+b')
        try:
            if os.fstat(self.file.fileno()).st_size == 0:
                self.file.write(b'0'); self.file.flush()
            self.file.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close(); self.file = None
            raise RuntimeError('CANNON_ALREADY_RUNNING')
        return self

    def __exit__(self, *exc):
        if self.file:
            self.file.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            self.file.close(); self.file = None
