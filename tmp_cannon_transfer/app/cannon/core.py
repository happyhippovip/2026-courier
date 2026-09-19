"""Thin canonical HTTP client; never routes, verifies, or writes Courier state."""
import json
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


class CourierClient:
    isolated = False

    def __init__(self, url, token, goal_ids):
        parsed = urlsplit(url)
        if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.username or parsed.query:
            raise ValueError('Only explicit loopback Courier endpoints are supported')
        self.url, self.token = url.rstrip('/'), token
        self.goal_ids = list(goal_ids)
        if len(self.goal_ids) > 100: raise ValueError('Bounded goal window required')

    def request(self, method, path, body=None):
        request = Request(self.url + path, method=method,
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=30) as response:
            payload = response.read(2_000_001)
            if len(payload) > 2_000_000: raise ValueError('Courier response exceeds bounded window')
            return json.loads(payload)

    def tasks(self):
        tasks = []
        for goal in self.goal_ids:
            body = self.request('GET', '/goals/' + quote(goal, safe=''))
            tasks.extend(body.get('goal', {}).get('workflow_plan', []))
            if len(tasks) > 100: raise ValueError('Core task window exceeded')
        return tasks

    def task(self, task_id):
        result = self.request('GET', '/tasks/search?task_id=' + quote(task_id, safe=''))
        exact = [t for t in result.get('tasks', []) if t.get('task_id') == task_id]
        if len(exact) != 1: raise ValueError('Canonical task identity is ambiguous')
        return exact[0]

    def claim(self, worker):
        response = self.request('POST', '/tasks/claim', {'worker_id': worker})
        task = response.get('task')
        if task and task.get('goal_id') not in self.goal_ids:
            raise ValueError('CLAIM_OUTSIDE_AUTHORIZED_WINDOW: requires scoped core claim')
        return task

    def receive(self, result):
        self.request('POST', '/tasks/result', result)
        stored = self.task(result['task_id']).get('result', {})
        if any(stored.get(key) != value for key, value in result.items()):
            raise ValueError('Courier ACK did not bind the exact result')

    def after_result(self):
        # Only an external independent verifier may advance canonical truth.
        pass
