"""Read-only local process telemetry. No command arguments, prompts or paths leave this module."""
import datetime
import json
import platform
import subprocess
import time
import urllib.error
import urllib.request


def cpu_seconds(value):
    parts = value.split(':')
    return sum(float(p) * 60 ** i for i, p in enumerate(reversed(parts)))


def classify(command):
    if '/Antigravity.app/' in command:
        return 'antigravity'
    if '/ChatGPT.app/' in command and ('/MacOS/ChatGPT' in command or command.endswith('/Resources/codex')):
        return 'chatgpt'
    if '/muse-bin-' in command or command.endswith('/muse'):
        return 'muse'
    return None


class LocalToolObserver:
    def __init__(self):
        self.previous = {}
        self.last_sample = None
        self.cached = None
        self.active_until = {}
        self.remote_sampled_at = 0.0
        self.remote_hosts = {}

    def observe_windows(self, now):
        """Read-only, bounded observation of the existing Windows Courier host."""
        if self.remote_hosts and now - self.remote_sampled_at < 30:
            return self.remote_hosts

        observed = {
            'hostname': 'DESKTOP-JDPRUGR',
            'status': 'UNKNOWN',
            'courier_health': 'UNKNOWN',
            'runtime_sha': None,
            'task_known': False,
        }
        try:
            with urllib.request.urlopen('http://192.168.178.87:8080/health', timeout=2) as response:
                payload = json.loads(response.read().decode('utf-8'))
                if response.status == 200 and payload.get('status') == 'healthy':
                    observed.update(status='ONLINE', courier_health='HEALTHY')
        except (OSError, ValueError, urllib.error.URLError):
            observed.update(status='OFFLINE', courier_health='UNREACHABLE')

        if observed['status'] == 'ONLINE':
            try:
                command = (
                    'Set-Location C:\\Users\\lol\\2026-workspace\\2026-courier; '
                    'Write-Output $env:COMPUTERNAME; git rev-parse HEAD'
                )
                result = subprocess.run(
                    ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=2',
                     'windows-ai', 'powershell', '-NoProfile', '-Command', command],
                    capture_output=True, text=True, timeout=4, check=True,
                )
                lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                if len(lines) >= 2:
                    observed['hostname'] = lines[-2]
                    observed['runtime_sha'] = lines[-1]
            except (OSError, subprocess.SubprocessError):
                # HTTP health remains authoritative for availability. SSH identity
                # is optional display evidence and never changes Courier state.
                pass

        observed['observed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.remote_sampled_at = now
        self.remote_hosts = {'windows': observed}
        return self.remote_hosts

    def snapshot(self):
        now = time.monotonic()
        if self.cached and self.last_sample is not None and now - self.last_sample < 4:
            return self.cached
        try:
            output = subprocess.run(['ps', '-axo', 'pid=,time=,comm='], capture_output=True, text=True, timeout=2, check=True).stdout
            current = {}
            for line in output.splitlines():
                fields = line.strip().split(None, 2)
                if len(fields) != 3:
                    continue
                pid, used, command = fields
                tool = classify(command)
                if tool:
                    current[pid] = (tool, cpu_seconds(used))
            elapsed = now - self.last_sample if self.last_sample is not None else None
            tools = {}
            for key in ('chatgpt', 'muse', 'antigravity'):
                matching = {pid: record for pid, record in current.items() if record[0] == key}
                measured = elapsed is not None and any(pid in self.previous for pid in matching)
                delta = sum(max(0, record[1] - self.previous[pid][1]) for pid, record in matching.items() if pid in self.previous and self.previous[pid][0] == key)
                cpu = round(delta / elapsed * 100, 1) if measured else None
                if cpu is not None and cpu >= 2:
                    self.active_until[key] = now + 8
                status = 'OFFLINE' if not matching else ('COMPUTING' if self.active_until.get(key, 0) > now else 'OPEN')
                tools[key] = {'status': status, 'process_count': len(matching), 'cpu_percent': cpu, 'activity_source': 'PROCESS_CPU_DELTA', 'task_known': False}
            self.previous = current
            self.last_sample = now
            self.cached = {
                'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'source': 'LOCAL_PROCESS_OBSERVER',
                'hosts': {
                    'mac': {
                        'hostname': platform.node(),
                        'status': 'ONLINE',
                        'task_known': False,
                    },
                    **self.observe_windows(now),
                },
                'tools': tools,
            }
            return self.cached
        except (OSError, subprocess.SubprocessError, ValueError):
            return {'source': 'LOCAL_PROCESS_OBSERVER', 'error': 'OBSERVATION_UNAVAILABLE', 'tools': {}}


observer = LocalToolObserver()
