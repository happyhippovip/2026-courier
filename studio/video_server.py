"""Static video HQ plus a fixed, read-only, credential-free status proxy."""
import json
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

SOURCE = 'http://127.0.0.1:8768/api/cannon/status'
ROOT = str(Path(__file__).resolve().parent)


def read_status():
    with urlopen(SOURCE, timeout=2) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError('oversize status')
    data = json.loads(raw)
    state = data.get('state')
    if not isinstance(state, dict) or not isinstance(state.get('status'), str):
        raise ValueError('missing state')
    # Never forward the control token, workspace paths, or arbitrary upstream fields.
    clean = {key: data.get(key) for key in ('kind', 'live_muse')}
    session = data.get('session') or {}
    clean['session'] = {key: session.get(key) for key in ('mode', 'count')}
    clean['state'] = {key: state.get(key) for key in ('status', 'counts', 'metrics', 'active_lanes')}
    last = state.get('last_result') or {}
    clean['state']['last_result'] = {key: last.get(key) for key in ('result_id', 'task', 'completed_at')}
    clean['state']['tasks'] = []
    for lane in (state.get('lanes') or {}).values():
        task = lane.get('task') if isinstance(lane, dict) else None
        if isinstance(task, dict):
            task = task.get('task_id') or task.get('id')
        if isinstance(task, str):
            clean['state']['tasks'].append(task[:400])
    if data.get('error'):
        clean['state']['status'] = 'ERROR'
    return {'available': True, 'source': SOURCE,
            'observed_at': datetime.now(timezone.utc).isoformat(), 'cannon': clean}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_GET(self):
        if self.path != '/video-status':
            return super().do_GET()
        try:
            payload, status = read_status(), 200
        except Exception:
            payload, status = {'available': False}, 503
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8000), Handler).serve_forever()
