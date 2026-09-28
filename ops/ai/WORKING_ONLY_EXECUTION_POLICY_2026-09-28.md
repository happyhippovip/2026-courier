# Working-Only Execution Policy — 2026-09-28

Status: CANONICAL EXECUTION OVERRIDE

Purpose:
Courier must prefer proven working execution paths and must not waste operator time repairing optional third-party/provider/adapter paths during normal delivery work.

## Working-only rule

A path is ACTIVE only when it is currently proven usable for its intended role.

If an optional path fails with the same causal fingerprint twice:
- set PATH_STATE=DISABLED_UNTIL_TRIGGER;
- remove it from active routing;
- preserve evidence of the failure;
- use a known-good alternative if one exists;
- do not keep repairing or probing it during normal execution.

Do not delete historical evidence or source blindly. "Remove" means remove from ACTIVE routing unless a bounded repo task explicitly proves physical deletion is safe and useful.

## No vendor repair

Courier workers do not repair third-party provider products, IDEs, CLIs, account systems, billing, auth, or external infrastructure.

When such a dependency is broken:
1. classify once;
2. disable that path;
3. route to an already-working alternative;
4. return to product work.

## Git rule

Git remains durable source-control truth, but it is not a mandatory prerequisite for every Google IDE task.

When the repo is already open locally:
- use the current working tree first;
- use local files directly;
- do not require git show to read a prompt;
- do not require git fetch for read-only local work;
- if remote sync is unavailable, set REMOTE_SYNC_DEFERRED=YES and continue any task that does not require remote durability;
- only remote-durability tasks may block on remote Git availability.

Never fabricate a remote PASS.

## Google IDE direct mode

Known-good Google IDE execution is:
current opened repo -> direct instruction -> exact local files -> concrete work -> saved repo artifact/result.

Do not assume:
- a hidden claim API;
- a google_cli_worker_adapter.py;
- a prompt loader;
- a background daemon;
- a remote git-show step.

If those are not explicitly proven in the current runtime, do not use them.

## Task continuation

A direct IDE master must continue through multiple concrete tasks in one session.

After each task:
1. persist the deliverable/result;
2. select the next unfinished task from the same master;
3. continue.

A single completed subtask is not a reason to return to the operator.

## Stop conditions

Return only for:
- real permission/auth/admin/payment/safety/legal gate;
- destructive truth conflict;
- required remote durability with no working remote path;
- provider hard limit;
- explicit operator stop.

Do not stop merely for:
- one finished subtask;
- one unavailable optional tool;
- one failed provider path;
- temporary absence of remote sync;
- family completion when another legal family exists.

## Product principle

Keep the active system small:
WORKING -> ACTIVE
BROKEN/UNPROVEN -> DISABLED
REPAIRED AND RETESTED -> ACTIVE AGAIN

No speculative repair backlog for third-party tools during the product critical path.
