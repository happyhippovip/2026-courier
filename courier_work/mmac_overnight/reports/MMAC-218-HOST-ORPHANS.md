# MMAC-218 — Host stability inspection (read-only)

Host fine (load ~5.5 falling). No Courier-owned runaway: load comes from live
agent workers (foreign, untouched).

FINDING-HOST-ORPHANS (LOW): two sets of pytest-spawned children outlived their
runs with PPID=1 — an 18.3h verifier polling a dead 127.0.0.1:8080 (stderr log
2.7MB and growing; owner tests/test_run_physical.py::test_run_physical_success)
and four 7.3h fake_config_daemon.py (owner file unidentified, exact tmp path in
JSON). Fix belongs to test owners (finalizer kill+wait; optional verifier
consecutive-failure park). No action taken here: foreign processes, no-kill rule.
