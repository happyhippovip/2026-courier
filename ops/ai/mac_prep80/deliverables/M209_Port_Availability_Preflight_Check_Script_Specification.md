# M209 — Port Availability Preflight Check Script Specification

## 1. Overview & Authority
- **Task ID**: M209
- **Area**: PORT_PREFLIGHT
- **Status**: COMPLETE

## 2. Preflight Implementation
```python
import socket
def check_port_free(host='127.0.0.1', port=8081):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) != 0
```
Guarantees clean startup before process invocation.
