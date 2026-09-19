"""Courier Symphony: loopback-only view. Never imports or mutates Courier."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parent.parent
PROJECT = Path.home() / '2026-workspace' / '2026-courier'
MUSE = Path.home() / 'Desktop' / 'Muse.lnk'
DATA = ROOT / 'data'
PORT = 8766
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()
GIT = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
COURIER_PYTHON = PROJECT / '.venv' / 'Scripts' / 'python.exe'
COURIER_RUNTIME_PYTHON = PROJECT / '.venv' / 'Scripts' / 'pythonw.exe'
COURIER_URL = 'http://127.0.0.1:8081'
COURIER_RUNTIME = PROJECT / 'server' / 'run_waitress.py'
UNKNOWN = 'UNKNOWN'
RUNTIME_LOCK = threading.Lock()
RUNTIME_START = {'action': 'NOT_ATTEMPTED', 'status': 'UNAVAILABLE', 'url': COURIER_URL}


def read_json(path):
    try:
        raw = path.read_bytes()
        if len(raw) > 20_000_000:
            raise ValueError('Source too large')
        obj = json.loads(raw.decode('utf-8-sig'))
        if not isinstance(obj, dict):
            raise ValueError('Expected object')
        return obj, {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
                     'modified': path.stat().st_mtime, 'status': 'READ'}
    except (OSError, ValueError):
        return {}, {'path': str(path), 'status': 'UNAVAILABLE'}


def compact(value, limit=280):
    if value is None or value == '' or value == [] or value == {}:
        return UNKNOWN
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)
    return value[:limit]


def git(*args):
    try:
        result = subprocess.run([str(GIT), '-C', str(PROJECT), *args],
                                capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=4,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def project_info():
    status = git('status', '--porcelain', '--untracked-files=no')
    tracking = git('rev-list', '--left-right', '--count', 'HEAD...@{upstream}')
    sync = UNKNOWN
    if tracking:
        counts = tracking.split()
        if len(counts) == 2 and all(x.isdigit() for x in counts):
            sync = f'{counts[0]} voraus / {counts[1]} zurück (lokaler Stand, kein Fetch)'
    return {'name': PROJECT.name, 'path': str(PROJECT), 'exists': PROJECT.is_dir(),
            'branch': git('branch', '--show-current') or UNKNOWN,
            'head': git('rev-parse', 'HEAD') or UNKNOWN,
            'worktree': UNKNOWN if status is None else ('Geändert' if status else 'Tracked-Dateien sauber'),
            'sync': sync}


def courier_health():
    """Read only the canonical runtime health endpoint; no guesses from files."""
    try:
        with urlopen(COURIER_URL + '/health', timeout=2) as response:
            data = json.load(response)
        if response.status == 200 and data.get('status') == 'healthy':
            return {'status': 'READY', 'url': COURIER_URL}
        return {'status': 'UNHEALTHY', 'url': COURIER_URL}
    except (URLError, OSError, ValueError, TimeoutError):
        return {'status': 'UNAVAILABLE', 'url': COURIER_URL}


def ensure_courier_runtime():
    """Reuse the canonical Courier runtime or start its existing entrypoint once.

    This deliberately does not implement a V2 queue, router, worker, or verifier.
    ``run_waitress.py`` is Courier's existing server/verifier entrypoint and
    owns all further runtime behavior.
    """
    current = courier_health()
    if current['status'] == 'READY':
        return {'action': 'REUSED', **current}
    if not COURIER_RUNTIME_PYTHON.is_file() or not COURIER_RUNTIME.is_file():
        return {'action': 'UNAVAILABLE', **current}
    with RUNTIME_LOCK:
        current = courier_health()
        if current['status'] == 'READY':
            return {'action': 'REUSED', **current}
        try:
            subprocess.Popen(
                [str(COURIER_RUNTIME_PYTHON), str(COURIER_RUNTIME)],
                cwd=str(PROJECT), stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=(getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                               | getattr(subprocess, 'DETACHED_PROCESS', 0)),
            )
        except OSError:
            return {'action': 'START_FAILED', **courier_health()}
        for _ in range(20):
            time.sleep(.25)
            current = courier_health()
            if current['status'] == 'READY':
                return {'action': 'STARTED', **current}
        return {'action': 'START_FAILED', **current}


def submit_canonical_goal(goal_text):
    """Submit through Courier's own authenticated endpoint without exposing its key.

    The V2 browser never receives a credential.  The isolated existing Courier
    environment reads its already-configured OS keyring and returns only the
    canonical response.  V2 does not create a plan, choose a worker, or write
    Courier state directly.
    """
    if not COURIER_PYTHON.is_file():
        return None, 'COURIER_CLIENT_UNAVAILABLE'
    if courier_health()['status'] != 'READY':
        return None, 'COURIER_RUNTIME_UNAVAILABLE'
    program = (
        'import json,keyring,sys,urllib.request,urllib.error; '
        'key=keyring.get_password("courier","api_key"); '
        'payload=json.dumps({"goal_text":sys.argv[1]}).encode("utf-8"); '
        'req=urllib.request.Request(sys.argv[2]+"/goals",data=payload,method="POST",'
        'headers={"Authorization":"Bearer "+(key or ""),"Content-Type":"application/json"}); '
        'resp=urllib.request.urlopen(req,timeout=15); print(resp.read().decode("utf-8"))'
    )
    try:
        completed = subprocess.run(
            [str(COURIER_PYTHON), '-c', program, goal_text, COURIER_URL],
            cwd=str(PROJECT), capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=25,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, 'COURIER_SUBMISSION_FAILED'
    if completed.returncode != 0:
        # Never return subprocess stderr: it may contain sensitive runtime detail.
        return None, 'COURIER_INTAKE_REJECTED'
    try:
        payload = json.loads(completed.stdout)
    except ValueError:
        return None, 'COURIER_INTAKE_INVALID_RESPONSE'
    goal_id = payload.get('goal_id')
    if not isinstance(goal_id, str) or not goal_id:
        return None, 'COURIER_INTAKE_INVALID_RESPONSE'
    return payload, None


def dict_rows(value):
    if isinstance(value, dict):
        return [(key, row) for key, row in value.items() if isinstance(row, dict)]
    return []


def worker_view(key, row, now):
    try:
        age = now - float(row.get('last_seen', 0))
    except (ValueError, TypeError):
        age = -1
    fresh = 0 <= age <= 120
    status = UNKNOWN
    if fresh:
        if row.get('available') is False or row.get('provider_available') is False or row.get('capacity_available') is False:
            status = 'UNAVAILABLE'
        elif row.get('current_task'):
            status = 'BUSY'
        elif all(row.get(field) is True for field in ('available', 'provider_available', 'capacity_available')):
            status = 'AVAILABLE'
    return {'name': compact(row.get('worker_id', key)), 'provider': compact(row.get('provider')),
            'platform': compact(row.get('platform')), 'status': status,
            'seen': row.get('last_seen') if isinstance(row.get('last_seen'), (float, int)) else None,
            'evidence': 'Heartbeat ≤ 120 s' if fresh else 'Kein aktueller Heartbeat',
            'task': compact(row.get('current_task'))}


def snapshot():
    now = time.time()
    state, source = read_json(PROJECT / 'server/state/central_state.json')
    ledger, ledger_source = read_json(PROJECT / 'agent_handoff_ledger.json')
    record = ledger.get('record') if isinstance(ledger.get('record'), dict) else {}
    tasks = []
    for key, row in dict_rows(state.get('tasks'))[-60:]:
        result = row.get('result') if isinstance(row.get('result'), dict) else {}
        verification = row.get('verification')
        tasks.append({'id': compact(row.get('task_id', key)), 'goal': compact(row.get('goal_id')),
                      'status': compact(row.get('status')), 'worker': compact(row.get('worker_id')),
                      'instruction': compact(row.get('instruction')),
                      'blocker': compact(row.get('blocker')), 'result_id': compact(result.get('result_id', row.get('result_id'))),
                      'verification': compact(verification, 500),
                      'hash': hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest(),
                      'artifacts': compact(row.get('artifact_refs', result.get('artifacts')), 700),
                      'timestamp': compact(row.get('completed_at', row.get('updated_at', result.get('timestamp'))))})
    goals = [{'id': compact(r.get('goal_id', k)), 'text': compact(r.get('goal_text'), 1200),
              'status': compact(r.get('status')), 'steps': [
                  {'instruction': compact(s.get('instruction')), 'status': compact(s.get('status'))}
                  for s in r.get('workflow_plan', []) if isinstance(s, dict)]}
             for k, r in dict_rows(state.get('goals'))[-20:]]
    ready = [t['id'] for t in tasks if t['status'] == 'QUEUED']
    blocked = [t for t in tasks if t['blocker'] != UNKNOWN or t['status'] == 'HUMAN_REQUIRED']
    sources = [source, ledger_source]
    files = []
    if PROJECT.is_dir():
        for f in sorted(PROJECT.iterdir(), key=lambda f: (f.is_file(), f.name.lower())):
            if f.name.startswith('.') or f.name in ('__pycache__',):
                continue
            files.append({'name': f.name, 'kind': 'Ordner' if f.is_dir() else 'Datei',
                          'size': f.stat().st_size if f.is_file() else None})
    projects = [{'name': PROJECT.name, 'path': str(PROJECT)}] if PROJECT.is_dir() else []
    repair = Path.home() / 'Documents' / 'ANTIGRAVITY REPAIR'
    if repair.is_dir():
        projects.append({'name': repair.name, 'path': str(repair)})
    workers = [worker_view(k, r, now) for k, r in dict_rows(state.get('workers'))]
    # A launcher is evidence of a local capability, not provider availability.
    providers = [{'name': n, 'status': UNKNOWN, 'detail': 'Keine aktuelle Verfügbarkeitsquelle'}
                 for n in ('Muse', 'Codex', 'Gemini', 'Windows Worker', 'Mac Worker', 'GitHub Worker', 'AWS Worker')]
    providers[0]['detail'] = 'V1-Starter vorhanden · Anmeldung nicht geprüft' if MUSE.is_file() else 'Starter fehlt'
    system = [
        ['Current goal', compact(record.get('GOAL'))],
        ['Active writer', compact(record.get('ACTIVE_WRITERS'))],
        ['Ready task', compact(ready) + ' · gespeichert, nicht neu bewertet' if ready else UNKNOWN],
        ['Ledger / Trust', 'UNKNOWN · keine neue Abnahme'],
        ['A → B', 'UNKNOWN · keine neue Abnahme'],
        ['Unattended', UNKNOWN], ['Cost routing', UNKNOWN],
        ['Last durable result', next((t['result_id'] for t in reversed(tasks) if t['result_id'] != UNKNOWN), UNKNOWN)],
        ['Human gate', compact([t['id'] for t in tasks if t['status'] == 'HUMAN_REQUIRED'])],
        ['Current blocker', compact(record.get('FIRST_CAUSAL_BLOCKER'))],
    ]
    prefs, _ = read_json(DATA / 'preferences.json')
    draft, _ = read_json(DATA / 'draft.json')
    return {'observed_at': now, 'project': project_info(), 'projects': projects,
            'sources': sources, 'tasks': tasks, 'goals': goals, 'workers': workers,
            'providers': providers, 'system': system, 'files': files,
            'preferences': {'display_name': compact(prefs.get('display_name', 'Dennis'), 60)},
            'draft': {'text': draft.get('text', '')}, 'muse_launcher': str(MUSE),
            'muse_exists': MUSE.is_file(), 'token': TOKEN,
            'intake': courier_health(), 'runtime_start': RUNTIME_START}


def save_local(name, value):
    DATA.mkdir(exist_ok=True)
    with LOCK:
        target = DATA / name
        temp = target.with_suffix('.tmp')
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, target)


class LocalHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, payload, kind='application/json; charset=utf-8'):
        data = json.dumps(payload, ensure_ascii=False).encode() if not isinstance(payload, bytes) else payload
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403, {'error': 'Local host only'})
        path = urlsplit(self.path).path
        if path == '/api/identity':
            return self.reply(200, {'app': 'Courier Symphony V2', 'root': str(ROOT)})
        if path == '/api/cannon/status':
            from cannon import web
            return self.reply(200, {**web.status(), 'token': TOKEN})
        if path == '/api/state':
            try:
                return self.reply(200, snapshot())
            except Exception:
                return self.reply(503, {'error': 'Quelldaten derzeit nicht lesbar. Erneut aktualisieren.'})
        if path == '/api/courier-health':
            return self.reply(200, courier_health())
        routes = {'/': ('app/index.html', 'text/html; charset=utf-8'),
                  '/cannon': ('app/cannon.html', 'text/html; charset=utf-8'),
                  '/cannon.js': ('app/cannon.js', 'text/javascript; charset=utf-8'),
                  '/cannon.css': ('app/cannon.css', 'text/css; charset=utf-8'),
                  '/ui.js': ('app/ui.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('app/style.css', 'text/css; charset=utf-8'),
                  '/icon.svg': ('assets/courier_symphony_icon.svg', 'image/svg+xml'),
                  '/favicon.ico': ('assets/courier_symphony_icon.ico', 'image/x-icon')}
        if path not in routes:
            return self.reply(404, {'error': 'Not found'})
        relative, mime = routes[path]
        try:
            self.reply(200, (ROOT / relative).read_bytes(), mime)
        except OSError:
            self.reply(404, {'error': 'Asset unavailable'})

    def do_POST(self):
        origin = f'http://127.0.0.1:{self.server.server_port}'
        if not self.valid_host() or self.headers.get('Origin') != origin or self.headers.get('X-Symphony-Token') != TOKEN:
            return self.reply(403, {'error': 'Local session required'})
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 24000:
                return self.reply(400, {'error': 'Invalid body size'})
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError()
        except (ValueError, TypeError):
            return self.reply(400, {'error': 'Invalid JSON'})
        path = urlsplit(self.path).path
        try:
            if path == '/api/cannon/action':
                from cannon import web
                try:
                    return self.reply(200, web.action(body))
                except (ValueError, RuntimeError, OSError) as exc:
                    return self.reply(409, {'error': str(exc)})
            elif path == '/api/draft':
                value = body.get('text')
                if not isinstance(value, str) or len(value) > 8000:
                    return self.reply(400, {'error': 'Ziel darf maximal 8000 Zeichen enthalten.'})
                save_local('draft.json', {'text': value, 'kind': 'UI_DRAFT_ONLY', 'updated_at': time.time()})
            elif path == '/api/preferences':
                value = body.get('display_name')
                if not isinstance(value, str) or not 1 <= len(value.strip()) <= 60:
                    return self.reply(400, {'error': 'Name muss 1–60 Zeichen enthalten.'})
                save_local('preferences.json', {'display_name': value.strip()})
            elif path == '/api/open':
                action = body.get('action')
                targets = {'muse': MUSE, 'project': PROJECT, 'v2': ROOT,
                           'repair': Path.home() / 'Documents/ANTIGRAVITY REPAIR'}
                if action not in targets or not targets[action].exists():
                    return self.reply(400, {'error': 'Ziel ist nicht verfügbar.'})
                os.startfile(str(targets[action]))
            elif path == '/api/run-goal':
                value = body.get('goal_text')
                if not isinstance(value, str) or not 1 <= len(value.strip()) <= 8000:
                    return self.reply(400, {'error': 'Ziel muss 1–8000 Zeichen enthalten.'})
                submitted, error = submit_canonical_goal(value.strip())
                if error:
                    status = 503 if error == 'COURIER_RUNTIME_UNAVAILABLE' else 502
                    return self.reply(status, {'error': error, 'health': courier_health()})
                return self.reply(201, {'goal': submitted, 'health': courier_health()})
            elif path == '/api/shutdown':
                self.reply(200, {'ok': True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            else:
                return self.reply(404, {'error': 'Not connected'})
            self.reply(200, {'ok': True})
        except OSError:
            self.reply(503, {'error': 'Lokale Aktion fehlgeschlagen.'})


def open_app(url):
    candidates = [Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe',
                  Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) / 'Microsoft/Edge/Application/msedge.exe']
    for exe in candidates:
        if exe.exists():
            subprocess.Popen([str(exe), '--app=' + url], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return
    import webbrowser
    webbrowser.open(url)


def main():
    global RUNTIME_START
    if len(sys.argv) > 1 and sys.argv[1] == '--cannon':
        from cannon.cli import main as cannon_main
        raise SystemExit(cannon_main(sys.argv[2:]))
    parser = argparse.ArgumentParser()
    parser.add_argument('--open', action='store_true')
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--cannon-only', action='store_true', help='Open isolated Cannon controls without starting shared Courier')
    args = parser.parse_args()
    url = f'http://127.0.0.1:{args.port}'
    try:
        server = LocalHTTPServer(('127.0.0.1', args.port), Handler)
    except OSError:
        # Reuse only our own running instance; never open an unknown port owner.
        try:
            with urlopen(url + '/api/identity', timeout=2) as response:
                identity = json.load(response)
            if identity != {'app': 'Courier Symphony V2', 'root': str(ROOT)}:
                raise ValueError('Port occupied')
            if args.open:
                open_app(url + ('/cannon' if args.cannon_only else ''))
            return
        except Exception:
            DATA.mkdir(exist_ok=True)
            (DATA / 'startup-error.txt').write_text('Port belegt. Keine fremde Instanz geöffnet.\n', encoding='utf-8')
            return
    if args.open:
        threading.Timer(.35, open_app, args=(url + ('/cannon' if args.cannon_only else ''),)).start()
    try:
        # V2 owns only the handoff: Courier's existing runtime owns the work.
        if not args.cannon_only:
            RUNTIME_START = ensure_courier_runtime()
        server.serve_forever()
    finally:
        server.server_close()
        if 'cannon.web' in sys.modules:
            sys.modules['cannon.web'].close()


if __name__ == '__main__':
    main()
