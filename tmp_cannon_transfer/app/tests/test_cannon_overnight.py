"""Fail-closed Dauerlauf checks on the pinned, isolated local fixture only."""
import unittest
from unittest.mock import patch
from test_cannon import CannonTests
from cannon_support import step
from cannon.storage import read


class OvernightTests(unittest.TestCase):
    setUpClass = classmethod(CannonTests.setUpClass.__func__)
    tearDownClass = classmethod(CannonTests.tearDownClass.__func__)
    setUp = CannonTests.setUp
    controller = CannonTests.controller
    remember = CannonTests.remember

    def pending_status(self):
        # Unclaimed steps live in the canonical goal plan, not /tasks/search yet.
        return next(t['status'] for t in self.core.tasks() if t['task_id'] == 'pending')

    def test_unknown_stops_whole_chain_and_restart_cannot_resubmit(self):
        self.core.add([step('malformed', fake_mode='MALFORMED_RESULT'), step('pending')])
        state = self.controller().run()
        self.assertEqual(state['status'], 'RECONCILE_REQUIRED')
        self.assertEqual(state['metrics']['STARTED'], 1)
        self.assertEqual(state['metrics']['DONE'], 0)
        self.assertNotIn('last_completion', state)
        again = self.controller().run()
        self.assertEqual(again['metrics']['STARTED'], 1)
        self.assertEqual(len(self.core.claimed), 1)
        self.assertEqual(self.pending_status(), 'QUEUED')
        self.remember(again)

    def test_exit_success_without_verification_is_not_completion(self):
        self.core.add([step('unverified'), step('pending')])
        with patch.object(self.core, 'after_result'):
            state = self.controller().run()
        self.assertEqual(state['status'], 'RECONCILE_REQUIRED')
        self.assertEqual(state['metrics']['STARTED'], 1)
        self.assertEqual(state['metrics']['DONE'], 0)
        self.assertNotIn('last_completion', state)
        self.assertEqual(list((self.root / 'controller/executions').glob('*/completion.json')), [])
        self.remember(state)

    def test_failed_result_requires_intervention_not_next_task(self):
        self.core.add([step('failed', fake_mode='FAILURE'), step('pending')])
        state = self.controller().run()
        self.assertEqual(state['status'], 'BLOCKED')
        self.assertEqual(state['metrics']['FAILED'], 1)
        self.assertEqual(state['metrics']['STARTED'], 1)
        self.assertEqual(self.pending_status(), 'QUEUED')
        self.assertNotIn('last_completion', state)
        self.remember(state)

    def test_unavailable_preserves_queue_without_submission(self):
        self.core.add([step('pending')])
        with patch.object(self.adapter, 'health', return_value={'available': False}):
            state = self.controller().run()
        self.assertEqual(state['status'], 'BLOCKED_UNAVAILABLE')
        self.assertEqual(state['metrics']['STARTED'], 0)
        self.assertEqual(self.pending_status(), 'QUEUED')
        restored = self.controller().run()
        self.assertEqual(restored['metrics']['DONE'], 1)
        self.assertEqual(len(self.core.claimed), 1)
        self.remember(restored)

    def test_slow_task_does_not_release_at_five_seconds(self):
        self.core.add([step('slow', fake_delay=5.3), step('next')])
        state = self.controller().run()
        events = sorted([read(p) for p in (self.root / 'controller/executions').glob('*/event.json')],
                        key=lambda e: e['start'])
        self.assertGreaterEqual(events[0]['end'] - events[0]['start'], 5)
        self.assertGreaterEqual(events[1]['start'] - events[0]['end'], 5)
        self.assertEqual(state['metrics']['DONE'], 2)
        self.remember(state)

    def test_normal_is_only_allowed_mode(self):
        for mode in ['TURBO TEST', 'FAST']:
            with self.assertRaises(ValueError): self.controller(mode=mode)


if __name__ == '__main__': unittest.main()
