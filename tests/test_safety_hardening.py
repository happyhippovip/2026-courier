import unittest
import json
import uuid
import sys
import os

# add parent dir to path to allow importing server/app.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from server.app import app, load_state, save_state

class TestCourierSafetyHardening(unittest.TestCase):
    def setUp(self):
        from server.app import ROLE_KEYS
        self.app = app.test_client()
        app.testing = True
        
        # Ensure a clean temp state file for testing
        self.test_state_file = 'server/state/test_state.json'
        os.environ['COURIER_STATE_FILE'] = self.test_state_file
        
        # Mock auth
        ROLE_KEYS['linux'] = 'dev-secret-key'
        ROLE_KEYS['windows'] = 'dev-secret-key'
        ROLE_KEYS['verifier'] = 'dev-secret-key'
        
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)
            
        self.auth_headers = {'Authorization': 'Bearer dev-secret-key'}

    def tearDown(self):
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)
            
    def test_reject_forged_success(self):
        # Setup initial state with a dispatched task
        task_id = 'test-task-1'
        state = {'schema_version': 2, 'tasks': {
            task_id: {
                'task_id': task_id,
                'status': 'DISPATCHED',
                'lease_id': 'valid-lease',
                'worker_id': 'test-worker'
            }
        }, 'workers': {}, 'goals': {}}
        save_state(state)
        
        # Try to post result with wrong lease_id
        res = self.app.post('/tasks/result', json={
            'task_id': task_id,
            'worker_id': 'test-worker',
            'lease_id': 'forged-lease',
            'result_id': 'r-1',
            'status': 'SUCCESS',
            'artifacts': []
        }, headers=self.auth_headers)
        
        self.assertEqual(res.status_code, 403)
        self.assertIn('Invalid or expired lease', json.loads(res.data)['error'])
        
    def test_human_required_cannot_be_cleared(self):
        task_id = 'test-task-2'
        state = {'schema_version': 2, 'tasks': {
            task_id: {
                'task_id': task_id,
                'status': 'HUMAN_REQUIRED',
                'lease_id': 'valid-lease',
                'worker_id': 'test-worker'
            }
        }, 'workers': {}, 'goals': {}}
        save_state(state)
        
        # Try to post result to a HUMAN_REQUIRED task
        res = self.app.post('/tasks/result', json={
            'task_id': task_id,
            'worker_id': 'test-worker',
            'lease_id': 'valid-lease',
            'result_id': 'r-2',
            'status': 'SUCCESS',
            'artifacts': []
        }, headers=self.auth_headers)
        
        self.assertEqual(res.status_code, 403)
        self.assertIn('requires human intervention', json.loads(res.data)['error'])

if __name__ == '__main__':
    unittest.main()
