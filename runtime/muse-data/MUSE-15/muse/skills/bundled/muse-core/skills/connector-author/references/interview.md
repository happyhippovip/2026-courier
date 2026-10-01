# Connector-author reference: the interview

The eight questions, in this order (ADR 37480 D12; spec 25011 FR-37480-44(b)).
Ask one per turn; skip a question the human's words already answered and say
what you took. Each answer fills the `--answers` JSON key shown; a key the
human did not give becomes a `TODO(answer <key>)` stub in the scaffold and a
line in its "Not filled in yet" section. Never ask for a secret value.

| # | Question (finite → card; free → text) | Answers key(s) |
| --- | --- | --- |
| 1 | **The source.** What does the connector connect (a service, a CLI, a queue, a feed), and where do the messages a human wants answered appear? | `source.name`, `source.word` (the one-word `--source` the listen takes; `status --json` lists it under `sources_available`), `source.summary` |
| 2 | **How it delivers** — finite: **push** (the source calls a webhook / posts to a local endpoint), **poll** (a CLI or API asked repeatedly; ask for the exact command and its output shape), or **an existing event-stream connector's source** (a connector already in the catalog lists this source: the redirect). | `delivery` (`push` / `poll` / `stream`); `poll.command`, `poll.output`, `poll.interval_s`; `push.port`, `push.payload`; `stream.connector`, `stream.source` |
| 3 | **Identity and auth.** Which account does the connector act as, and how does it authenticate — the environment variable NAMES or the login the source uses? | `auth.identity`, `auth.env` (a list of names) |
| 4 | **What one conversation is** — the container an alias `c<n>` stands for (a thread, a ticket, a room, a run) and the stable id the registry keys on. | `conversation.unit`, `conversation.id_rule` |
| 5 | **The reply verb.** How is a reply posted back into that container (the exact command or endpoint, with `{conversation}` and `{text}` where they go), and does the source render markdown? | `reply.command`, `reply.summary`, `reply.markdown` |
| 6 | **Default filters.** What does "addressed to me" mean on this source (mention, assigned, reply-to-me)? Anything wider is asked for in the connect prompt, never defaulted. | `filters.default` (one word; `mention` unless they say otherwise), `filters.meaning` |
| 7 | **Gate and environment.** Behind `MUSE_EXPERIMENTAL_TAG` like the daemon (yes by default; it rides the SKILL frontmatter). A plugin placement always binds one product gate as well, named `<plugin id>_plugin` by the scaffold's crate; a project skill has no product gate. | `gate.experimental_tag` (true/false) |
| 8 | **Name and placement** — the connector id (kebab-case, `<name>-connector` unless they name it) and, finite: a **project skill** (`.agents/skills/<name>/` in the workspace — the default: no rebuild, the catalog lists it at once) or a **plugin package** (`crates/plugins/<id>/`, shaped like the general event-stream connector's plugin, for a connector that ships in the product; its crate still needs a reviewed registration PR, and because it embeds non-Rust files with `include_str!`, the internal Buck build needs `extra_srcs = ["plugin.json", "skills/**"]` in `fbcode/musecode/fixups/<crate-name>/fixups.toml` — Reindeer stages only `*.rs` otherwise). | `name`, `placement.kind` (`project` / `plugin`), `placement.plugin_id`, `connect_words` (a list) |

## Cards versus text

A finite choice (questions 2 and 8, and the final confirm) is a card with
buttons or a `static_select` when the connector that delivered this
conversation renders cards — the Slack connector's `references/slack-ui.md`
(named in your starter) has the shapes; the click comes back as one line
(`<lane> <user> [ui]: <action> (button) = <value>`) and your next call
answers it. On a lane that cannot render a card (`ui_needs_relay_lane`, or a
connector whose `status --json` says `cards: false`) the same choice is a
numbered text list and the human answers with the number or the word. Free
text questions are plain `reply --text`.

The same `status --json` is the connector's status contract, read by the
daemon's `start` on every restart: `sources_available` (every `--source` word
`listen` honours; a recorded row whose word is missing is reported `stale`,
never armed) and `listeners` with one record per source word beside the
`<source>|<filter>` subscription keys; a record whose last listener ended
non-zero carries `exit` and `ended_at` (the daemon's `start` records the
failure from them without a model call) until a new listener starts on it.

## The redirect (question 2)

When a connector already in the catalog lists the source the human named —
the general event-stream connector's SKILL states its sources; read the
catalog descriptions, never a keyword table — do not build. Say which
connector carries it and hand back its connect words:

```
python3 <scaffold> scaffold --connector <name> --delivery stream --answers <file> --root <workspace root>
→ {"outcome":"redirect","connector":"<id>","source":"<source>","connect":"/daemon connect <id> <source>","written":[]}
```

Nothing is written. The human connects with those words in the daemon's
thread (`/daemon connect <id> <source>`).

## Summary and confirm

After question 8 post ONE summary — every answer on its own line (a card's
`fields` section or a numbered list) — and ask for the confirm ("Build it?"
with Yes / Change an answer / Stop). Only a Yes runs the scaffold. "Change an
answer" re-asks that one question and re-posts the summary. Stop, cancel, or
"never mind" at any point — before or after the summary — ends the task with
nothing on disk: one line back, and no scaffold call.

## The answers file

Write the answers as one JSON object with the keys above (nested by the dot:
`{"source": {"name": …, "word": …}, "poll": {"command": …}, …}`) to a file in
the workspace's temp dir, pass it as `--answers <file>`, and delete it after
the scaffold: the scaffold copies it into the connector's `tests/answers.json`,
which is the durable record the `TODO(answer …)` markers cite.

Worked example (poll, project skill):

```json
{"source": {"name": "the events CLI", "word": "events", "summary": "a local CLI that prints one JSON line per event."},
 "delivery": "poll",
 "poll": {"command": "./events.sh --since {cursor}", "output": "json lines: id, sender, text, conversation", "interval_s": 2},
 "auth": {"identity": "the local user", "env": ["EVENTS_TOKEN"]},
 "conversation": {"unit": "one ticket", "id_rule": "the ticket id the CLI prints"},
 "reply": {"command": "./events.sh reply {conversation} {text}", "markdown": false},
 "filters": {"default": "mention", "meaning": "the text contains @muse"},
 "gate": {"experimental_tag": true},
 "name": "events-connector", "placement": {"kind": "project"},
 "connect_words": ["connect events", "watch the events CLI"]}
```
