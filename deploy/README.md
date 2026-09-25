# Linux deployment (server + verifier + GitHub dispatcher + watchdog)

`deploy/courier.service` runs `deploy/run-supervisor.sh` from `/opt/courier`.
The supervisor starts `scripts/courier_verifier.py`,
`scripts/courier_github_dispatcher.py`, `scripts/courier_watchdog.py` and
`gunicorn -w 1 --threads 4 -b 0.0.0.0:8080 server.app:app`, and refuses to
start unless `COURIER_API_KEY` and `COURIER_VERIFIER_API_KEY` are set and
differ.

On a fresh Linux host with `git`, `python3` and systemd:

```sh
sudo git clone --depth=1 https://github.com/happyhippovip/2026-courier.git /opt/courier
cd /opt/courier
sudo deploy/install.sh            # venv + flask/gunicorn/requests, installs and enables the unit
sudoedit /opt/courier/deploy/.env # set both keys (created from env.example, mode 600)
sudo systemctl restart courier
```

`install.sh` never overwrites an existing `deploy/.env` and does not start the
service, because placeholder keys make the supervisor fail closed and systemd
would restart-loop. `deploy/.env` is git-ignored.

Health and status (status needs the worker key in the environment):

```sh
deploy/courier-health.sh
COURIER_API_KEY=... deploy/courier-status.sh
```

Workers run on their own hosts and point `COURIER_SERVER` at this server:

- macOS: `scripts/mac_worker/setup_keychain.sh`, then `scripts/mac_worker/install.sh` (LaunchAgent).
- Windows: `scripts/windows_worker/bootstrap.ps1` (writes `config.json`, installs a Scheduled Task).
- GitHub: tasks are dispatched by `courier_github_dispatcher.py` to `.github/workflows/courier_worker.yml`.

On macOS the whole runtime can instead run under launchd via
`deploy/install_mac_runtime.sh` (same `run-supervisor.sh`).

`deploy/journald-courier.conf` and `deploy/install-github-runner.sh` are
optional host helpers and are not used by `install.sh`.
