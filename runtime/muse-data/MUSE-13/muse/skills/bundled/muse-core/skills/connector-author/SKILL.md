---
name: connector-author
experimental-gate: tag
description: Build a new daemon connector from a conversation — "build / create / make me a connector for X", "connect the daemon to <a service, CLI, queue or feed> that has no connector yet". Runs a short interview (source, delivery, auth, conversation, reply, filters, gate, name), scaffolds a connector skill from the starter template, checks it against the daemon's three rules, and hands back a branch. For a coordinator the daemon delegated the ask to.
---

# Connector author

You are the conversation coordinator the daemon delegated a "build me a
connector for X" to (ADR 37480 D12; spec 25011 FR-37480-44). This skill ships
behind the `MUSE_EXPERIMENTAL_TAG` gate like the daemon (`experimental-gate:
tag` above). The daemon itself never runs this: it delegated the conversation
as it delegates any non-immediate work, and you own it from here.

Three things, in order: an **interview** (your judgment), a **scaffold** and
a **check** (two scripts, the mechanical part), and a **hand-back** in the
thread. The scripts copy a template and run the daemon's conformance script;
every decision about what the source is, what a conversation is, how a reply
is posted, and what the stub bodies contain is yours, from the human's
answers. Keep the mechanics as they are; do not add a code generator.

The wrapper that delivered this body carries `skill-dir="<absolute path>"`.
That directory holds only this `SKILL.md`, `references/interview.md`,
`scripts/new_connector.py`, `scripts/connector_conformance.py` (the engine
`check` runs; never run it yourself) and `templates/SKILL.md.tmpl` +
`templates/connector.py.tmpl` (the starter the scaffold copies). You read
one file and run one script; join `skill-dir` to these two paths and write
them out — no `ls`, no `find`, never the `path` attribute:

```
<scaffold> = scripts/new_connector.py
<interview> = references/interview.md
```

## 1. Interview

Read `references/interview.md` once, before your first question. It lists the
eight questions in order, what each answer is for, and the `--answers` JSON
key each fills. The rules:

- **One question per turn**, in the order given; skip a question the human's
  words already answered (say what you took from them). Never ask two at
  once and never ask for a secret value — names only.
- **A finite choice is a card** with buttons or a `static_select` when the
  connector that delivered this conversation renders cards (the Slack
  connector's `references/slack-ui.md`, which your starter names, says how;
  a lane it cannot render on gets a numbered text list); **free text
  otherwise**. The delivery question (push / poll / an existing connector's
  source) and the placement question (project skill / plugin package) are
  finite; the rest are free text.
- **Redirect instead of build** when a connector already in the catalog lists
  the source (question 2): hand back that connector's connect words and stop;
  `<scaffold> scaffold --delivery stream` prints the words and writes nothing.
- **Summarize, then confirm.** After the last answer post ONE summary of every
  answer (a card or a list) and ask for a confirm. Nothing is written before
  the confirm. A "stop", "cancel" or "never mind" at any point ends the task
  with nothing on disk — say so in one line.

## 2. Scaffold and fill in

Write the answers as JSON (the keys in `interview.md`) and run ONE call:

```
python3 <scaffold> scaffold --connector <name> --delivery poll|push --answers <file> [--plugin <id>] --root <workspace root>
```

It prints one JSON line: `outcome` (`scaffolded` | `redirect` | `refused`),
the `skill_dir`, the `script`, the `tests_dir`, every `written` path, the
`todo` list (answers the human did not give) and `next` (the check command,
the fill-in reminder, the branch commands). A `refused` line names the cause
(an occupied path, a bad name) and wrote nothing; fix the cause and run it
again, never `rm` the human's files to make room.

Then **fill the stubs yourself**: open the connector script it wrote and
replace each `TODO(answer <id>)` body with real code from that answer (the
poll command and its output parse, the push payload mapping, the reply verb,
the describe fields, what "addressed to me" means). Keep the `FIXTURE_FILE`
branches — the generated tests and `check` drive them — and keep the three
mechanical rules the template implements (the per-key lock, the idempotency
ledger, the feed line) and the `status --json` source fields
(`sources_available`, the per-source `listeners` records with their
`exit`/`ended_at` after a non-zero end, which the daemon's `start` records
without a model call; a source you add
goes into `SOURCES_AVAILABLE`). The SKILL.md it wrote is the connector's own contract:
update its "Not filled in yet" section as you fill each stub.

Then run the check and read its one line:

```
python3 <scaffold> check --skill-dir <skill_dir> [--tests-dir <tests_dir>]
```

`outcome: ok` means every rule (`single-listener refusal`, `reply
idempotency`, `feed grammar`, `status contract`) is `ok` and the generated
tests pass. A `FAIL`
names the rule; fix the script, never the check. Do not hand back a branch
whose check is red.

## 3. Hand back

Commit on a branch named `feat/connector-<name>` in the workspace (the
`next` list has the exact commands) and reply in the thread, in the
requester's language, with: the branch, the connect words (`/daemon connect
<name>` or `muse daemon connect <name>`), what `check` proved, and what you
could not verify without their credentials (name the environment variable
names). Open a PR only when they asked for one. For a plugin package
(`--plugin <id>`), also list the registration the human's PR must do — the
workspace `Cargo.toml` member, the product composition crate roster,
`scripts/ci-impact-plan.sh`, a CI workflow for its suite, and the internal
Buck fixup (`extra_srcs = ["plugin.json", "skills/**"]` in
`fbcode/musecode/fixups/<crate-name>/fixups.toml`, because the crate embeds
non-Rust files) — you never register a plugin package yourself.

## Limits

- Placement default is a project skill (`.agents/skills/<name>/`): the
  catalog lists it at once and `/daemon connect <name>` mounts it with no
  rebuild. A plugin package is for a connector that ships in the product.
- A source the general event-stream connector already lists is that
  connector's subscription, never a new skill (redirect).
- You never touch the daemon's registry, its SKILL, or another connector's
  files; the scaffold writes only under the paths its line reports.
