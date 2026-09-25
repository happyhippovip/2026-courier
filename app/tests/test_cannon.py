import contextlib
import io
import json
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from cannon_support import APP, ROOT, SNAPSHOT, IsolatedCore, load_core, snapshot, step
from cannon.adapters import FakeAdapter, LiveMuseAdapter
from cannon.controller import Controller
from cannon.importer import Importer
from cannon.storage import InstanceLock, atomic, digest, file_hash, owned, read


class CannonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        snapshot()
        cls.previous_cwd = Path.cwd()
        os.chdir(SNAPSHOT)
        cls.api, cls.verifier = load_core()
        cls.evidence = read(ROOT / 'data/cannon-tests/observations.json', {})

    @classmethod
    def tearDownClass(cls):
        atomic(ROOT / 'data/cannon-tests/observations.json', cls.evidence)
        os.chdir(cls.previous_cwd)

    def setUp(self):
        import uuid
        self.root = ROOT / 'data/cannon-tests/runs' / (self._testMethodName + '-' + uuid.uuid4().hex[:8])
        self.root.mkdir(parents=True)
        self.workspace = self.root / 'workspace'; self.workspace.mkdir()
        os.chdir(self.workspace)
        self.core = IsolatedCore(self.api, self.verifier, self.root / 'core')
        self.adapter = FakeAdapter(SNAPSHOT / 'scripts/integration_contract.py', self.workspace)
        self.addCleanup(self.adapter.close); self.addCleanup(self.core.close)
        self.verifier.VERDICT_CACHE.clear()
        self.capture = io.StringIO()
        self.output = contextlib.redirect_stdout(self.capture); self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)
        self.addCleanup(lambda: os.chdir(SNAPSHOT))

    def controller(self, **kwargs):
        return Controller(self.root / 'controller', self.core, self.adapter, resources=lambda: 'GREEN', **kwargs)

    def remember(self, state):
        atomic(self.root / 'observations.json', {'core_source_manifest_sha256': file_hash(ROOT / 'data/cannon-tests/core-source-manifest.json'),
                                               'controller': state, 'claims': self.core.claimed,
                                               'verifications': self.core.verifications})
        self.evidence[self._testMethodName] = {'path': str(self.root), 'metrics': state.get('metrics', {}), 'state': state.get('status')}

    def run_count(self, count):
        self.core.add([step('task-' + str(i)) for i in range(count)])
        controller = self.controller(); state = controller.run()
        self.assertEqual(state['metrics']['DONE'], count)
        self.assertEqual(state['metrics']['STARTED'], count)
        self.assertEqual(len(self.core.verifications), count)
        self.assertEqual(state['status'], 'IDLE')
        self.assertEqual(len(list(self.workspace.rglob('*.txt'))), count)
        self.assertEqual(len(set(x['execution_ref'] for x in self.core.claimed)), count)
        for folder in (self.root / 'controller/executions').iterdir():
            event = read(folder / 'event.json')
            observed = read(folder / 'process.json')
            self.assertEqual(observed['pid'], event['pid'])
            # Windows PID-reuse hardening only: posix launch records no
            # creation filetime, pid equality already binds the handle.
            if sys.platform == 'win32':
                self.assertTrue(observed['creation_filetime'])
        self.remember(state)

    def test_01_single_five(self): self.run_count(5)
    def test_02_single_ten(self): self.run_count(10)

    def test_03_restart_between_tasks(self):
        self.core.add([step('restart-' + str(i)) for i in range(5)])
        before = self.controller().run(max_starts=3)
        self.assertEqual(before['metrics']['DONE'], 3)
        after = self.controller().run()
        self.assertEqual(after['metrics']['DONE'], 5)
        self.assertEqual([c['task_id'] for c in self.core.claimed], ['restart-' + str(i) for i in range(5)])
        self.remember(after)

    def test_04_failure_continues_independent(self):
        self.core.add([step('bad', fake_mode='FAILURE'), step('good')])
        state = self.controller().run()
        self.assertEqual(state['metrics']['FAILED'], 1)
        self.assertEqual(state['metrics']['DONE'], 1)
        self.assertEqual(self.core.task('bad')['next_action'], 'RETRY')
        self.remember(state)

    def test_05_timeout_and_cancel(self):
        self.core.add([step('timeout', fake_mode='TIMEOUT'), step('cancel', fake_mode='CANCEL'), step('after')])
        state = self.controller(timeout=.5).run()
        self.assertEqual(state['metrics']['FAILED'], 2)
        self.assertEqual(state['metrics']['DONE'], 1)
        self.assertEqual(len(self.adapter.handles), 0)
        self.remember(state)

    def test_06_malformed_locks_lane(self):
        self.core.add([step('malformed', fake_mode='MALFORMED_RESULT'), step('not-started')])
        state = self.controller().run()
        self.assertEqual(state['metrics']['STARTED'], 1)
        self.assertEqual(state['metrics']['DONE'], 0)
        self.assertEqual(state['status'], 'BLOCKED')
        again = self.controller().run()
        self.assertEqual(again['metrics']['STARTED'], 1)
        self.assertEqual(self.core.task('malformed')['status'], 'DISPATCHED')
        self.remember(state)

    def test_07_dependency_and_two_lanes(self):
        self.core.add([step('A', fake_delay=.3), step('B', fake_delay=.3), step('C', depends_on=['A', 'B'])])
        state = self.controller(mode='TURBO TEST').run()
        self.assertEqual(state['metrics']['DONE'], 3)
        events = {e['task_id']: e for p in (self.root / 'controller/executions').glob('*/event.json') for e in [read(p)]}
        self.assertLess(max(events['A']['start'], events['B']['start']), min(events['A']['end'], events['B']['end']))
        self.assertGreaterEqual(events['C']['start'], max(events['A']['end'], events['B']['end']))
        self.assertEqual({v['task_id'] for v in self.core.verifications}, {'A', 'B', 'C'})
        self.remember(state)

    def test_08_scope_lock(self):
        self.core.add([step('writer-a', exclusive_resources=['same'], fake_delay=.2), step('writer-b', exclusive_resources=['same'], fake_delay=.2)])
        state = self.controller(mode='TURBO TEST').run()
        events = sorted([read(p) for p in (self.root / 'controller/executions').glob('*/event.json')], key=lambda e: e['start'])
        self.assertEqual(state['metrics']['DONE'], 2)
        self.assertGreaterEqual(events[1]['start'], events[0]['end'])
        self.remember(state)

    def test_09_resource_no_new_start(self):
        self.core.add([step('resource')])
        for level in ['YELLOW', 'RED']:
            controller = Controller(self.root / 'controller', self.core, self.adapter, resources=lambda: level)
            state = controller.run()
            self.assertEqual(state['metrics']['STARTED'], 0)
            self.assertEqual(state['status'], 'CANNON_PAUSED_RESOURCE')
        state = self.controller().run()
        self.assertEqual(state['metrics']['DONE'], 1)
        self.remember(state)

    def test_10_single_instance_and_empty_idle(self):
        with InstanceLock(self.root / 'controller'):
            with self.assertRaises(RuntimeError): self.controller().run()
        before = len(self.core.requests)
        state = self.controller().run()
        self.assertEqual(state['status'], 'IDLE')
        self.assertEqual(len(self.core.requests), before)
        self.remember(state)

    def test_11_restart_mid_execution_conservative(self):
        self.core.add([step('interrupted', fake_delay=5)])
        task = self.core.claim(self.core.worker_ids[0])
        folder = self.root / 'controller/executions' / digest(task['execution_ref'])
        controller = self.controller()
        lane = {'phase': 'INTENT', 'task': task, 'folder': str(folder)}
        controller.state['lanes'][self.core.worker_ids[0]] = lane
        def persist(identity):
            lane.update(process=identity, phase='RUNNING'); controller.state['metrics']['STARTED'] += 1; controller.save()
        self.adapter.execute(task, folder, persist)
        self.adapter.close()  # exact owned fake handle, no live process is touched
        state = self.controller().run()
        self.assertEqual(state['status'], 'BLOCKED')
        self.assertEqual(state['metrics']['STARTED'], 1)
        self.assertEqual(state['metrics']['DONE'], 0)
        self.assertEqual(len(self.core.claimed), 1)
        self.remember(state)

    def test_12_verification_pending_and_replay(self):
        self.core.auto_verify = False
        self.core.add([step('waiting'), step('dependent', depends_on=['waiting'])])
        state = self.controller().run()
        self.assertEqual(state['status'], 'WAITING')
        self.assertEqual(state['metrics']['DONE'], 0)
        result = self.core.task('waiting')['result']
        wire = {k: v for k, v in result.items() if k not in {'received_runtime_identity', 'result_fingerprint'}}
        self.core.receive(wire)
        self.assertEqual(len(self.core.claimed), 1)
        changed = dict(wire, result_id='contradictory')
        with self.assertRaisesRegex(ValueError, 'exact result'): self.core.receive(changed)
        self.core.auto_verify = True; self.core.after_result()
        state = self.controller().run()
        self.assertEqual(state['metrics']['DONE'], 2)
        self.remember(state)

    def test_13_identity_and_late_result(self):
        self.run_count(1)
        folder = next((self.root / 'controller/executions').iterdir())
        request = read(folder / 'request.json'); raw = read(folder / 'result.json')
        for key in ['goal_id', 'task_id', 'attempt_id', 'dispatch_id', 'execution_ref', 'worker_id']:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.adapter.contract.validate_durable_result(request['task'], {**raw, key: 'wrong'})
        with self.assertRaises(ValueError): self.adapter.contract.validate_durable_result(request['task'], {**raw, 'artifacts': []})
        newer = {**request['task'], 'attempt_id': 'new-attempt'}
        with self.assertRaises(ValueError): self.adapter.contract.validate_durable_result(newer, raw)

    def test_14_import_resume_dedup_and_authorization(self):
        importer = Importer(self.root / 'import')
        source = self.root / 'batch.jsonl'
        records = [{'id': 'one', 'kind': 'TASK', 'task': step('import-one')}, {'id': 'note', 'text': 'do something'}, {'id': 'two', 'kind': 'TASK', 'task': step('import-two')}]
        source.write_text('\n'.join(json.dumps(r) for r in records) + '\n', encoding='utf-8')
        first = importer.ingest(source, 'import', 1)
        self.assertEqual(first['line'], 1)
        second = Importer(self.root / 'import').ingest(source, 'import')
        self.assertEqual(second['line'], 3); self.assertTrue(second['eof'])
        self.assertEqual(importer.ingest(source, 'import'), second)
        self.assertFalse(read(self.root / 'import/receipts' / (digest('one') + '.json'))['execution_authorized'])
        with self.assertRaises(ValueError): importer.submit_authorized([('note', digest(records[1]))], self.core, 'notes')
        receipt = importer.submit_authorized([('one', digest(records[0])), ('two', digest(records[2]))], self.core, 'approval')
        self.assertEqual(importer.submit_authorized([('one', digest(records[0])), ('two', digest(records[2]))], self.core, 'approval'), receipt)
        self.core.goal_ids.append(receipt['goal_id'])
        state = self.controller().run(); self.assertEqual(state['metrics']['DONE'], 2)
        duplicate = self.root / 'duplicates.jsonl'
        duplicate.write_text('\n'.join(json.dumps(r) for r in [records[0], {**records[0], 'id': 'different'}, {**records[0], 'text': 'conflict'}]) + '\n')
        result = importer.ingest(duplicate)
        self.assertEqual((result['imported'], result['reused'], result['conflicts']), (1, 1, 1))
        self.remember(state)

    def test_15_import_bounds_bad_record_and_source_change(self):
        importer = Importer(self.root / 'import')
        source = self.root / 'bad.jsonl'; source.write_text('not json\n{"id":"good","text":"note"}\n')
        result = importer.ingest(source, 'fixed')
        self.assertEqual((result['invalid'], result['imported']), (1, 1))
        source.write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'CONTENT_CONFLICT'): importer.ingest(source, 'fixed')
        source.write_text('x' * 65537)
        with self.assertRaisesRegex(ValueError, 'TOO_LARGE'): importer.ingest(source, 'long')

    def test_16_human_gate_and_provider_wait(self):
        self.core.add([step('gated', requires_human_approval=True), step('safe')])
        state = self.controller().run(); self.assertEqual(state['metrics']['DONE'], 1)
        self.assertEqual([c['task_id'] for c in self.core.claimed], ['safe'])
        self.core.request('POST', '/workers/register', {'worker_id': self.core.worker_ids[0], 'provider_available': False})
        state = self.controller().run(); self.assertEqual(state['metrics']['STARTED'], 1)
        self.assertEqual(state['status'], 'WAITING')
        self.remember(state)

    def test_17_pause_stop_and_resume(self):
        self.core.add([step('paused')])
        controller = self.controller(); controller.control('PAUSE')
        self.assertEqual(controller.run()['metrics']['STARTED'], 0)
        controller = self.controller(); controller.control('STOP_AFTER_CURRENT')
        self.assertEqual(controller.run()['metrics']['STARTED'], 0)
        controller = self.controller(); controller.control('RESUME')
        self.assertEqual(controller.run()['metrics']['DONE'], 1)

    def test_27_pause_after_second_task(self):
        self.assert_control_after_second('PAUSE', 'PAUSED')

    def test_28_stop_after_second_is_idle(self):
        self.assert_control_after_second('STOP_AFTER_CURRENT', 'IDLE')

    def assert_control_after_second(self, action, expected):
        self.core.add([step('control-' + str(i), fake_delay=.1) for i in range(5)])
        controller = self.controller()
        original = self.adapter.execute
        def launch(task, folder, persist):
            child = original(task, folder, persist)
            if len(self.core.claimed) == 2:
                controller.control(action)
            return child
        with patch.object(self.adapter, 'execute', side_effect=launch):
            state = controller.run()
        self.assertEqual(state['metrics']['DONE'], 2)
        self.assertEqual(state['metrics']['STARTED'], 2)
        self.assertEqual(state['counts']['QUEUED'], 3)
        self.assertEqual(state['status'], expected)
        self.remember(state)

    def test_18_live_unproven_and_no_auto_upshift(self):
        live = LiveMuseAdapter()
        self.assertFalse(live.health()['available'])
        with self.assertRaises(RuntimeError): live.execute({})
        with self.assertRaises(ValueError): self.controller(mode='FAST')
        with self.assertRaises(ValueError): Controller(self.root / 'other', self.core, live, mode='TURBO TEST')

    def test_19_pressure_during_execution_and_stop(self):
        self.core.add([step('finishes', fake_delay=.15), step('not-yet')])
        levels = iter(['GREEN', 'RED'])
        controller = Controller(self.root / 'controller', self.core, self.adapter, resources=lambda: next(levels, 'RED'))
        state = controller.run()
        self.assertEqual(state['metrics']['DONE'], 1)
        self.assertEqual(state['metrics']['STARTED'], 1)
        self.assertEqual(state['status'], 'CANNON_PAUSED_RESOURCE')
        self.assertFalse(self.adapter.handles)
        self.remember(state)

    def test_20_delayed_result_and_cancel_owned_handle(self):
        self.core.add([step('delay', fake_mode='DELAYED_RESULT', fake_delay=.3)])
        controller = self.controller()
        original = self.adapter.execute
        def launch(*args):
            child = original(*args)
            self.adapter.cancel(args[0]['execution_ref'])
            return child
        with patch.object(self.adapter, 'execute', side_effect=launch):
            state = controller.run()
        self.assertEqual(state['metrics']['FAILED'], 1)
        self.assertEqual(state['metrics']['DONE'], 0)
        self.assertEqual(self.core.task('delay')['result']['stderr'], 'Fake worker: cancelled')
        self.remember(state)

    def test_21_stale_controller_object_reloads_under_lock(self):
        self.core.add([step('only-once')])
        stale = self.controller()
        self.controller().run()
        self.assertEqual(stale.run()['metrics']['STARTED'], 1)
        self.assertEqual(len(self.core.claimed), 1)

    def test_22_real_controller_process_restart(self):
        import subprocess
        env = dict(os.environ, CANNON_DEMO_DIR=str(self.root / 'physical-restart'))
        command = [sys.executable, '-B', str(APP / 'server.py'), '--cannon', 'demo', '--count', '5']
        # Two genuinely distinct controller processes reload the same canonical
        # fixture state. No task/result or verification is manually inserted.
        first = subprocess.run(command + ['--max-starts', '3'], env=env, capture_output=True, timeout=30,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        first_state = read(self.root / 'physical-restart/controller/controller.json')
        self.assertEqual(first_state['metrics']['DONE'], 3, first.stderr.decode(errors='replace'))
        second = subprocess.run(command, env=env, capture_output=True, timeout=30,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(second.returncode, 0, second.stderr.decode(errors='replace'))
        state = read(self.root / 'physical-restart/controller/controller.json')
        self.assertEqual(state['metrics']['DONE'], 5)
        self.assertEqual(state['metrics']['STARTED'], 5)
        events = [read(p) for p in (self.root / 'physical-restart/controller/executions').glob('*/event.json')]
        self.assertEqual(len(events), 5)
        self.assertEqual(len({e['execution_ref'] for e in events}), 5)
        self.remember(state)

    @unittest.skipUnless(os.name == 'nt', 'Windows job semantics')
    def test_23_owner_crash_does_not_orphan_worker(self):
        import ctypes
        from ctypes import wintypes as W
        import subprocess
        self.core.add([step('owned-crash', fake_delay=10)])
        task = self.core.claim(self.core.worker_ids[0])
        folder = self.root / 'crash-execution'; marker = self.root / 'owned-process.json'
        atomic(self.root / 'crash-request.json', {'contract': str(SNAPSHOT / 'scripts/integration_contract.py'),
               'workspace': str(self.workspace), 'task': task, 'folder': str(folder), 'marker': str(marker)})
        owner = subprocess.Popen([getattr(sys, '_base_executable', sys.executable), '-B', str(APP / 'tests/cannon_crash_owner.py'), str(self.root / 'crash-request.json')],
                                 stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        handle = None
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]; api.OpenProcess.restype = W.HANDLE
        api.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
        api.CloseHandle.argtypes = [W.HANDLE]
        try:
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline and owner.poll() is None:
                threading.Event().wait(.025)
            identity = read(marker)
            self.assertIsNotNone(identity)
            handle = api.OpenProcess(0x100000, False, identity['pid'])
            self.assertTrue(handle)
            owner.kill(); owner.wait(timeout=5)
            self.assertEqual(api.WaitForSingleObject(handle, 5000), 0, 'Owned worker survived owner job closure')
            self.assertFalse((folder / 'result.json').exists())
            self.assertEqual(self.core.task(task['task_id'])['status'], 'DISPATCHED')
            atomic(self.root / 'job-crash-proof.json', {'owned_pid': identity['pid'], 'owner_pid': owner.pid, 'worker_exit_observed': True, 'result_manufactured': False})
        finally:
            if owner.poll() is None: owner.kill(); owner.wait(timeout=5)
            if owner.stdin: owner.stdin.close()
            if handle: api.CloseHandle(handle)

    @unittest.skipUnless(os.name == 'nt', 'Windows extended paths')
    def test_24_extended_windows_paths_stay_scope_bound(self):
        destination = '\\\\?\\' + str(self.root / 'extended.json')
        atomic(destination, {'bounded': True})
        self.assertTrue(read(destination)['bounded'])
        with self.assertRaises(ValueError): owned('\\\\?\\C:\\Users\\lol\\AppData\\Local\\MuseTerminal\\never-change.json')

    def test_25_changed_artifact_never_unlocks_dependency(self):
        self.core.add([step('artifact-a'), step('artifact-b', depends_on=['artifact-a'])])
        original = self.adapter.result
        def changed(task, folder):
            result = original(task, folder)
            (self.workspace / task['artifacts'][0]).write_text('Changed after worker fingerprint', encoding='utf-8')
            return result
        with patch.object(self.adapter, 'result', side_effect=changed):
            state = self.controller().run()
        self.assertEqual(state['metrics']['DONE'], 0)
        failed = self.core.task('artifact-a')
        self.assertEqual(failed['verification']['verdict'], 'FAIL')
        self.assertEqual(failed['status'], 'QUEUED')  # existing bounded core retry
        self.assertEqual([c['task_id'] for c in self.core.claimed], ['artifact-a'])
        self.remember(state)

    def test_26_lost_ack_recovers_exact_persisted_result(self):
        self.core.add([step('lost-ack'), step('next', depends_on=['lost-ack'])])
        original = self.core.receive
        original_read = self.core.task
        disconnected = [False]
        def lose_ack(result):
            original(result)
            disconnected[0] = True
            raise ConnectionError('Injected loss after canonical receipt')
        def disconnected_read(task_id):
            if disconnected[0]: raise ConnectionError('Connection unavailable until restart')
            return original_read(task_id)
        with patch.object(self.core, 'receive', side_effect=lose_ack), patch.object(self.core, 'task', side_effect=disconnected_read):
            before = self.controller().run()
        # UNKNOWN lane phases report RECONCILE_REQUIRED (reconcile pending),
        # never success: the persisted outbox alone may resolve it on retry.
        self.assertEqual(before['status'], 'RECONCILE_REQUIRED')
        state = self.controller().run()
        self.assertEqual(state['metrics']['DONE'], 2)
        self.assertEqual(state['metrics']['STARTED'], 2)
        self.assertEqual([c['task_id'] for c in self.core.claimed], ['lost-ack', 'next'])
        self.remember(state)


if __name__ == '__main__':
    unittest.main(verbosity=2)
