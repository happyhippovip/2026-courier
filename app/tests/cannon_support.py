"""Isolated integration harness: copied existing core, no production state/credentials."""
import contextlib
import importlib
import json
import os
import shutil
import sys
import types
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
_app_added = str(APP) not in sys.path
if _app_added:
    sys.path.insert(0, str(APP))
import cannon
import cannon.adapters
import cannon.controller
import cannon.core
import cannon.importer
import cannon.processes
import cannon.storage
import cannon.web
from cannon.core import CourierClient
from cannon.storage import ROOT, InstanceLock, atomic, digest, file_hash, owned
if _app_added and str(APP) in sys.path:
    sys.path.remove(str(APP))
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

CORE_MANIFEST = ROOT / 'data/cannon-tests/core-source-manifest.json'
FALLBACK_CANNON_DATA = ROOT / 'tmp_cannon_transfer/data/cannon-tests'
if not CORE_MANIFEST.exists() and (FALLBACK_CANNON_DATA / 'core-source-manifest.json').exists():
    CORE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FALLBACK_CANNON_DATA / 'core-source-manifest.json', CORE_MANIFEST)

def _cleanup_cannon_test_data():
    target = ROOT / 'data/cannon-tests'
    if target.exists():
        path_str = ('\\\\?\\' + os.path.abspath(str(target))) if os.name == 'nt' else str(target)
        shutil.rmtree(path_str, ignore_errors=True)

import atexit
atexit.register(_cleanup_cannon_test_data)

# This is a frozen local fixture, never an implicit acceptance of the live Core.
CORE_HASHES = json.loads(CORE_MANIFEST.read_text(encoding='utf-8'))
CORE_FIXTURE_ID = digest(CORE_HASHES)
SNAPSHOT = ROOT / 'data/cannon-tests/core-snapshots' / CORE_FIXTURE_ID


