# Unattended Permissions Preflight (Courier work unit, Muse 1.4.3)

What a normal Courier reviewer/worker unit on macOS observably needs.
Grounded in real sessions (git/gh/provider traffic as executed), not in
assumed defaults. Windows specifics stay with the Windows host/CI.

## 1. Network destinations (observed, per work unit)

| Destination | Used by | When |
|---|---|---|
| `github.com:443` | `git fetch/push/pull` | every refetch, push, worktree add |
| `api.github.com:443` | `gh pr/issue/run` API | every PR/issue/CI read, comment, create |
| GitHub CDN family (`objects.githubusercontent.com`, `codeload.github.com`) | git object transfer | conditional on fetch content (not separately granted) |
| Provider model endpoint, as configured | Muse model traffic | every model turn (no fixed hostname asserted here; see provider settings) |

NOT observed for a standard review/verify unit: npm, pip installs,
package registries, inbound connections, localhost servers (physical-runner
lanes bind 8080/8081 — lane-specific, not part of this preflight).

## 2. Workspace trust

- `~/.config/muse/`: `settings.json` (keys incl. `permissions`), `trust.json`
  + `auth.json` (presence only; contents never read or published).
- Workspace skills/rules load only under trust (`--trust-workspace`,
  run-scoped). Untrusted workspace content must not auto-execute.

## 3. Filesystem

- Read/write: the repo checkout (own detached worktrees under `/tmp` for
  scratch verification; shared checkout is foreign-owned — read-only).
- Write: `/tmp` scratch; session logs under `~/.local/share/muse` (runtime-owned).
- Never: other checkouts' state, keychain/credentials, secrets, ACLs,
  security settings, global installs.
- Tooling caveat (proven in-repo): path handling must be repo-root anchored,
  never CWD-relative — unanchored tools crash or act on the wrong tree when
  a scheduler/launcher sets another working directory.

## 4. Approval posture for unattended runs

- Default is approval on-request; sandbox ON. Keep both ON.
- `--user-input-auto-resolve` resolves headless prompts by CANCELING them
  (fail-closed). That is the correct unattended setting, not a stall.
- A session-scoped "don't ask again" grant DOES NOT persist across
  sessions. Never promise persistence; re-grant or restructure instead.
- NEVER use `--yolo`, `--disable-approval`, `--disable-sandbox`, blanket
  network modes, or unrestricted profiles to make an unattended run quiet.
- Unknown permission or external-effect request on an unattended run:
  fail closed, checkpoint the workkey with the exact gate, park it, and
  continue with unrelated safe work. Optimistic admission is a defect.

## 5. Session-grant non-persistence (explicit)

If a run needs a network destination outside section 1, request the narrow
grant for that run AND record it here as a gap: the next session starts
without it. Recurring grants for the same destination mean the table above
is incomplete — update the table, do not normalize re-granting.

## 6. Scope

Covers reviewer/verifier worker units (read, test, comment, branch, PR).
Physical-runner, installer, and provider-builder lanes carry extra
destinations and privileges defined by their own lanes — this preflight
does not speak for them.
