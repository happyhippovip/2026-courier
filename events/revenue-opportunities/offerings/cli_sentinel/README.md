# Task Sentinel CLI — Zero-Dependency Background Process Watchdog

A lightweight, zero-dependency Python utility for monitoring background task runners, verifying true kernel PID liveness, and managing POSIX `fcntl.flock` leases.

---

## Features
- **Kernel PID Signal Truth:** Uses `os.kill(pid, 0)` to verify worker health instead of trusting stale logs.
- **Heartbeat Gap Detection:** Automatically detects worker stalls when heartbeat age exceeds 30s.
- **POSIX Lock Leasing:** Clean, non-blocking atomic file fencing.

---

## Commercial Pro Licensing
- Free Core (Open-Source / MIT)
- Pro License (€29): Webhook integration, remote heartbeat sync, and multi-process crash alerts.
