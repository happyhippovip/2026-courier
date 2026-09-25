"""Local fixture integrity and 5/10 selection regressions; no providers."""
import io
import unittest
import uuid
from unittest.mock import Mock, patch

import cannon_support as support
from cannon import web
from cannon.storage import ROOT, atomic, digest, file_hash, read


class FixtureIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'data/cannon-tests/selection-tests' / uuid.uuid4().hex
        legacy = self.root / 'data/cannon-tests/core-snapshot/server/app.py'
        legacy.parent.mkdir(parents=True)
        legacy.write_text('# bounded fixture\n', encoding='utf-8')
        self.hashes = {'server\\app.py': file_hash(legacy)}
        self.manifest = self.root / 'manifest.json'
        atomic(self.manifest, self.hashes)
        self.fingerprint = digest(self.hashes)
        self.snapshot = self.root / 'snapshots' / self.fingerprint
        self.patcher = patch.multiple(support, ROOT=self.root, CORE_MANIFEST=self.manifest,
                                     CORE_HASHES=self.hashes, CORE_FIXTURE_ID=self.fingerprint,
                                     SNAPSHOT=self.snapshot)
        self.patcher.start(); self.addCleanup(self.patcher.stop)

    def test_pinned_fixture_reused_without_live_core_or_legacy_rewrite(self):
        self.assertEqual(support.snapshot(), self.hashes)
        # Subsequent runs rely on the validated versioned copy, not mutable source.
        legacy = self.root / 'data/cannon-tests/core-snapshot/server/app.py'
        legacy.write_text('# later source\n', encoding='utf-8')
        self.assertEqual(support.snapshot(), self.hashes)
        self.assertEqual((self.snapshot / 'server/app.py').read_text(), '# bounded fixture\n')
        self.assertEqual(legacy.read_text(), '# later source\n')

    def test_tampered_published_fixture_fails_closed(self):
        support.snapshot()
        (self.snapshot / 'server/app.py').write_text('# changed\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'CORE_SNAPSHOT_MUTATED'):
            support.snapshot()

    def test_changed_manifest_cannot_silently_rebind(self):
        support.snapshot()
        atomic(self.manifest, {'server\\app.py': '0' * 64})
        with self.assertRaisesRegex(ValueError, 'CORE_FIXTURE_MANIFEST_CHANGED'):
            support.snapshot()

    def test_unlisted_executable_code_rejected(self):
        support.snapshot()
        (self.snapshot / 'unexpected.py').write_text('# extra\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'CORE_SNAPSHOT_UNEXPECTED_CODE'):
            support.snapshot()


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'data/cannon-tests/selection-tests' / uuid.uuid4().hex
        self.launches = []
        def launch(command, cwd, env, **kwargs):
            child = Mock()
            child.poll.return_value = None
            child.stdin = io.BytesIO()
            self.launches.append((command, env, child))
            return child, Mock(), {'test_only': True}
        self.patches = [patch.multiple(web, DEMO=self.root, CHILD=None, JOB=None, LOADED_BUILD='fixed'),
                        patch.object(web, 'build_identity', return_value='fixed'),
                        patch.object(web, 'launch_gated', side_effect=launch),
                        patch.object(web.threading, 'Thread')]
        for p in self.patches:
            p.start(); self.addCleanup(p.stop)

    def finish(self, count):
        self.launches[-1][2].poll.return_value = 0
        atomic(web.active_demo() / 'session.json', {'count': count, 'mode': 'NORMAL', 'goal_id': 'fixture-' + str(count)})

    def test_five_then_ten_use_distinct_state_and_honor_count(self):
        web.action({'action': 'START', 'count': 5})
        five = web.active_demo()
        self.finish(5)
        web.action({'action': 'START', 'count': 10})
        ten = web.active_demo()
        self.assertNotEqual(five, ten)
        command, env, _ = self.launches[-1]
        self.assertEqual(command[command.index('--count') + 1], '10')
        self.assertEqual(env['CANNON_DEMO_DIR'], str(ten))
        self.assertEqual(read(five / 'session.json')['count'], 5)
        self.finish(10)
        web.action({'action': 'START', 'count': 5})
        self.assertEqual(web.active_demo(), five)

    def test_active_start_does_not_spawn_duplicate(self):
        web.action({'action': 'START', 'count': 5})
        result = web.action({'action': 'START', 'count': 10})
        self.assertTrue(result['reused'])
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(web.active_demo(), web.demo_path(5, 'NORMAL'))

    def test_resume_preserves_current_run_even_if_dropdown_changed(self):
        web.action({'action': 'START', 'count': 5})
        self.finish(5)
        atomic(web.active_demo() / 'controller/controller.json', {'status': 'PAUSED'})
        web.action({'action': 'RESUME', 'count': 10})
        command = self.launches[-1][0]
        self.assertEqual(command[command.index('--count') + 1], '5')

    def test_invalid_count_and_empty_resume_do_not_launch(self):
        for count in [0, 1000, True, '../other']:
            with self.assertRaises(ValueError):
                web.action({'action': 'START', 'count': count})
        with self.assertRaises(ValueError):
            web.action({'action': 'RESUME'})
        self.assertEqual(self.launches, [])

    def test_changed_source_blocks_start_resume_but_allows_safe_stop(self):
        web.action({'action': 'START', 'count': 5})
        with patch.object(web, 'build_identity', return_value='changed'):
            for action in ['START', 'RESUME']:
                with self.assertRaisesRegex(ValueError, 'Neue Version vorhanden'):
                    web.action({'action': action})
            web.action({'action': 'STOP_AFTER_CURRENT'})
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(read(web.active_demo() / 'controller/control.json')['action'], 'STOP_AFTER_CURRENT')

    def test_turbo_cannot_be_started(self):
        with self.assertRaises(ValueError):
            web.action({'action': 'START', 'mode': 'TURBO TEST', 'count': 5})
        self.assertEqual(self.launches, [])


if __name__ == '__main__':
    unittest.main()
