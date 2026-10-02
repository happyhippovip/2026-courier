# Muse Autonomous Operation Rules

Date: 2026-09-20  
Status: working operational rules

## Goal

Make trusted Courier development runs require as little repetitive human clicking as possible while preserving meaningful safety boundaries.

## Preferred autonomous startup

Known working direction for Muse Code 1.3.0:

```
--trust-workspace --approval-mode never
```

Use a dedicated Auto launcher for autonomous sessions.

## Important separation

`approval-mode never` and sandboxing are different controls.

Desired autonomous mode:
- workspace trusted;
- no repetitive Proceed/tool approval prompts;
- sandbox remains enabled;
- project boundaries remain explicit;
- no hidden privilege escalation.

Do not assume `--yolo` or `--disable-sandbox` is necessary for autonomy.

## If confirmations still appear

Classify the source before changing anything:

```
MUSE_APPROVAL
MUSE_SANDBOX
OS_PERMISSION
SUDO_OR_ADMIN_PASSWORD
CLAUDE_CODE_APPROVAL
BROWSER_LOGIN
OTHER
```

Only solve the actual owner of the prompt.

## Workspace rule

Before product work, verify the active workspace/root is the intended Courier/Muse project root.

Do not work around a wrong active workspace by reaching into another project with absolute paths.

## Serial autonomous work

For Courier:
- one externally active task at a time where required;
- persist result;
- verify;
- reconcile;
- continue only after DONE;
- UNKNOWN blocks next;
- do not mass-preallocate huge task counts.

## Stop conditions

Stop for genuine:
- HUMAN decision;
- MONEY/spend approval;
- SAFETY;
- PERMISSION;
- ambiguous external state;
- contradictory verification;
- unknown result after a side effect.

## Operator shorthand

When the founder wants Muse to continue from known context, short restart phrases may be used only if the durable project state makes the intended next work unambiguous.

A short phrase never overrides safety gates or an UNKNOWN result.