def _copy_matching_hash(source: Path, target: Path, expected: str):
    import hashlib
    raw = source.read_bytes()
    for candidate in (raw, raw.replace(b'\r\n', b'\n'), raw.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')):
        if hashlib.sha256(candidate).hexdigest() == expected:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(candidate)
            return
    raise ValueError('CORE_SNAPSHOT_MUTATED')


def snapshot():
    hashes = json.loads(CORE_MANIFEST.read_text(encoding='utf-8'))
    if hashes != CORE_HASHES:
        raise ValueError('CORE_FIXTURE_MANIFEST_CHANGED: restart the test process')
    with InstanceLock(SNAPSHOT.parent / (CORE_FIXTURE_ID + '-lock')):
        manifest_path = SNAPSHOT / 'manifest.json'
        published = manifest_path.exists()
        if published and json.loads(manifest_path.read_text(encoding='utf-8')) != hashes:
            raise ValueError('CORE_SNAPSHOT_MUTATED')
        for name, expected in hashes.items():
            relative = Path(name.replace('\\', '/'))
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('CORE_FIXTURE_PATH_INVALID')
            target = owned(SNAPSHOT / relative)
            if not target.is_file() and not published:
                source = ROOT / 'data/cannon-tests/core-snapshot' / relative
                if not source.is_file():
                    source = FALLBACK_CANNON_DATA / 'core-snapshot' / relative
                _copy_matching_hash(source, target, expected)
            if not target.is_file() or file_hash(target) != expected:
                raise ValueError('CORE_SNAPSHOT_MUTATED')
        actual = {p.relative_to(SNAPSHOT).as_posix() for p in SNAPSHOT.rglob('*.py')}
        expected_set = {Path(k.replace('\\', '/')).as_posix() for k in hashes}
        if actual != expected_set:
            raise ValueError('CORE_SNAPSHOT_UNEXPECTED_CODE')
        if not published:
            atomic(manifest_path, hashes)
    return hashes


def load_core():
    saved_sys_path = list(sys.path)
    saved_scripts_modules = {k: v for k, v in sys.modules.items() if k == 'scripts' or k.startswith('scripts.')}
    for k in list(saved_scripts_modules):
        sys.modules.pop(k, None)
    sys.path.insert(0, str(SNAPSHOT))
    try:
        # An unavailable keyring is explicitly forbidden in this fixture, never read.
        keyring = types.ModuleType('keyring')
        def forbidden(*a, **kw): raise AssertionError('Test attempted real credential access')
        keyring.get_password = forbidden; keyring.set_password = forbidden
        sys.modules['keyring'] = keyring
        os.environ.update(DISABLE_KEYRING='1', COURIER_API_KEY='isolated-worker-fixture',
                          COURIER_VERIFIER_API_KEY='isolated-verifier-fixture',
                          COURIER_STATE_FILE=str(SNAPSHOT / 'state.json'))
        # Suppress unrelated minute-based reaper while testing request handlers.
        with patch('threading.Thread.start'):
            spec = importlib.util.spec_from_file_location('isolated_courier_server', SNAPSHOT / 'server/app.py')
            api = importlib.util.module_from_spec(spec); spec.loader.exec_module(api)
        api.app.config['TESTING'] = False  # Do not enable runtime-binding test bypass.
        verifier = importlib.import_module('scripts.courier_verifier')
        return api, verifier
    finally:
        sys.path[:] = saved_sys_path
        for k in [m for m in list(sys.modules) if m == 'scripts' or m.startswith('scripts.')]:
            sys.modules.pop(k, None)
        sys.modules.update(saved_scripts_modules)


class IsolatedCore(CourierClient):
    isolated = True

    def __init__(self, api, verifier, directory, lanes=2, verify=True):
        self.api, self.verifier = api, verifier
        self.directory = owned(directory); self.directory.mkdir(parents=True, exist_ok=True)
        self.goal_ids = []; self.worker_ids = ['cannon-fake-1', 'cannon-fake-2'][:lanes]
        self.auto_verify = verify
        self.requests = []; self.claimed = []; self.verifications = []
        api.STATE_FILE = str(self.directory / 'canonical-state.json')
        api.BATCH_QUEUE_DIR = str(self.directory / 'batches')
        api._cached_state_json = None
        self.wait_patch = patch.object(api.NEW_WORK_CONDITION, 'wait', return_value=False)
        self.wait_patch.start()
        for worker in self.worker_ids:
            self.request('POST', '/workers/register', {'worker_id': worker, 'platform': 'windows',
                         'capabilities': ['windows', 'cannon.fake'], 'cost_class': 'free',
                         'provider': 'local-fixture', 'provider_available': True, 'capacity_available': True})

    def close(self):
        self.wait_patch.stop()

    def request(self, method, path, body=None, verifier=False):
        self.requests.append((method, path))
        with self.api.app.test_client() as client:
            response = client.open(path, method=method, json=body,
                headers={'Authorization': 'Bearer ' + ('isolated-verifier-fixture' if verifier else 'isolated-worker-fixture')})
        if response.status_code >= 400:
            raise ValueError(f'HTTP {response.status_code}: {response.get_json()}')
        return response.get_json()

    def add(self, steps, request_id='bounded-fixture'):
        result = self.request('POST', '/goals', {'goal_text': 'Local Cannon fixture', 'terminal': True,
                              'client_request_id': request_id, 'workflow_plan': steps})
        self.goal_ids.append(result['goal_id'])
        return result['goal_id']

    def claim(self, worker):
        result = super().claim(worker)
        if result:
            import time
            self.claimed.append({'task_id': result['task_id'], 'time': time.time(), 'execution_ref': result['execution_ref']})
        return result

    def after_result(self):
        if not self.auto_verify: return
        core = self
        class Response:
            def __init__(self, value): self.value = value; self.status_code = 200; self.text = ''
            def json(self): return self.value
        class Requests:
            @staticmethod
            def get(url, **kwargs):
                return Response(core.request('GET', '/tasks/pending_verification', verifier=True))
            @staticmethod
            def post(url, json, **kwargs):
                result = core.request('POST', '/tasks/verify', json, verifier=True)
                core.verifications.append(json)
                return Response(result)
        class EndOfCycle(BaseException): pass
        def end(seconds): raise EndOfCycle()
        # Execute the unmodified verifier loop once; transport and clock only are
        # replaced. Its artifact hashing and payload logic are real source code.
        with patch.object(self.verifier, 'requests', Requests), patch.object(self.verifier, 'time', types.SimpleNamespace(sleep=end)):
            try: self.verifier.run_loop()
            except EndOfCycle: pass


def step(name, **extra):
    return {'task_id': name, 'instruction': 'Cannon harmless local output: ' + name,
            'target_agent': 'windows', 'required_capabilities': ['cannon.fake'],
            'artifacts': ['outputs/' + name + '.txt'], **extra}
