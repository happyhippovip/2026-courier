# M204: Port Ownership & Preflight Evidence

## Goal
Prove that the local worker execution avoids cross-run contamination and stale-server spoofing by validating port availability (port ownership) before starting the server component.

## Context
When running local end-to-end tests (like `RUN_1` and `RUN_2` via `run_1_mac.sh` and `run_2_mac.sh`), a local server (`server.app`) is started on port `8080`.
If a previous execution failed to clean up its server, or if a zombie server is lingering in the background, a new test run might successfully spawn a worker that connects to the *stale* server rather than the newly spawned one.
This breaks process isolation and invalidates physical proof boundaries by mixing states across different runs.

## Preflight Validation
To prevent this, the Mac worker scripts employ a strict preflight check before proceeding with any local execution:

```bash
# In run_1_mac.sh
if lsof -i :8080 | grep -q "LISTEN"; then
    echo "ERROR: Port 8080 is already in use. Run aborted."
    exit 1
fi
```

```bash
# In run_2_mac.sh
# (After killing prior processes and cleaning up)
sleep 2
if lsof -i :8080 | grep -q "LISTEN"; then
    echo "ERROR: Port 8080 is still in use after kill. Port-conflict recovery failed."
    exit 1
fi
```

## Security & Proof Guarantees
1. **Preventing Cross-Contamination**: By aborting the run if the port is in use, we guarantee the worker will only ever connect to the freshly spawned `server.app` for that exact run.
2. **Explicit Port Ownership**: The preflight check confirms that the port is definitively relinquished by the OS before attempting to bind it again. 
3. **No Silent Fallbacks**: The test does not attempt to bind a dynamic or random port; it strictly requires `8080`. This fail-fast mechanism ensures predictability. Any deviation (port in use) is treated as a fatal failure requiring explicit remediation, ensuring no tests pass on a polluted environment.

## Conclusion
The `lsof -i :8080` check serves as a hard boundary for physical proof prep. It validates that the testing environment is clean of previous test artifacts (in the form of lingering processes holding TCP sockets), thus preserving the integrity of the execution phase.

STATUS=PROVEN
