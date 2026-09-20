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


## Screenshot-Driven Administrator Mode

When the administrator is present and sends a screenshot, use a fast guided workflow instead of long explanations.

### Required response format

1. Name the device.
2. Name the exact window/app.
3. Give only the next concrete action.
4. Say what the other visible windows should do: KEEP OPEN / MINIMIZE / WAIT / CLOSE.
5. Avoid repeating background theory unless the screenshot shows a new risk or ambiguity.
6. If a command is required, provide only the command that belongs in that named window.
7. After the command, ask for the next screenshot/result rather than predicting multiple future screens.

Example:

```
MACBOOK — CLAUDE CODE TERMINAL
Paste:
<command>

MACBOOK — OTHER WINDOWS
ChatGPT: KEEP OPEN
Claude Desktop: MINIMIZE
Old duplicate Terminal: MINIMIZE
AWS Browser: WAIT

NEXT: send screenshot after the command finishes.
```

### Minimal-window rule

Prefer the smallest stable working set.

Default Mac setup:
- one ChatGPT/browser window for the human + assistant coordination;
- one active Claude Code Terminal session;
- one AWS browser tab only when AWS console work is needed.

Claude Desktop is optional for this setup and may be minimized unless a task explicitly belongs there.

Duplicate Terminal/Claude Code sessions should not be used in parallel unless explicitly required. If one session is confirmed to be the active Remote Control session, keep that one and minimize old duplicate sessions.

Do not tell the administrator to close the active Claude Code Terminal that owns the current Remote Control session. Closing that Terminal may stop the local Claude Code process/session. Minimize it instead when not actively entering commands.

### Prompt-routing shorthand

Use these exact labels:

- `MACBOOK — CLAUDE CODE TERMINAL`
- `MACBOOK — NORMAL TERMINAL`
- `MACBOOK — CLAUDE DESKTOP APP`
- `MACBOOK — AWS BROWSER`
- `WINDOWS PC — POWERSHELL`
- `WINDOWS PC — CLAUDE CODE TERMINAL`
- `IPHONE — REMOTE CONTROL`

The operator should never have to infer where a command goes.

### Administrator fast-mode principle

When the administrator says they can follow along and wants speed:
- favor one-step instructions;
- avoid saying "you should see..." unless that visible result is necessary for safety;
- do not open extra windows if an existing window can do the job;
- reduce duplicate tools and duplicate sessions;
- preserve state before cleanup;
- treat "close" and "delete" as different actions;
- never delete apps, repositories, sessions, keys, or project data merely to simplify the desktop.


## Continuous persistence rule

When the founder says an idea/rule is important or asks for urgent preservation:

1. save it to the correct Agent Warehouse document;
2. keep the public-repository secret policy;
3. update the machine-readable manifest;
4. update the master rules/ideas snapshot when it changes a core principle;
5. correct earlier handoff statements if later evidence disproves them;
6. prefer a concise canonical rule over copying raw chat logs into GitHub.
