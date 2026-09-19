"""Bounded real local HTTP/process checks. No Muse/provider execution."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest
from urllib.request import Request, urlopen
import uuid
from unittest.mock import patch

from cannon_support import APP, ROOT
from cannon.storage import atomic, read
from cannon import storage


class V0Tests(unittest.TestCase):
    def setUp(self):
        self.directory = ROOT / 'data/cannon-tests/v0' / (self._testMethodName + '-' + uuid.uuid4().hex[:8])
        self.directory.mkdir(parents=True)
        self.server = None
        self.err = None
        self.addCleanup(self.stop_server)

    def request(self, path, body=None):
        headers = {}
        if body is not None:
            headers = {'Content-Type': 'application/json', 'Origin': self.base,
                       'X-Symphony-Token': self.status()['token']}
        req = Request(self.base + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
        with urlopen(req, timeout=3) as response:
            return json.load(response)

    def status(self):
        return self.request('/api/cannon/status')

    def action(self, action, count=5):
        return self.request('/api/cannon/action', {'action': action, 'mode': 'NORMAL', 'count': count})

    def start_server(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        self.base = 'http://127.0.0.1:' + str(port)
        env = dict(os.environ, CANNON_DEMO_DIR=str(self.directory / 'runs'),
                   PYTHONPATH=os.pathsep.join([str(APP), str(ROOT / '.venv/Lib/site-packages')]),
                   PYTHONDONTWRITEBYTECODE='1')
        self.err = (self.directory / ('server-' + str(port) + '.log')).open('wb')
        self.server = subprocess.Popen([sys._base_executable, '-B', str(APP / 'server.py'),
                                        '--cannon-only', '--port', str(port)], cwd=ROOT, env=env,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=self.err,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if self.server.poll() is not None: self.fail('Owned test server exited')
            try:
                identity = self.request('/api/identity')
                self.assertEqual(identity['root'], str(ROOT))
                return
            except OSError:
                time.sleep(.03)
        self.fail('Owned test server not ready')

    def stop_server(self):
        if self.server is not None:
            if self.server.poll() is None:
                try: self.request('/api/shutdown', {})
                except OSError: pass
                try: self.server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.server.kill(); self.server.wait(timeout=5)  # exact owned handle
            self.server = None
        if self.err is not None: self.err.close(); self.err = None

    def wait(self, predicate):
        deadline = time.monotonic() + 85
        while time.monotonic() < deadline:
            status = self.status()
            if predicate(status): return status
            if status['error']: self.fail(status['error'])
            time.sleep(.03)
        self.fail('Bounded condition not reached: ' + json.dumps(status))

    def control_at_second(self, action):
        self.start_server()
        self.action('START')
        at_second = self.wait(lambda s: s['state'].get('metrics', {}).get('STARTED') == 2 and s['state'].get('active_lanes') == 1)
        self.action(action)
        stopped = self.wait(lambda s: not s['helper_active'])
        self.assertEqual(stopped['helper_exit'], 0)
        self.assertEqual(stopped['state']['metrics']['DONE'], 2)
        self.assertEqual(stopped['state']['metrics']['STARTED'], 2)
        self.assertEqual(stopped['state']['counts']['QUEUED'], 3)
        self.assertEqual(stopped['state']['active_lanes'], 0)
        self.assertIsNone(stopped['error'])
        return at_second, stopped

    def inspect_results(self, status, expected):
        directory = Path(status['demo_directory'])
        state = read(directory / 'core/canonical-state.json')
        tasks = list(state['tasks'].values())
        completed = [t for t in tasks if t['status'] == 'RECONCILED']
        self.assertEqual(len(completed), expected)
        for task in completed:
            self.assertEqual(task['verification']['verdict'], 'PASS')
            self.assertEqual(task['result']['result_id'], task['verification']['result_id'])
        events = sorted([read(p) for p in (directory / 'controller/executions').glob('*/event.json')], key=lambda e: e['start'])
        self.assertEqual(len(events), expected)
        self.assertEqual(len({e['execution_ref'] for e in events}), expected)
        for a, b in zip(events, events[1:]): self.assertLessEqual(a['end'], b['start'])
        completions = {read(p)['execution_ref']: read(p) for p in
                       (directory / 'controller/executions').glob('*/completion.json')}
        self.assertEqual(len(completions), expected)
        gaps = []
        for a, b in zip(events, events[1:]):
            completion = completions[a['execution_ref']]
            gap = b['start'] - completion['confirmed_at']
            self.assertGreaterEqual(gap, 5)
            self.assertGreaterEqual(b['start'], completion['next_task_not_before'])
            gaps.append(gap)
        atomic(self.directory / 'cooldown-proof.json', {'verified_completion_to_next_start_seconds': gaps,
                                                      'events': events, 'completions': completions})
        return events

    def save(self, **evidence):
        for value in evidence.values():
            if isinstance(value, dict): value.pop('token', None)
        atomic(self.directory / 'evidence.json', evidence)

    def test_pause_second_restart_resume(self):
        at_second, paused = self.control_at_second('PAUSE')
        self.assertEqual(paused['state']['status'], 'PAUSED')
        self.inspect_results(paused, 2)
        self.stop_server()
        self.start_server()
        restored = self.status()
        self.assertEqual(restored['state'], paused['state'])
        self.assertEqual(restored['session'], paused['session'])
        self.action('RESUME')
        done = self.wait(lambda s: not s['helper_active'])
        self.assertEqual(done['state']['metrics']['DONE'], 5)
        self.assertEqual(done['state']['metrics']['STARTED'], 5)
        self.assertEqual(done['state']['status'], 'IDLE')
        self.assertEqual(done['session']['goal_id'], paused['session']['goal_id'])
        events = self.inspect_results(done, 5)
        self.save(at_second=at_second, paused=paused, restored=restored, done=done,
                  events=events, max_active=1, duplicates=0, lost_results=0)

    def test_stop_second_idle_preserves_queue(self):
        at_second, stopped = self.control_at_second('STOP_AFTER_CURRENT')
        self.assertEqual(stopped['state']['status'], 'IDLE')
        events = self.inspect_results(stopped, 2)
        self.save(at_second=at_second, stopped=stopped, events=events, max_active=1,
                  duplicates=0, lost_results=0, preserved_pending=3)

    def test_restart_during_cooldown_preserves_terminal_results(self):
        self.start_server(); self.action('START')
        saved = self.wait(lambda s: s['state'].get('metrics', {}).get('DONE') == 2
                          and s['state']['status'] == 'COOLDOWN')
        events_before = self.inspect_results(saved, 2)
        self.stop_server()  # Exact owned test runtime; no task is active.
        self.start_server()
        restored = self.status()
        self.assertEqual(restored['state']['metrics']['DONE'], 2)
        self.assertEqual(restored['state']['status'], 'COOLDOWN')
        self.action('RESUME')
        done = self.wait(lambda s: not s['helper_active'])
        self.assertEqual(done['state']['metrics']['DONE'], 5)
        self.assertEqual(done['state']['metrics']['STARTED'], 5)
        events = self.inspect_results(done, 5)
        self.assertEqual(events[:2], events_before)
        self.save(saved=saved, restored=restored, done=done, events=events,
                  duplicates=0, lost_results=0, max_active=1)

    def test_import_acceptance_from_unrelated_cwd_without_running_it(self):
        probe = ('import runpy; runpy.run_path(' + repr(str(APP / 'cannon/acceptance.py'))
                 + ', run_name="__import_probe__"); print("IMPORT_OK_NO_EXECUTION")')
        completed = subprocess.run([sys.executable, '-B', '-c', probe], cwd=self.directory,
                                   capture_output=True, text=True, timeout=10,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('IMPORT_OK_NO_EXECUTION', completed.stdout)
        self.save(import_only=True, returncode=completed.returncode, stdout=completed.stdout)

    def test_transient_reader_lock_retries_atomic_replace(self):
        path = self.directory / 'state.json'
        atomic(path, {'state': 'old'})
        original = storage.os.replace
        attempts = []
        def replace(source, target):
            attempts.append(1)
            if len(attempts) <= 2:
                self.assertEqual(read(path), {'state': 'old'})
                error = PermissionError('bounded sharing conflict'); error.winerror = 32
                raise error
            return original(source, target)
        with patch.object(storage.os, 'replace', side_effect=replace):
            atomic(path, {'state': 'new'})
        self.assertEqual(len(attempts), 3)
        self.assertEqual(read(path), {'state': 'new'})

    def test_persistent_reader_lock_fails_without_erasing_state(self):
        path = self.directory / 'state.json'
        atomic(path, {'state': 'old'})
        error = PermissionError('persistent sharing conflict'); error.winerror = 32
        with patch.object(storage.os, 'replace', side_effect=error) as replace, patch.object(storage.time, 'sleep'):
            with self.assertRaises(PermissionError): atomic(path, {'state': 'new'})
        self.assertEqual(replace.call_count, 8)
        self.assertEqual(read(path), {'state': 'old'})


if __name__ == '__main__':
    unittest.main()
