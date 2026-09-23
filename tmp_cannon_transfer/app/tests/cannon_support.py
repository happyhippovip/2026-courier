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
sys.path.insert(0, str(APP))
from cannon.core import CourierClient
from cannon.storage import ROOT, InstanceLock, atomic, digest, file_hash, owned

CORE_MANIFEST = ROOT / 'data/cannon-tests/core-source-manifest.json'
# This is a frozen local fixture, never an implicit acceptance of the live Core.
CORE_HASHES = json.loads(CORE_MANIFEST.read_text(encoding='utf-8'))
NORMALIZED_HASHES = {k.replace('\\', '/'): v for k, v in CORE_HASHES.items()}
CORE_FIXTURE_ID = digest(CORE_HASHES)
SNAPSHOT = ROOT / 'data/cannon-tests/core-snapshots' / CORE_FIXTURE_ID


def snapshot():
    hashes = json.loads(CORE_MANIFEST.read_text(encoding='utf-8'))
    if hashes != CORE_HASHES:
        raise ValueError('CORE_FIXTURE_MANIFEST_CHANGED: restart the test process')
    with InstanceLock(SNAPSHOT.parent / (CORE_FIXTURE_ID + '-lock')):
        manifest_path = SNAPSHOT / 'manifest.json'
        published = manifest_path.exists()
        if published and json.loads(manifest_path.read_text(encoding='utf-8')) != hashes:
            raise ValueError('CORE_SNAPSHOT_MUTATED')
        for name, expected in NORMALIZED_HASHES.items():
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('CORE_FIXTURE_PATH_INVALID')
            target = owned(SNAPSHOT / relative)
            if not target.is_file() and not published:
                source = ROOT / 'data/cannon-tests/core-snapshot' / relative
                if file_hash(source) != expected:
                    raise ValueError('CORE_SNAPSHOT_MUTATED')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            if not target.is_file() or file_hash(target) != expected:
                raise ValueError('CORE_SNAPSHOT_MUTATED')
        actual = {str(p.relative_to(SNAPSHOT)).replace('\\', '/') for p in SNAPSHOT.rglob('*.py')}
        if actual != set(NORMALIZED_HASHES.keys()):
            raise ValueError('CORE_SNAPSHOT_UNEXPECTED_CODE')
        if not published:
            atomic(manifest_path, hashes)
    return hashes


def load_core():
    sys.path.insert(0, str(SNAPSHOT))
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
