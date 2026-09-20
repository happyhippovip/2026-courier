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

Read-only AWS discovery has already identified the intended running Linux/Ubuntu EC2 workload in the expected Frankfurt region.

For security, this public handoff intentionally does NOT preserve:
- account ID;
- public IP;
- instance ID;
- exact key-pair name;
- root/account ARN;
- credential material.

Current rule:
1. do not repeat already-completed instance discovery;
2. do not guess a private key;
3. prefer an AWS-supported access/recovery path such as EC2 Instance Connect or Session Manager if available;
4. after access, create a clean managed access path;
5. verify backup/rollback before migration;
6. move daily administration toward least-privilege IAM/roles rather than root use.

No destructive change, server terminate action, or migration cutover should be inferred from this handoff.

## Device/window interaction rule

All future instructions must follow:

`docs/agent-warehouse/OPERATOR_INTERACTION_PROTOCOL_2026-09-20.md`

Every command/prompt must say both:
- which device;
- which app/window.

## Current coordination recommendation

- Windows PC: stop repeating the same key search; preserve current Courier working state.
- MacBook: AWS discovery is complete enough for the next access/recovery step.
- iPhone: Remote Control / monitoring only.
- AWS: prefer managed access/recovery instead of guessing missing key material.

## Next integration milestone

1. establish AWS-supported access to the verified EC2 workload;
2. confirm the running Courier/cloud state;
3. create a clean managed access method;
4. back up and test restore;
5. only then continue migration/deployment work.


## MacBook UI simplification decision

Administrator preference: screenshot-driven guidance with as few windows as possible.

Preferred live Mac workspace:
- ChatGPT/browser: coordination and screenshot exchange;
- one active Claude Code Terminal: execution + Remote Control owner;
- AWS browser tab only when AWS console inspection is needed.

Claude Desktop can be minimized for infrastructure setup unless a task explicitly requires it.

Old/duplicate Terminal or Claude Code sessions should be minimized first. Close only after confirming they are not the active Remote Control session and contain no running task that must be preserved.

The currently known active Remote Control session was shown in a Claude Code Terminal window with `/remote-control is active`; that Terminal should be kept open and may be minimized, not closed, during setup.


## SSH key attribution update — 2026-09-20

Correction after the broader Windows search:

- no matching Courier EC2 private key was found on the Windows PC;
- certificate-bundle `.pem` files found in development environments were correctly excluded as non-SSH keys;
- no matching historical SSH command/key path was established;
- no private key contents were printed;
- no SSH connection was performed during discovery.

The MacBook search also found no matching Courier EC2 private key.

Operational conclusion:
- do not keep repeating the same local key search;
- do not guess a private key or SSH identity;
- use an AWS-supported recovery/access method such as EC2 Instance Connect or Session Manager if available, then establish a clean managed access path.


## MacBook SSH key search result — 2026-09-20

Claude Code completed a read-only, name-based search on the MacBook for the EC2 key pair `courier-key-2`.

Result:
- `MATCHING_KEY_FOUND=NO`
- search covered normal user locations plus iCloud/Mobile Documents;
- Spotlight and a broader home-folder search were used;
- no file named `courier-key*` was found;
- certificate `.pem` files and unrelated general Mac SSH keys were excluded as non-matches;
- no SSH connection was attempted;
- no files or permissions were changed.

Operational conclusion:
- stop repeating the same Mac key search;
- keep the Mac Claude Code session available/minimized;
- next key-attribution work belongs on the Windows PC or, if Windows also has no key, use a separate AWS-supported recovery/access path rather than guessing.
