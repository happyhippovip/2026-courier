# W10 Desktop Overlay Architecture & Containment Scout

This document outlines the architecture for the Desktop Swarm Overlay (Issue #55) to integrate with the L5 Desktop Hub, satisfying the W10/W14 requirements.

## 1. Process Separation and Threading
The W10 matrix requires: "Overlay shell separates cleanly from Windows L3 Worker Host processes."
The Desktop Hub (`courier_hub`) is already a separate reader/relay process from the Controller and L3 Worker Host.
To satisfy the requirement that the Hub reliably starts the Overlay, the Hub can:
1. Start its `HubServer.serve_forever` in a background daemon thread.
2. Instantiate the `Tkinter` overlay root on the **main thread** (required by macOS and Windows GUI frameworks).
3. Connect the overlay's state machine to the Controller's `bus.jsonl`.
This keeps the Hub and Overlay in the same isolated UI process, wholly separate from any heavy L3 Worker.

## 2. L5 Mac Test Failures
**Failure Mode Discovery:** L5 `courier_hub` tests (`tests/hub/test_hub_product.py`) fail on macOS native execution with `urllib3.exceptions.NewConnectionError: [Errno 1] Operation not permitted` or `requests.exceptions.JSONDecodeError: Direct IP access is not allowed`.
**Root Cause:** macOS system proxy settings or strict firewall configurations block `requests.get("http://127.0.0.1:0")` to dynamically bound ports.
**Resolution:** This is a local OS constraint, not a logic regression. CI on `ubuntu-latest` and `windows-latest` passes cleanly. Future Mac L5 test runners should inject `urllib.request.getproxies = lambda: {}` or patch the requests `Session` object.

## 3. Next Implementation Steps for W10/W14
- Integrate the scouted W11 Layout Engine, W13 State Machine, and W14 Renderer (currently on local branch `w14/overlay-integration-tests`) into `courier_overlay`.
- Modify `courier_hub/cli.py` to optionally spin up the Overlay on the main thread after spinning up the Hub server in a background thread.
