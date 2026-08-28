# 2026 Courier — local repository draft

This directory is a **local-only draft** for a future dedicated GitHub
repository named `2026-courier`. It is not a Git repository, has no remote,
and must not contain credentials, private source material, or production
content.

## Purpose

Carry a compact, auditable event envelope between a future GitHub-triggered
Work task and the existing local Courier / Control Thread:

`GitHub PR event -> Work -> Courier -> Control Thread -> 2026-Zentrale -> result`

The existing Control Thread remains the only local execution route. This draft
does not claim that GitHub alone can return data to a local machine; that
return route must be explicitly supported and tested after a connector is
authorized.

## Included files

- `schemas/courier_event.schema.json` — the compact envelope contract.
- `scripts/emit_noop.sh` — creates a deterministic test envelope in dry-run
  mode by default; `--write` writes only to `events/incoming/`.
- `docs/COURIER_PROTOCOL.md` — exactly-once, dedupe, retry, and PR-trigger
  rules.
- `events/` — local runtime folders. Event JSON is ignored by Git so that
  payloads are never accidentally committed.

## Security boundary

Never place passwords, access tokens, OAuth codes, API keys, personal data,
social-media assets, or production data in this directory. A future ChatGPT
connector should be granted access only to the dedicated external repository,
not to the full 2026 project.
