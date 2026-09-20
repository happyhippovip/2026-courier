# Operator Interaction Protocol — Device + Window Labels

Date: 2026-09-20  
Status: mandatory interaction rule for human-guided setup work

## Purpose

Courier setup spans multiple devices and multiple interfaces at the same time. To prevent commands being pasted into the wrong place, every operational instruction must identify BOTH:

1. the physical device;
2. the exact app/window where the text belongs.

## Mandatory heading format

Use one of these headings before every command or prompt:

- `WINDOWS PC — POWERSHELL`
- `WINDOWS PC — CLAUDE CODE APP`
- `WINDOWS PC — BROWSER / CLAUDE CLOUD`
- `MACBOOK — TERMINAL`
- `MACBOOK — CLAUDE CODE APP`
- `MACBOOK — BROWSER / AWS CONSOLE`
- `IPHONE — CLAUDE / REMOTE CONTROL`
- `AWS CLOUD — SSH SESSION` only after a verified connection exists.

Never give a bare command block without one of these labels when multiple devices are active.

## Copy/paste rule

Immediately before a code block, state where to paste it in plain language.

Example:

### MACBOOK — CLAUDE CODE APP

Paste the following into the Claude Code input box at the bottom of the MacBook Claude Code window.  
Do NOT paste it into Terminal.

```text
READ ONLY.
...
```

## Command-type rules

### Terminal / PowerShell commands

Commands such as these belong in a shell:

- `cd`
- `Set-Location`
- `git status`
- `aws sts get-caller-identity`
- `aws ec2 describe-instances`
- `ssh`
- `scp`

Always label the shell and device.

### Claude Code agent prompts

Natural-language prompts beginning with instructions such as:

- `READ ONLY.`
- `Do not modify AWS.`
- `Return: ...`

belong in the Claude Code app/session input, not the operating-system shell.

### Browser / cloud-console instructions

Clicks such as:

- AWS Console -> EC2 -> Instances;
- Claude Cloud / Remote Control session selection;

must be labeled as browser instructions, not terminal instructions.

## One active step at a time

When the human is switching between Windows, MacBook and phone:

1. give one device's next action;
2. wait for its result;
3. then advance that device;
4. parallel work is allowed only when explicitly labeled `PARALLEL`.

## Boss-mode rule

When the user asks the assistant to coordinate the whole setup, the assistant should:

- name the active device;
- name the active window;
- state the single next objective;
- say whether the other device should WAIT or RUN IN PARALLEL;
- avoid sending work to another computer unless clearly announced.

Recommended status footer:

```
ACTIVE: MACBOOK — CLAUDE CODE APP
WINDOWS: WAIT
IPHONE: MONITOR ONLY
AWS: READ-ONLY / NOT CONNECTED
```

## Safety rule

Never infer that an AWS host, SSH user, key, or server role is correct merely because a host key appears in `known_hosts`.

Before the first SSH connection, verify the intended instance, login user and private key source.

## Persistence

Any future setup handoff should reference this protocol so a new agent does not repeat the device/window ambiguity.
