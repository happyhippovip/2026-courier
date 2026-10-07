# L6 handoff: shipping the Desktop Hub in the Windows EXE

This page is L5's handoff to L6 (Windows packaging). It is written against the
repository as it stands: `main` at e3d785f7 plus PR #74 (Desktop Hub), with
reference to the open L6 branch `lane/L6-windows-packaging`. L5 implements
none of this.

## What has to run on the customer's machine

| Process | Command (embedded Python, cwd = install dir) | Owns |
| --- | --- | --- |
| Controller | `python -m courier_core.serve --home <H> --port <CP>` | `<H>/courier.db`, `<H>/run/controller.lock`, `<H>/run/controller.token` |
| Worker host | `python -m courier_worker.host --home <H> --controller http://127.0.0.1:<CP> --max-tasks 1 --heartbeat 2` | `<H>/run/worker.lock`, `<H>/outbox`, `<H>/artifacts` |
| Desktop Hub | `python -m courier_hub --home <H> --controller http://127.0.0.1:<CP> --port <HP>` | nothing on disk (it only reads `<H>/courier.db`) |

- **`<H>`:** the controller's home, proposed `%LOCALAPPDATA%\Courier` (per user).
  - The hub's `--home` must be the controller's `<H>`: it reads `<H>/courier.db` and `<H>/run/controller.token`.
  - The worker keeps its own locks and outbox under its `--home`. Using the same `<H>` is simplest, but only the hub strictly needs the controller's.
- **`<CP>`, `<HP>`:** fixed ports from the installer's config, not `0`. The hub finds the controller only through `--controller`.
  - Today the controller picks a random port when given `--port 0` and writes it nowhere except stdout (`--print-port`).
  - The launcher must either pass a fixed `--port`, or read `--print-port` and hand that URL to the worker and the hub.
  - If L2 later writes `<H>/run/controller.port`, the hub can discover it. That change is L2's to make, not L5's.

## Entrypoints and files to package

- **Python modules:** `courier_core`, `courier_worker`, `adapters`, `courier_hub`. All are standard library only; no third-party runtime dependency.
- **Hub static files:** `courier_hub/static/*` (`index.html`, `hub.js`, `hub_core.mjs`, `hub.css`, `favicon.svg`). The hub finds them through its own package path, `Path(__file__).parent / "static"`.
  - With an embedded `python.exe` and the source tree, nothing extra is needed.
  - A frozen build (PyInstaller) must add `courier_hub/static` as data, and `pyproject.toml` already declares it as package data.
- **Worker adapter runner:** it is started as `sys.executable <install>/courier_worker/adapter_runner.py <request>`.
  - With the embedded `python.exe` used by `CourierLauncher.cs` on the L6 branch this works as is.
  - A single-file frozen EXE would break it, because `sys.executable` would be the EXE. Keep the embedded Python layout, or have L3 add a frozen-mode runner entry.

## Where the L6 branch stands today

Checked against `lane/L6-windows-packaging` at 48f7b8bb (`scripts/windows_worker/launcher/CourierLauncher.cs`):

- The launcher starts only the worker host (`courier_worker.host`), with `--home %PROGRAMDATA%\CourierWorker` and the controller URL from `config.json` (`COURIER_SERVER`). It does not start the controller or the hub yet.
- It already puts its child in a Job Object with kill-on-close. Start the controller and the hub in the same job, so closing the launcher leaves no orphans.
- It falls back to `uv run python` when `<install>\python\python.exe` is missing. A clean machine has no `uv`, so the embedded Python must be shipped.
- `%PROGRAMDATA%` is shared by all users. If the controller's home goes there, `run\controller.token` needs an ACL that only the owning user can read. Otherwise, keep the controller's home per user as proposed above.

## Lifecycle

1. **Start order:** controller, wait for `GET /v1/health` = 200 (with the token), then worker host, then hub, then open the default browser at `http://127.0.0.1:<HP>/` (Python `webbrowser` or `ShellExecute`).
2. **Single instance:**
   - The controller and worker refuse a second copy per home (lock files).
   - The hub has no lock: with a fixed `<HP>` a second hub fails to bind, and the launcher should then just open the browser at the running hub.
3. **Stop:**
   - Controller: `POST /v1/shutdown` (or CTRL_BREAK).
   - Worker: CTRL_BREAK (it was started with `CREATE_NEW_PROCESS_GROUP`).
   - Hub: may simply be terminated; it holds no state and writes nothing.
4. **Restart:** any process can restart alone. The hub recomputes everything from the journal on its next read. An open browser tab reconnects by itself (backoff up to 30 s) and shows "Courier isn't running" while the controller is down.
5. **Upgrade:** replace the install directory. Data lives in `<H>` and survives. A newer controller rebuilds an older projection from the verified journal on first start; a damaged journal starts in safe mode (read-only), which the hub shows as a banner.
6. **Uninstall:** remove the install directory. Removing `<H>` must be a separate, explicit choice, because it deletes the customer's history.

## Logs and support

- Each process logs to stderr. The launcher should redirect them to `<H>\logs\controller.log`, `worker.log` and `hub.log`.
- The hub logs no request bodies, and no process ever logs the controller token.
- Support diagnostics:
  - `GET /v1/health` gives mode, head sequence and build identity.
  - Every receipt in the hub has a "For support" section with ids and event names, and a "Save support record" link.
  - That link (`GET /hub/api/items/<id>/support`) downloads one item's record as a JSON file: its runtime ids, event names, hashes, receipt and the hub's build identity.
    - It never includes the controller token, task payloads or any other item's history.
    - Support can ask the customer for this file instead of the database.

## Security assumptions L6 must keep

- All three bind `127.0.0.1` only. Do not open firewall ports.
- The hub refuses foreign `Host` headers and requires `X-Courier-Hub: 1` plus JSON on every POST. Do not put a proxy in front of it that rewrites `Host`.
- `<H>\run\controller.token` must stay readable only by the user.

## Clean-machine acceptance (proposed)

On a fresh Windows 11 VM with no Python installed:

1. Install. Launch from the Start menu. The browser opens the hub and shows "Nothing needs you".
2. Run the scenario `python -m courier_hub.demo` performs (a checked task, a non-idempotent task whose worker is killed, a running task), driven through the installed processes. The hub must show:
   - one Needs-you card;
   - one Working card;
   - one "Checked by Courier".
3. Choose "It happened". The card moves to Done as "Confirmed by <user>", without the check mark.
4. Reboot the VM and relaunch. The same Done items come back, nothing reruns, and no orphan worker processes remain (Task Manager).
5. Uninstall. The install directory is gone and `<H>` remains unless removal was chosen.
