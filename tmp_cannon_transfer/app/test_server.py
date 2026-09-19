import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import server


class LocalBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / 'data'
        self.project = self.root / 'courier'
        (self.project / 'server/state').mkdir(parents=True)
        self.statefile = self.project / 'server/state/central_state.json'
        self.statefile.write_text(json.dumps({'goals': {}, 'tasks': {}, 'workers': {}}))
        self.patches = [patch.object(server, 'PROJECT', self.project), patch.object(server, 'DATA', self.data),
                        patch.object(server, 'git', return_value=None)]
        for p in self.patches:
            p.start()
        self.http = server.LocalHTTPServer(('127.0.0.1', 0), server.Handler)
        self.port = self.http.server_port
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port)
        conn.request(method, path, json.dumps(body) if body is not None else None, headers or {})
        r = conn.getresponse()
        status, data = r.status, json.loads(r.read())
        conn.close()
        return status, data

    def authorized(self):
        return {'Origin': f'http://127.0.0.1:{self.port}', 'X-Symphony-Token': server.TOKEN}

    def test_read_has_no_courier_mutation_or_false_status(self):
        before = self.statefile.read_bytes()
        with patch.object(server, 'courier_health', return_value={'status':'UNAVAILABLE','url':'http://127.0.0.1:8081'}):
            code, data = self.request('GET', '/api/state')
        self.assertEqual(code, 200)
        self.assertEqual(data['intake']['status'], 'UNAVAILABLE')
        self.assertTrue(all(w['status'] == 'UNKNOWN' for w in data['providers']))
        self.assertEqual(before, self.statefile.read_bytes())

    def test_draft_persists_only_in_v2(self):
        before = self.statefile.read_bytes()
        code, _ = self.request('POST', '/api/draft', {'text': 'Nur ein Entwurf'}, self.authorized())
        self.assertEqual(code, 200)
        self.assertEqual(json.loads((self.data / 'draft.json').read_text())['kind'], 'UI_DRAFT_ONLY')
        self.assertEqual(before, self.statefile.read_bytes())

    def test_cross_origin_and_missing_token_rejected(self):
        self.assertEqual(self.request('POST', '/api/open', {'action':'muse'})[0], 403)
        h = self.authorized(); h['Origin'] = 'https://example.org'
        self.assertEqual(self.request('POST', '/api/draft', {'text':'x'}, h)[0], 403)
        self.assertFalse(self.data.exists())

    def test_host_rebinding_rejected(self):
        self.assertEqual(self.request('GET', '/api/state', headers={'Host':'evil.example'})[0], 403)

    def test_port_is_exclusive(self):
        with self.assertRaises(OSError):
            server.LocalHTTPServer(('127.0.0.1', self.port), server.Handler)

    def test_only_allowlisted_launch_target(self):
        with patch.object(server.os, 'startfile', create=True) as launch:
            code, _ = self.request('POST', '/api/open', {'action':'cmd.exe'}, self.authorized())
            self.assertEqual(code, 400)
            launch.assert_not_called()

    def test_muse_reuses_exact_launcher_without_edit(self):
        launcher = self.root / 'Muse.lnk'; launcher.write_bytes(b'unchanged')
        with patch.object(server, 'MUSE', launcher), patch.object(server.os, 'startfile', create=True) as launch:
            self.assertEqual(self.request('POST','/api/open',{'action':'muse'},self.authorized())[0],200)
            launch.assert_called_once_with(str(launcher))
            self.assertEqual(launcher.read_bytes(), b'unchanged')

    def test_invalid_draft_and_unwired_intake(self):
        self.assertEqual(self.request('POST','/api/draft',{'text':[]},self.authorized())[0],400)
        self.assertEqual(self.request('POST','/api/goals',{'text':'execute'},self.authorized())[0],404)

    def test_run_goal_fails_closed_when_courier_runtime_is_unavailable(self):
        with patch.object(server, 'courier_health', return_value={'status':'UNAVAILABLE','url':'http://127.0.0.1:8081'}), \
             patch.object(server, 'submit_canonical_goal', return_value=(None,'COURIER_RUNTIME_UNAVAILABLE')):
            code, data = self.request('POST','/api/run-goal',{'goal_text':'harmless'},self.authorized())
        self.assertEqual(code,503)
        self.assertEqual(data['error'],'COURIER_RUNTIME_UNAVAILABLE')
        self.assertEqual(self.statefile.read_bytes(), json.dumps({'goals': {}, 'tasks': {}, 'workers': {}}).encode())

    def test_run_goal_rejects_empty_input_without_submitting(self):
        with patch.object(server, 'submit_canonical_goal') as submit:
            self.assertEqual(self.request('POST','/api/run-goal',{'goal_text':'  '},self.authorized())[0],400)
            submit.assert_not_called()

    def test_runtime_reuses_a_healthy_courier_without_starting_another(self):
        ready = {'status': 'READY', 'url': 'http://127.0.0.1:8081'}
        with patch.object(server, 'courier_health', return_value=ready), \
             patch.object(server.subprocess, 'Popen') as launch:
            self.assertEqual(server.ensure_courier_runtime()['action'], 'REUSED')
            launch.assert_not_called()

    def test_runtime_starts_only_the_existing_courier_entrypoint(self):
        python = self.root / 'courier-pythonw.exe'; python.write_bytes(b'')
        entrypoint = self.project / 'server' / 'run_waitress.py'; entrypoint.write_text('# existing entrypoint')
        unavailable = {'status': 'UNAVAILABLE', 'url': 'http://127.0.0.1:8081'}
        ready = {'status': 'READY', 'url': 'http://127.0.0.1:8081'}
        with patch.object(server, 'COURIER_RUNTIME_PYTHON', python), \
             patch.object(server, 'COURIER_RUNTIME', entrypoint), \
             patch.object(server, 'courier_health', side_effect=[unavailable, unavailable, ready]), \
             patch.object(server.subprocess, 'Popen') as launch, \
             patch.object(server.time, 'sleep'):
            self.assertEqual(server.ensure_courier_runtime()['action'], 'STARTED')
            launch.assert_called_once()
            self.assertEqual(launch.call_args.args[0], [str(python), str(entrypoint)])

    def test_stale_future_and_unknown_heartbeats(self):
        row={'available':True,'provider_available':True,'capacity_available':True,'last_seen':50}
        self.assertEqual(server.worker_view('w',row,1000)['status'],'UNKNOWN')
        row['last_seen']=1001
        self.assertEqual(server.worker_view('w',row,1000)['status'],'UNKNOWN')
        row['last_seen']=999
        self.assertEqual(server.worker_view('w',row,1000)['status'],'AVAILABLE')
        row['current_task']='a'
        self.assertEqual(server.worker_view('w',row,1000)['status'],'BUSY')
        row.pop('current_task'); row.pop('provider_available')
        self.assertEqual(server.worker_view('w',row,1000)['status'],'UNKNOWN')

    def test_missing_state_stays_unknown(self):
        self.statefile.unlink()
        code, data=self.request('GET','/api/state')
        self.assertEqual(code,200)
        self.assertEqual(data['sources'][0]['status'],'UNAVAILABLE')
        self.assertEqual(data['tasks'],[])


if __name__ == '__main__':
    unittest.main(verbosity=2)
