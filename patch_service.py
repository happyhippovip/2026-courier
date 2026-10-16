import re

with open("courier_worker/service.py", "r") as f:
    content = f.read()

# 1. Update claim to accept resource_state
content = content.replace(
    'def claim(self, worker_id: str) -> Optional[dict]:\n        try:\n            status, payload = self._call("POST", "/claim", {"worker_id": worker_id})',
    'def claim(self, worker_id: str, resource_state: str = "NORMAL") -> Optional[dict]:\n        try:\n            status, payload = self._call("POST", "/claim", {"worker_id": worker_id, "resource_state": resource_state})'
)

# 2. Update heartbeat to accept resource_state
content = content.replace(
    'def heartbeat(self, worker_id: str, dispatch_ids: list) -> dict:\n        status, payload = self._call("POST", "/heartbeat",\n                                     {"worker_id": worker_id, "active_dispatches": dispatch_ids})',
    'def heartbeat(self, worker_id: str, dispatch_ids: list, resource_state: str = "NORMAL") -> dict:\n        status, payload = self._call("POST", "/heartbeat",\n                                     {"worker_id": worker_id, "active_dispatches": dispatch_ids, "resource_state": resource_state})'
)

# 3. Add state tracking to WorkerLoop
content = re.sub(
    r'self\.heartbeat_s = heartbeat_s\n(.*?)self\._watchers = {}',
    r'self.heartbeat_s = heartbeat_s\n\1self._watchers = {}\n        self._cooldown_until = 0.0\n        self._last_resource_state = "NORMAL"',
    content, flags=re.DOTALL
)

# 4. Update _send_heartbeat to send resource_state
content = content.replace(
    'payload = client.heartbeat(self.worker_id, [spec.dispatch_id])',
    'payload = client.heartbeat(self.worker_id, [spec.dispatch_id], resource_state=self._last_resource_state)'
)

# 5. Update iterate to check pressure, handle hysteresis, and send heartbeat if idle
iterate_new = """
    def iterate(self, stop: threading.Event) -> str:
        \"\"\"Run one claim-execute-deliver cycle. Never loops by itself.\"\"\"
        import time
        try:
            self.flush_outbox()
        except ControllerError:
            return "idle"
        client = self._client or self._client_factory()
        self._client = client
        
        reason = self.host._pressure_probe()
        now = time.time()
        
        if reason is not None:
            self._last_resource_state = "PRESSURED"
            self._cooldown_until = now + 60.0  # 1 minute hysteresis
        elif now < self._cooldown_until:
            self._last_resource_state = "COOLDOWN"
        else:
            self._last_resource_state = "NORMAL"
            
        if self._last_resource_state != "NORMAL":
            # Just send heartbeat to report state and remain idle
            try:
                client.heartbeat(self.worker_id, [], resource_state=self._last_resource_state)
            except ControllerError:
                pass
            return "idle"
            
        claim = client.claim(self.worker_id, resource_state=self._last_resource_state)
        if claim is None:
            # Send idle heartbeat
            try:
                client.heartbeat(self.worker_id, [], resource_state=self._last_resource_state)
            except ControllerError:
                pass
            return "idle"
"""

content = re.sub(r'    def iterate\(self, stop: threading\.Event\) -> str:.*?(?=        try:\n            spec = resolve_spec)', iterate_new.lstrip('\n'), content, flags=re.DOTALL)

with open("courier_worker/service.py", "w") as f:
    f.write(content)
