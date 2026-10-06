# macOS Muse unattended runner

This is **development/operator tooling**, not customer-facing Courier V1 UI.

It exists because Muse's in-session `/loop` is intentionally a sequence of bounded scheduled turns: an individual run can finish and return the composer while the recurring job remains scheduled.

For stronger unattended behavior when the terminal may be closed, this repo provides a macOS `launchd` wrapper around `muse exec --prompt-file`.

## Properties

- one Muse process per invocation;
- every five minutes by default;
- launchd owns recurrence;
- atomic single-owner lock prevents overlap;
- stale lock recovery is bounded;
- resource-pressure detection creates a sticky `RESOURCE_PAUSE`;
- provider/non-resource failures back off for 15 minutes;
- durable state lives under `~/.courier/dev-night/`;
- each Muse invocation is a deep batch, targeting 4–8 non-duplicate read-only work units;
- no workflow/child-agent/subagent fanout;
- no product-source writes;
- before each batch the checkout is fast-forwarded when it is clean, so the runner reviews current code (`COURIER_NIGHT_AUTO_UPDATE=0` turns this off).

This is deliberately separate from the customer runtime. Courier V1 itself continues to use the canonical ledger/controller/worker architecture.

## Install

Use a clone that only the runner touches, on `integration/v1`, and run the installer from a terminal where `muse` works:

```bash
git clone --branch integration/v1 https://github.com/happyhippovip/2026-courier.git ~/courier-night
cd ~/courier-night && bash scripts/install_macos_muse_night_runner.sh
```

The installer creates one user LaunchAgent:

`com.couriersymphony.dev.muse-night`

and immediately kicks it once.

## Status

```bash
bash scripts/macos_muse_night_status.sh
```

Important files:

- `~/.courier/dev-night/STATE.md`
- `~/.courier/dev-night/runner.log`
- `~/.courier/dev-night/RESOURCE_PAUSE`
- `~/.courier/dev-night/BACKOFF_UNTIL`

## Resource pause

If a run sees EMFILE / os error 24 / related spawn pressure, it writes `RESOURCE_PAUSE` and future scheduled runs fail closed without probing.

After the host is genuinely stable, the operator may explicitly re-arm it:

```bash
rm ~/.courier/dev-night/RESOURCE_PAUSE
launchctl kickstart -k gui/$UID/com.couriersymphony.dev.muse-night
```

Do not automate clearing the pause.

## Uninstall

```bash
bash scripts/uninstall_macos_muse_night_runner.sh
```

Uninstall preserves state/logs.

## Why not just queue 100 prompts?

A large manual prompt queue retains duplicate text and still has no strong cross-turn ownership primitive.

The runner instead persists queue state outside the chat and launches a fresh bounded headless turn when needed.

The Muse CLI's own `/loop` remains useful when the interactive session stays open. The external runner is the stronger fallback for unattended periods and terminal restarts.
