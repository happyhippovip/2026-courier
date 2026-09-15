# External Linux deployment

This is a narrow deployment wrapper around Courier's existing autonomous
supervisor. It stores the repository's `events/` directory in
`/var/lib/courier/events`, so queue records, task status, locks, and reports
survive service and host restarts. The checkout in `/opt/courier` is treated
as replaceable program code.

On a fresh Linux host with `git`, `python3`, and systemd:

```sh
sudo git clone --depth=1 https://github.com/happyhippovip/2026-courier.git /opt/courier
cd /opt/courier
sudo deploy/install.sh
sudoedit /etc/courier/courier.env
sudoedit /etc/courier/courier.secrets
sudo systemctl restart courier
```

`install.sh` is also safe to re-run to shallow-fetch the configured
`COURIER_BRANCH` (default `main`) and reinstall the unit. It creates the
unprivileged `courier` account, initializes state, and replaces the checkout's
`events` path with a symlink to durable state, preserving the checkout's
tracked event structure on first install. Configure workers and providers in
the two `/etc/courier` files; do not add credentials to the checkout.

The service starts and polls an empty durable queue without contacting Google,
ChatGPT, Codex, Windows, or macOS. Existing tasks decide whether to use an
available worker. Any existing GitHub-hosted bounded work remains configured
by its own task/provider environment; this service does not create a broker or
network dependency.

Courier's logs use a dedicated systemd journal namespace bounded to 200 MiB
with 100 MiB host free space reserved. Read them with:

```sh
sudo journalctl --namespace=courier -u courier.service -f
```

Supervisor reports older than `COURIER_REPORT_RETENTION_DAYS` are removed
after a successful polling pass. Durable queue/event records are deliberately
not pruned by this deployment wrapper.
