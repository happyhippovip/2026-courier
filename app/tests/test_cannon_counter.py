"""ERLEDIGT counter: dotted format, read-only display, DONE only when verified.

Local only; no providers. Controller is driven with minimal stubs so this
test needs no generated fixture.
"""
import json
import re
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from cannon.controller import Controller  # noqa: E402
from cannon.storage import ROOT  # noqa: E402

VECTORS = [
    (0, '0'),
    (1, '1'),
    (10, '10'),
    (752, '752'),
    (10000, '10.000'),
    (1000000000, '1.000.000.000'),
]


def extract_formatter(src):
    start = src.index('function fmtCount')
    i = src.index('{', start)
    depth = 0
    for j in range(i, len(src)):
        if src[j] == '{':
            depth += 1
        elif src[j] == '}':
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
    raise ValueError('unbalanced fmtCount')


class FormatterTests(unittest.TestCase):
    def test_shipped_js_formats_grouped_dots(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node unavailable')
        src = (APP / 'cannon.js').read_text(encoding='utf-8')
        fn = extract_formatter(src)
        script = fn + ';console.log(JSON.stringify(' + json.dumps([v[0] for v in VECTORS]) + '.map(fmtCount)));'
        out = subprocess.check_output([node, '-e', script], text=True, timeout=30)
        self.assertEqual(json.loads(out), [v[1] for v in VECTORS])


class CounterDisplayTests(unittest.TestCase):
    def test_counter_is_read_only_text(self):
        html = (APP / 'cannon.html').read_text(encoding='utf-8')
        match = re.search(r'<(p|span)\b([^>]*)id="erledigt"([^>]*)>', html)
        self.assertIsNotNone(match, 'missing #erledigt element')
        tag = match.group(0)
        self.assertNotIn('onclick', tag.lower())
        self.assertIn('ERLEDIGT: 0 / 1.000.000.000', html)
        js = (APP / 'cannon.js').read_text(encoding='utf-8')
        self.assertIn('const RUN_TARGET=1000000000;', js)
        self.assertIn('currentRunDone(m.DONE||0)', js)
        self.assertIn("' / '+fmtCount(RUN_TARGET)", js)
        self.assertIn("runBaseDone=lastDone;", js)
        self.assertIn("$('uebrig').textContent='ÜBRIG: '+fmtCount(data.session.remaining", js)


class UiLockTests(unittest.TestCase):
    def test_selectors_hidden_but_internally_fixed(self):
        html = (APP / 'cannon.html').read_text(encoding='utf-8')
        # Every remaining <select> lives inside a hidden label: no visible
        # dropdown, no visible arrow. Locked values: UNENDLICH and 1.
        for match in re.finditer(r'<select\b[^>]*id="(mode|count)"[^>]*>', html):
            start = html.rfind('<label', 0, match.start())
            self.assertNotEqual(start, -1)
            self.assertIn('hidden', html[start:match.start()].split('>')[0])
        mode = re.search(r'<select\b[^>]*id="mode"[^>]*>(.*?)</select>', html, re.S).group(1)
        count = re.search(r'<select\b[^>]*id="count"[^>]*>(.*?)</select>', html, re.S).group(1)
        self.assertEqual(re.findall(r'<option\b[^>]*>(.*?)</option>', mode), ['UNENDLICH'])
        self.assertEqual(re.findall(r'<option\b[^>]*>(.*?)</option>', count), ['1'])
        self.assertNotIn('>BEGRENZT<', html)
        self.assertIn('∞ DAUERLAUF', html)
        self.assertIn('id="uebrig"', html)
        self.assertIn('ÜBRIG: 1.000.000.000', html)
        for token in ['▶ DAUERLAUF', 'Pause', 'Fortsetzen', 'Nach aktueller Aufgabe stoppen']:
            self.assertIn(token, html)

    def test_css_keeps_hidden_controls_hidden(self):
        css = (APP / 'cannon.css').read_text(encoding='utf-8')
        self.assertRegex(css, r'label\[hidden\]\{[^}]*display\s*:\s*none')

    def test_static_copy_shows_run_counter(self):
        html = (APP / 'cannon.html').read_text(encoding='utf-8')
        self.assertIn('ERLEDIGT: 0 / 1.000.000.000', html)

    def test_no_limit_leftovers_in_run_info(self):
        js = (APP / 'cannon.js').read_text(encoding='utf-8')
        self.assertNotIn("'Übrig'", js)
        self.assertIn('Laufziel: 1.000.000.000 Aufgaben.', js)

    def test_js_still_uses_internal_locked_values(self):
        js = (APP / 'cannon.js').read_text(encoding='utf-8')
        self.assertIn("$('mode').value", js)
        self.assertIn("$('count').value", js)


class StubContract:
    def validate_durable_result(self, task, result):
        pass


class StubCore:
    def __init__(self):
        self.isolated = True
        self.worker_ids = ['worker-1']
        self.received = []
        self.record = None
        self._claimed = False
        self._calls = 0

    def tasks(self):
        self._calls += 1
        if self._calls == 1:
            return [{'status': 'QUEUED', 'next_retry_at': 0}]
        return []

    def claim(self, worker):
        if self._claimed:
            return None
        self._claimed = True
        self.record = {'goal_id': 'g', 'task_id': 't1', 'attempt_id': 'a1',
                       'dispatch_id': 'd1', 'execution_ref': 'exec-1',
                       'status': 'QUEUED', 'result': {'result_id': 'r1'},
                       'verification': {'verdict': 'PENDING', 'result_id': None}}
        return dict(self.record)

    def task(self, task_id):
        return dict(self.record)

    def receive(self, result):
        self.received.append(dict(result))

    def after_result(self):
        self.record['status'] = 'RECONCILED'
        self.record['verification'] = {'verdict': 'PASS',
                                       'result_id': self.received[-1]['result_id']}


class StubAdapter:
    def __init__(self, result_id='r1'):
        self.contract = StubContract()
        self._result_id = result_id
        self.closed = []

    def discover(self):
        return {'kind': 'STUB_PROCESS'}

    def health(self):
        return {'available': True}

    def execute(self, task, folder, persist):
        Path(folder).mkdir(parents=True, exist_ok=True)
        persist({'pid': 'stub'})
        child = Mock()
        child.wait = Mock(return_value=None)
        return child

    def result(self, task, folder):
        return {'result_id': self._result_id}

    def cancel(self, execution):
        pass

    def close_execution(self, ref):
        self.closed.append(ref)

    def close(self):
        pass


class DoneGatingTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'data/cannon-tests/counter' / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, True)

    def run_once(self, result_id):
        core = StubCore()
        controller = Controller(self.root, core, StubAdapter(result_id),
                                mode='NORMAL', resources=lambda: 'GREEN', timeout=5)
        return controller.run(max_starts=1)

    def test_done_only_after_persist_verify_reconcile(self):
        state = self.run_once('r1')
        self.assertEqual(state['metrics']['DONE'], 1)
        self.assertEqual(state['metrics']['STARTED'], 1)
        completion = state['last_completion']
        self.assertAlmostEqual(completion['next_task_not_before'] - completion['confirmed_at'],
                               5.0, delta=0.5)
        self.assertEqual(state['lanes']['worker-1']['phase'], 'IDLE')

    def test_mismatched_result_never_counts(self):
        state = self.run_once('WRONG')
        self.assertEqual(state['metrics']['DONE'], 0)
        self.assertEqual(state['lanes']['worker-1']['phase'], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
