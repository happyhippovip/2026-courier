# Courier Symphony — Current Setup Handoff

Date: 2026-09-20  
Status: public-safe operational handoff

## Purpose

This document preserves the important current setup state so future agents can continue without repeating discovery work.

Because the repository is public, this document intentionally excludes:

- private keys;
- API tokens;
- passwords;
- private email contents;
- customer data;
- cloud credentials;
- exact secret material.

## Windows state

Courier repository has been located and verified as a Git repository on the Windows PC.

Verified working repository:
- repository: `happyhippovip/2026-courier`
- current Windows branch: `ledger-reconciliation-final`
- remote: GitHub origin for `happyhippovip/2026-courier`
- branch was reported up to date with its matching origin branch at the time of inspection.

Local Windows working tree is NOT clean.

Observed modified files:
- `tests/conftest.py`
- `tests/test_retry_contract.py`

Observed untracked paths:
- `RECONCILIATION_RESULT.md`
- `docs/muse-workbench/`
- `scripts/revenue_worker_state/`
- `target_repo/`

Operational rule:
- do not run destructive reset/restore;
- do not discard these changes;
- do not blindly switch branches or pull over them;
- inspect and preserve before migration.

Claude Code was available on Windows and Remote Control had already been used successfully with a phone.

## Windows SSH discovery

The Windows `.ssh` directory contained host-history files but no SSH config and no private key was found in the initial `.ssh` listing.

Interpretation:
- historical SSH host records exist;
- this does NOT prove the correct cloud instance, login user, or private key;
- first SSH login must wait for proper instance/key attribution.

## MacBook state

Claude Code is open on the MacBook and Remote Control is active.

Current Mac objective:
- identify the intended AWS account/EC2 instances in read-only mode;
- do not modify AWS;
- do not SSH until instance + user + key are verified.

The current intended read-only AWS checks are:
- `aws sts get-caller-identity`
- `aws ec2 describe-instances --region eu-central-1`

If AWS CLI is unavailable, use the AWS Console in the browser and inspect EC2 instance metadata manually.

## Cloud state

Cloud migration is NOT yet considered complete.

Before first server connection:
1. identify the correct AWS account;
2. identify the intended EC2 instance;
3. determine instance OS/platform;
4. determine expected SSH username;
5. identify the matching private key;
6. verify backup/rollback plan;
7. only then perform first SSH connection.

No cloud purchase, destructive change, server start/stop/terminate, or migration cutover should be inferred from this handoff.

## Device/window interaction rule

All future instructions must follow:

`docs/agent-warehouse/OPERATOR_INTERACTION_PROTOCOL_2026-09-20.md`

Every command/prompt must say both:
- which device;
- which app/window.

## Current coordination recommendation

- Windows PC: continue local SSH-key/history attribution only.
- MacBook: perform AWS read-only identity/instance attribution.
- iPhone: Remote Control / monitoring only.
- AWS: read-only until instance + key + user are verified.

## Next integration milestone

Merge the two evidence streams:

Windows:
- historical SSH command/key path evidence.

MacBook/AWS:
- EC2 instance identity, platform and key-pair name.

Only after they agree should a single explicit SSH command be produced.
