# Slack connector reference: interactive cards over the mailbox

Read this when you want a rich reply — a plan, a decision, controls, a
result — on a lane the Muse Tag relay originated. The `reply` bullet in
`SKILL.md` is the contract; this file is the Slack-to-mailbox delta, six
complete examples, and the behaviour that makes a card worth posting.
The examples are guidance, not templates (ADR 35345 D3): compose whatever
Slack message Block Kit expresses the work; nothing here is a catalog to pick
from, and the connector never reads meaning into an `action_id`.

## Read this first (a coordinator lane)

These are the Slack-specific rules a delegated coordinator works under;
the daemon's starter and handoff point here instead of teaching them (ADR
37480 D1: markup, cards and attachments are this connector's own words).

- Read this one file once, before your first status, result or list reply
  in this lane and whenever a card is called for (a decision calls for one;
  a status or a list earns one too) — never `slack_connector.py`,
  `slack_ui.py`, a `SKILL.md` or `--help`.
- Your replies go to the requester in Slack: markdown renders, code in a
  ``` fence, links as `[label](url)`; the text never carries a lane id or a
  template word. Over two facts, or a list: a card.
- A checklist item is the glyph pair ☐ / ✅ at line start (⏳ for a step
  running in the background): Slack strips markdown `- [ ]` / `- [x]` task
  lists, so an edit that used them showed no progress.
- A Slack card (buttons, Approve/Cancel, a choice, a result with controls)
  is ONE call, `reply --to <lane> --message-json -` with `{"text": …,
  "blocks": […]}` on stdin; `reply --to <lane> --replace-last --message-json
  -` edits that card and needs no id or revision from you (the connector
  holds them); a click arrives as one line, `<lane> <user> [ui]: <action>
  (button) = <value>`, and your next call answers it.
- A yes/no or bounded decision you need from the requester (delete this?
  which of these? approve?) is a card with buttons whether or not they said
  card: prose ending "want me to?" leaves them typing; a card gives them a
  tap. A status, result, list or choice is a rich card when it has more than
  a sentence of structure, plain text for one-liners — "Choose the richest
  layout the message earns" below says which block fits which content: a
  status or result with more than two facts is a header, a `fields` section
  of label/value pairs and one context line, never paragraphs or a code
  fence; a list of files, steps or findings is a `rich_text_list` (a `table`
  when the items have columns), never dash bullets; command output and paths
  are `rich_text_preformatted`.
- When a card will carry the steps, the card IS the plan: arm without
  `--say` and post the card first, never a `*Plan*` list and a card for one
  job. A mailbox lane the relay did not originate refuses `--message-json`
  (`ui_needs_relay_lane`): reply there with `--text`. A Slack-direct lane
  (`slack-connector:slack`) has no `--message-json` and no `--attach`.
- Every `reply` line on a relay lane carries `cards`: `yes (version 2: early
  reply at the tap)` — the relay renders a pick's summary and a press's
  `✅ … working…` at the tap, before your turn; `yes (version 1)` — the card
  renders, taps reach you, nothing moves until you answer; `no — text and
  files only` (a Slack-direct lane: `no — text only`; a relay the
  connect-time listing did not name: `unverified …` — a card goes out as
  version 1 and its `[ui]` line tells). It is the connector's reading of
  the relay (the probe at
  connect, corrected by the relay's own answers), never your guess: do not
  tell the requester a lane has no buttons unless it says `cards: no`. With
  `cards: yes`, a choice, a confirmation, a plan approval or a status with
  actions goes out as a card — buttons, a `static_select`, a form with a
  submit; a numbered text menu is only for `cards: no`; a text plan on a
  card lane is edited with `--replace-last`, never re-posted.
- After a relaunch the card is still this lane's live card: the same
  `--replace-last` edits it, no status, state, log or script read first;
  derive its state from the clicks already answered (an answered Approve
  means that step ran), never move a card backwards, and if unsure say so in
  the update. The bracketed `[card rev N, after …]` prefix on an `Already
  sent` line is provenance for you, never part of the text you send.
- Attach your result when a file is easier for them to read or view than
  chat text — a generated file, an image or chart, CSV/JSON, a log or diff
  over ~40 lines, a whole script, text past ~3,000 characters — via
  `--attach <path>` on the SAME reply as your summary, one file each, never
  alone; a 20-line snippet, a command or a conclusion stays inline.

## The delta from Slack's API

You already know `chat.postMessage` and `chat.update`. On a mailbox lane the
same content goes through `reply`, and the connector supplies every identity
Slack would have asked you for:

```text
chat.postMessage(text, blocks)
  -> python3 <connector-script> reply --to <lane> --message-json -

chat.update(channel, ts, text, blocks)
  -> python3 <connector-script> reply --to <lane> --replace-last --message-json -
     (addresses the lane's LIVE card by the connector-held ui_id and
     expected_revision — its most recent presentation that is still live,
     whatever plain replies you sent since; a card that fell back to text,
     expired, or whose conflicting update reported no revision no longer
     counts; after a conflict that reports a revision the card is still live
     at that revision — update it again)

Slack interaction callback
  <- one inbound line in the lane, printed by your listener:
     <lane> <actor_slack_id> [ui]: <action_id> (<action_type>) = <values joined by ", ">
     followed by ` · state <key>=<v1,v2,…>` per non-empty state key;
     an empty values writes `= -`
```

The inbound grammar is spec 23499 FR-35345-4(c)/(f). The object you write is
`{"text": ..., "blocks": [...]}` plus, on a post only, any of
`expires_in_seconds`, `single_use`, `on_invalid`, `option_sources` and, on a
relay that speaks version 2, `behavior` ("When a button is tapped" below). `text` is
mandatory and must stand alone: it is the notification, the screen-reader
copy, and the whole message when the relay cannot render the blocks
(`on_invalid: fallback`, the default). An update accepts `text`, `blocks`
and `option_sources` only; the card keeps the expiry and single-use policy
it was posted with.

## Six complete examples

Each is one tool call. `c3` stands for the lane in your listener's line.
Match the depth to the ask. A card, a progress line or a click receipt is
short because the reader is deciding or glancing. A design, plan, review or
analysis the requester asked for IS the deliverable and gets the depth the
problem needs — goal, what you found, options and trade-offs,
recommendation, risks, steps — split across consecutive messages when
Slack's length forces it, the card then carrying only the decision. mrkdwn
has no headings: `## Goal` renders as pound signs, and its bold is `*single
asterisks*` (`**double**` renders literally there; a plain `reply --text` is
Markdown, where `**double**` is bold). `text` carries the whole ask. The
buttons are the ask — do not also write `reply Approve`. An update repeats
the shape with what changed.

### 1. A living plan or checklist

Post this once the approach is known, before the first long step, so the
requester sees the shape of the work instead of silence. If the requester
asked for a card, or your first step is their decision, the card IS the
plan: arm without `--say` and make the card your first outbound, with the
☐/✅ steps in its section block and every milestone an update of it. A
separate `*Plan*` message is for work no card will carry; never both lists
for one job. Update it in place (`--replace-last --message-json -`) at each
milestone — tick the step, move the context line — never once per tool call.
When a step will run longer than about 20 s in the background, mark it
running (⏳ at line start, or _running…_) in an update before you start it,
so the requester sees progress without a timer; the update after it turns
that step ✅.

```bash
python3 <connector-script> reply --to c3 --message-json - <<'MSG'
{
  "text": "Plan for #35345 lane D: 1/4 done — vendoring schema (done), writing RED tests (in progress), implementing slack_ui.py, running the suite.",
  "blocks": [
    {"type": "header", "text": {"type": "plain_text", "text": "Plan: slack_ui contract module", "emoji": false}},
    {"type": "section", "text": {"type": "mrkdwn", "text": "*Lane D of #35345* — pure contract module for `custom.slack.ui` v1."}},
    {"type": "divider"},
    {"type": "section", "text": {"type": "mrkdwn", "text": "☑ Vendor the v1 schema snapshot\n☐ Write the RED contract tests _(in progress)_\n☐ Implement `slack_ui.py`\n☐ Run the connector suite and open the PR"}},
    {"type": "context", "elements": [
      {"type": "mrkdwn", "text": "Step 2 of 4 · I will update this card at each milestone, not per tool call."}
    ]}
  ]
}
MSG
```

### 2. An approval or bounded choice

Post this for any yes/no or bounded decision you need from the requester —
delete this? which of these? approve? — whether or not they said "card":
prose ending "want me to?" leaves them typing; a card gives them a tap. It
is also the shape when product policy says a human must decide and the
choices are few and nameable; `single_use` retires the buttons after the
first press and
`expires_in_seconds` bounds how long the question stands. When the click
line arrives, your next call answers it: if the approved step finishes
within one call (under about a minute), do the work and send ONE update
that shows the outcome and drops the buttons (example 6); if it runs
longer, first update the card to show the decision was received and what
starts now (`✅ Approved — running step 2…`), then update again with the
result. A click you will not act on — a repeat, a stale one, one the policy
refuses — still gets that update or one plain line saying so; silence after
a tap is never right. An update only moves forward: a ✅ never returns to
☐, the header stays, and controls you removed stay removed; while a step is
running keep Cancel if cancelling is still possible. After a relaunch the
card the requester sees is its newest revision, not the post text quoted in
your prompt: derive its state from the clicks already answered (an answered
Approve means that step ran) and, if unsure, say so in the update rather
than guessing lower. If the card expires unanswered, say so in a plain
reply.

```bash
python3 <connector-script> reply --to c3 --message-json - <<'MSG'
{
  "text": "Decision needed: apply the migration to the production database now, or wait for the maintenance window? Reply approve / wait / reject.",
  "blocks": [
    {"type": "header", "text": {"type": "plain_text", "text": "Approval needed: production migration"}},
    {"type": "section", "text": {"type": "mrkdwn", "text": "The migration `2026_09_14_add_ui_records` is ready. It rewrites *2 tables* and takes about 40 s with a table lock.\n\n*Options*\n• *Apply now* — users see a 40 s write pause.\n• *Wait* — I will re-ask at the 22:00 maintenance window.\n• *Reject* — I stop and summarise what is left."}},
    {"type": "actions", "block_id": "migration_decision", "elements": [
      {"type": "button", "action_id": "approve", "style": "primary", "text": {"type": "plain_text", "text": "Apply now"}, "value": "apply_now",
       "confirm": {"title": {"type": "plain_text", "text": "Apply the migration now?"}, "text": {"type": "mrkdwn", "text": "Writes pause for about 40 s while the tables are rewritten."}, "confirm": {"type": "plain_text", "text": "Apply"}, "deny": {"type": "plain_text", "text": "Back"}}},
      {"type": "button", "action_id": "wait", "text": {"type": "plain_text", "text": "Wait for the window"}, "value": "wait"},
      {"type": "button", "action_id": "reject", "style": "danger", "text": {"type": "plain_text", "text": "Reject"}, "value": "reject"}
    ]}
  ],
  "single_use": true,
  "expires_in_seconds": 7200
}
MSG
```

### 3. Steering and cancellation

Post this at the start of a long run the requester may want to narrow or
stop; the select carries the options, the button the escape. Update it as
the run advances (elapsed, crates green) and, when it ends or a control is
used, replace the controls with what happened.

```bash
python3 <connector-script> reply --to c3 --message-json - <<'MSG'
{
  "text": "Running the full test suite (about 12 min). You can narrow the run to one crate or cancel it.",
  "blocks": [
    {"type": "section", "text": {"type": "mrkdwn", "text": "*Running:* full workspace test suite\n*Elapsed:* 3 min · *Estimate:* 12 min\n*So far:* 4 of 11 crates green"}},
    {"type": "actions", "block_id": "steer", "elements": [
      {"type": "static_select", "action_id": "narrow_to_crate", "placeholder": {"type": "plain_text", "text": "Narrow to one crate"},
       "options": [
         {"text": {"type": "plain_text", "text": "tbh-agent"}, "value": "tbh-agent"},
         {"text": {"type": "plain_text", "text": "tbh-cli"}, "value": "tbh-cli"},
         {"text": {"type": "plain_text", "text": "tbh-tui"}, "value": "tbh-tui"}
       ]},
      {"type": "button", "action_id": "cancel", "style": "danger", "text": {"type": "plain_text", "text": "Cancel run"}, "value": "cancel"}
    ]},
    {"type": "context", "elements": [{"type": "plain_text", "text": "Cancelling stops the run after the current crate finishes.", "emoji": false}]}
  ]
}
MSG
```

### 4. Needs attention

Post this the moment progress depends on the human — a missing grant, a
choice you cannot make — rather than waiting silently; state what is done,
what is blocked, and the two or three ways forward. After the click (or a
typed answer), update the card to say how it was unblocked and remove the
buttons.

```bash
python3 <connector-script> reply --to c3 --message-json - <<'MSG'
{
  "text": "Blocked: the deploy step needs the STAGING_DEPLOY_KEY secret, which I cannot read. Grant it or tell me to skip the deploy.",
  "blocks": [
    {"type": "header", "text": {"type": "plain_text", "text": "Needs your attention"}},
    {"type": "section", "text": {"type": "mrkdwn", "text": ":warning: *Blocked on a secret*\nThe deploy step reads `STAGING_DEPLOY_KEY` from the secret store and the ACL denies this agent. Everything before the deploy is done and pushed."}},
    {"type": "section", "fields": [
      {"type": "mrkdwn", "text": "*Branch*\n`feat/35345-D`"},
      {"type": "mrkdwn", "text": "*Waiting since*\n14:02"}
    ]},
    {"type": "actions", "block_id": "attention", "elements": [
      {"type": "button", "action_id": "retry_deploy", "style": "primary", "text": {"type": "plain_text", "text": "I granted it — retry"}, "value": "retry"},
      {"type": "button", "action_id": "skip_deploy", "text": {"type": "plain_text", "text": "Skip the deploy"}, "value": "skip"}
    ]}
  ]
}
MSG
```

### 5. A completed or failed result

Post this as the final word on a piece of work when a plain sentence would
bury the numbers: what landed, what failed, whether anything is still owed.
It carries no controls, so it needs no further update; a later change is a
new post or a plain reply.

```bash
python3 <connector-script> reply --to c3 --message-json - <<'MSG'
{
  "text": "Done: PR #35400 opened (3 files, +412/-0). CI: 5 of 6 checks passed; `clippy` failed on one unused import — fixed in a follow-up push.",
  "blocks": [
    {"type": "header", "text": {"type": "plain_text", "text": "Completed with one failure"}},
    {"type": "section", "text": {"type": "mrkdwn", "text": ":white_check_mark: Opened <https://github.com/mslsrc/tbh/pull/35400|PR #35400> — `slack_ui` contract module.\n:x: `clippy` failed on the first CI round (one unused import); the fix is pushed and CI is re-running."}},
    {"type": "section", "fields": [
      {"type": "mrkdwn", "text": "*Files*\n3 changed, +412 / -0"},
      {"type": "mrkdwn", "text": "*Checks*\n5 passed · 1 failed · rerun in progress"}
    ]},
    {"type": "context", "elements": [{"type": "mrkdwn", "text": "No further action needed from you; I will report the rerun result."}]}
  ]
}
MSG
```

### 6. Updating an existing card (the terminal update)

Send this after the click line for example 2 arrived and the work it
authorised is done: the same header, the decision and its actor recorded,
and no `actions` block, so stale buttons cannot be pressed twice. Only
`text`, `blocks` and `option_sources` are accepted here; the card's expiry
and single-use policy stay as posted.

```bash
python3 <connector-script> reply --to c3 --replace-last --message-json - <<'MSG'
{
  "text": "Decision recorded: apply now (chosen by <@U0123ABCD>). Migration applied in 38 s; controls removed.",
  "blocks": [
    {"type": "header", "text": {"type": "plain_text", "text": "Approval needed: production migration"}},
    {"type": "section", "text": {"type": "mrkdwn", "text": ":white_check_mark: *Apply now* — chosen by <@U0123ABCD> at 14:07.\nMigration `2026_09_14_add_ui_records` applied in 38 s; writes resumed."}},
    {"type": "context", "elements": [{"type": "mrkdwn", "text": "This decision is closed; the buttons were removed."}]}
  ]
}
MSG
```

## Choose the richest layout the message earns

Block Kit is not only for decisions. Read what the message carries before
you choose its shape, and give it the richest layout that content earns —
the relay renders every block family below, and a reader on a phone scans a
card faster than a paragraph. A status or result with more than two facts
is a header, a `fields` section of label/value pairs and one context line,
not a paragraph the reader has to parse. A list of files, steps or findings
is a `rich_text_list` — a `table` when the items have columns — never a wall
of dashes in mrkdwn. Command output, paths and error text go in
`rich_text_preformatted`, where wrapping and quoting cannot mangle them. A
choice among three to eight named options is a `static_select` (or
`radio_buttons` when the labels should be read side by side) in an actions
block; two or three are buttons; more than eight is a numbered list and a
typed answer; when several of the options may apply at once, the control is
`checkboxes` with a Submit button (example 10), never a select. A decision
the human must make keeps buttons whatever else the card carries. Provenance — who, when, where — is a context line, not a
sentence. Plain `reply --text` stays right for a one-line answer, an
acknowledgement or a conversational reply: a card around one sentence is
noise. The depth still follows the ask ("Match the depth to the ask" above);
this chooses the layout for that depth, never more words.

What the relay accepts, so you compose freely without reading the schema:
`header`, `section` (`text` or `fields`, plus one `accessory` — a button,
a select, a `multi_static_select`, an overflow or an image), `context`,
`divider`, `actions` (`button`, `static_select`, `overflow`, `checkboxes`,
`radio_buttons`, `datepicker`; never a multi-select there — it is a section
accessory), `image`, `rich_text` (`rich_text_section`, `rich_text_list`,
`rich_text_preformatted`, `rich_text_quote`) and `table`, within the 16 KiB
serialized size and 16-level nesting bounds. Both examples below serialize
to under 2 KiB, well under the 16 KiB bound. A click on a select arrives exactly like a button
press, with the element's type in the parentheses and the chosen option's
`value` after `=`.

### 7. A result or status card

Post this when the result has more than two facts — what ran, what it
found, what is left — instead of a paragraph. The `fields` carry the
numbers, the preformatted block carries the one thing the reader may copy
(a path, an error, a command), and the context line says where and when.
No controls, so no update follows.

```bash
python3 <connector-script> reply --to c3 --message-json - <<'MSG'
{
  "text": "Suite green on 3 crates after the fix: 212 passed, 0 failed, 2 ignored in 4 min 10 s; one warning left in tbh-cli (unused import std::fmt::Write at crates/tbh-cli/src/render.rs:14).",
  "blocks": [
    {"type": "header", "text": {"type": "plain_text", "text": "Result: suite green after the fix"}},
    {"type": "section", "fields": [
      {"type": "mrkdwn", "text": "*Crates*\n`tbh-agent`, `tbh-cli`, `tbh-tui`"},
      {"type": "mrkdwn", "text": "*Tests*\n212 passed · 0 failed · 2 ignored"},
      {"type": "mrkdwn", "text": "*Wall time*\n4 min 10 s"},
      {"type": "mrkdwn", "text": "*Left over*\n1 warning in `tbh-cli`"}
    ]},
    {"type": "rich_text", "elements": [
      {"type": "rich_text_section", "elements": [{"type": "text", "text": "The warning, verbatim:"}]},
      {"type": "rich_text_preformatted", "elements": [{"type": "text", "text": "warning: unused import: `std::fmt::Write`\n  --> crates/tbh-cli/src/render.rs:14:5"}]}
    ]},
    {"type": "context", "elements": [{"type": "mrkdwn", "text": "Run on `fix/render-wrap` at `a1b2c3d`, 14:32 UTC, in this workspace · nothing else changed."}]}
  ]
}
MSG
```

### 8. An option picker

Post this when the requester has to pick one of several named things — an
environment, a file, a name — and there are more than a pair of buttons'
worth. When more than one may apply, post example 10's checkboxes instead.
The select holds the options with a short description each; the section
says what the pick does. The click arrives as
`c3 U0456 [ui]: pick_target (static_select) = staging-eu` and your next
call answers it: update the card so the select is gone and the pick is
recorded (example 6's shape), then start the work.

```bash
python3 <connector-script> reply --to c3 --message-json - <<'MSG'
{
  "text": "Which environment should the smoke run against: dev, staging-eu, staging-us, canary or prod-mirror? Pick one; reply with the name if the picker does not render.",
  "blocks": [
    {"type": "section", "text": {"type": "mrkdwn", "text": "*Where should the smoke run?*\nThe build is green and the smoke takes about 3 min against any of these. `prod-mirror` is a read-only copy; `canary` carries 1 % of live traffic."}},
    {"type": "actions", "block_id": "smoke_target", "elements": [
      {"type": "static_select", "action_id": "pick_target", "placeholder": {"type": "plain_text", "text": "Choose an environment"},
       "options": [
         {"text": {"type": "plain_text", "text": "dev"}, "value": "dev", "description": {"type": "plain_text", "text": "shared dev cluster"}},
         {"text": {"type": "plain_text", "text": "staging-eu"}, "value": "staging-eu", "description": {"type": "plain_text", "text": "closest to the reporter"}},
         {"text": {"type": "plain_text", "text": "staging-us"}, "value": "staging-us"},
         {"text": {"type": "plain_text", "text": "canary"}, "value": "canary", "description": {"type": "plain_text", "text": "1 % of live traffic"}},
         {"text": {"type": "plain_text", "text": "prod-mirror"}, "value": "prod-mirror", "description": {"type": "plain_text", "text": "read-only copy of prod"}}
       ]}
    ]},
    {"type": "context", "elements": [{"type": "plain_text", "text": "One pick starts the smoke; I will report the result on this card.", "emoji": false}]}
  ],
  "single_use": true,
  "expires_in_seconds": 3600
}
MSG
```

## When to post, when to update, when to stay quiet

ADR 35345 D3 and D7 (as amended), in your terms:

- The daemon already posted its one-sentence acknowledgement when it handed
  you the task; on a bounded question it answers at once — the relay's
  working indicator covers that wait. Never post a second "received" or
  "working" line: your first message is substance.
- Short work — one step, under about a minute: do it and send the result, a
  plain `--text` reply or a card like example 5.
- Longer work: post the plan (example 1) once the approach is known, then
  update that same card at meaningful milestones. Your first message lands
  within about a minute of the daemon's acknowledgement — the card if it is
  ready, otherwise a one-line status of what you are looking at. Compose
  from the examples here; do not open `slack_ui.py`, `slack_connector.py`
  or the schema to learn the grammar — the relay's result line tells you if
  a shape is unsupported. Do not narrate tool calls and do not post a new
  status message when an update would do; a click is not a milestone by
  itself (example 2). A plain
  `--text` answer in between does not orphan the card: the next
  `--replace-last --message-json -` still addresses the lane's live card,
  while `--replace-last --text` edits the last plain message.
- Blocked, urgent, or genuinely in need of a decision: post attention
  (example 4) or a bounded choice (example 2) now, not at the end.
- Terminal update first, then the result: when a card with controls is
  finished — decided or cancelled — update it so the controls are gone and
  the outcome is on the card (example 6), then send the final concise
  result. Never leave live buttons on a closed question. An expired card
  needs no update: the relay already removed its controls; say what
  happened in a plain reply. The result never describes the card (`the card
  above is closed, buttons removed`) — they can see it; say what stands,
  what was not done, and what stayed (a branch, a worktree, a PR) as a
  statement — never a closing question; the requester decides.
- Every post has a `text` that carries the whole ask in one or two
  sentences — the items and the choice — because it is the phone
  notification and, on `fallback_sent`, all the requester sees: `Approve to
  archive lane.sh: 1) copy to archive/ with sha256, 2) verify, 3) remove the
  original — reply approve or cancel`, never a title such as `Checklist —
  approve to proceed` or `see above`.

## When a button is tapped

On a relay that speaks `custom.slack.ui` version 2 (both of the owner's
relays do), a card with controls reacts by itself: the moment the requester
taps, the relay removes the controls and adds one line under the card —
`✅ <button label> · working…` — with no turn of yours; the header and the
question stay as they were, shown once. You still get the click line as
before (`c3 U0456 [ui]: approve (button) = apply_now`), and your next reply
in the lane — plain `--text` or a card — settles it: the card's line becomes
`✅ <button label>` and your reply lands below it. A card with controls is
therefore a decision that ends at the tap, not a message you edit:
`--replace-last --message-json -` on it posts your new blocks as a new card
while the tap is unsettled (the `pending` line says so in `note`); once
your plain reply settled it, `--replace-last` is refused
`no_live_presentation` — post the next card without the flag. Rolling
progress belongs in plain replies or in a controls-free card, which
`--replace-last --message-json -` still edits in place. Nothing changes
for a card without controls, and nothing changes on a relay that speaks
only version 1. A long card is not refused for its early-reply views: a
press's view is that one line whatever the card's length, and when a form's
pick summaries (each a copy of the form) would push the request past the
relay's 65,536 bytes, the connector lets the controls of one row share a
view and, past that, posts the card as version 1 — a `slack-connector:
custom.slack.ui version 2: …` line on stderr says which; every card the
version 1 path carries still goes out.

Want the card to change in richer ways — pages, a toggle, a selection
summary, your own "approved" / "rejected" views? Declare the behavior
yourself, as a fifth member of the post: `"behavior": {"runtime":
"declarative-v1", "templates": {"approved": {"text": "…", "blocks": […]},
"detail": {…}}, "on_action": {"approve": {"kind": "business_submission",
"show_template": "approved"}, "more": {"kind": "presentation", "transition":
"toggle", "state_key": "more", "show_template": "detail",
"alternate_template": "approved"}}}`. Every control has an entry; templates
are display-only (no controls) and at most 16. A `business_submission` shows
its template at the tap and waits for your reply; the relay ADDS that
template under the card (controls removed) rather than replacing it, so
make it a status line — one `context` block — and never repeat the header
or the question, or the requester reads them twice. A `presentation` (a
page, toggle or selection summary) replaces the card's view and is handled
by the relay entirely; it reaches you as a click line ending ` ·
presentation` — no answer owed. A tick on `checkboxes` or a multi-select is
a presentation with no view and no line: the card does not change (Slack
keeps the ticks), the connector holds the tick, and the Submit press's
`state` carries the set (example 10). When your
reply's `blocks` equal one of your templates, the card becomes that template
and nothing else is posted; otherwise the relay shows its own settled view
and your reply follows below. A relay that speaks only version 1 refuses
`behavior` (nothing sent): drop it and post as before.

### 9. A form that answers every interaction itself

Rule of thumb: design the card so the relay answers every interaction at
once; you answer only the final submission. Here a pick shows a summary line
(`{{selection}}` is filled by the relay), a typed note is acknowledged the
same way, and only Approve / Cancel reach you as a click line to settle. The
`deployed` template is what your final reply becomes when its `blocks` equal
it; any other reply lands below the settled card.

```bash
python3 <connector-script> reply --to c3 --message-json - <<'MSG'
{
  "text": "Deploy form: pick the environment, add a note if you like, then Approve or Cancel. Reply with the environment name if the form does not render.",
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "Deploy build 4812"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "Pick the environment and, if useful, leave a note; *Approve* starts the deploy."
      },
      "accessory": {
        "type": "static_select",
        "action_id": "env",
        "placeholder": {
          "type": "plain_text",
          "text": "Environment"
        },
        "options": [
          {
            "text": {
              "type": "plain_text",
              "text": "staging"
            },
            "value": "staging"
          },
          {
            "text": {
              "type": "plain_text",
              "text": "canary"
            },
            "value": "canary"
          },
          {
            "text": {
              "type": "plain_text",
              "text": "prod"
            },
            "value": "prod"
          }
        ]
      }
    },
    {
      "type": "input",
      "block_id": "note",
      "dispatch_action": true,
      "label": {
        "type": "plain_text",
        "text": "Note for the deploy log"
      },
      "element": {
        "type": "plain_text_input",
        "action_id": "note_text",
        "placeholder": {
          "type": "plain_text",
          "text": "optional"
        }
      }
    },
    {
      "type": "actions",
      "block_id": "decide",
      "elements": [
        {
          "type": "button",
          "action_id": "approve",
          "style": "primary",
          "value": "approve",
          "text": {
            "type": "plain_text",
            "text": "Approve"
          }
        },
        {
          "type": "button",
          "action_id": "cancel",
          "style": "danger",
          "value": "cancel",
          "text": {
            "type": "plain_text",
            "text": "Cancel"
          }
        }
      ]
    }
  ],
  "behavior": {
    "runtime": "declarative-v1",
    "templates": {
      "picked": {
        "text": "Environment: {{selection}}",
        "blocks": [
          {
            "type": "header",
            "text": {
              "type": "plain_text",
              "text": "Deploy build 4812"
            }
          },
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "Pick the environment and, if useful, leave a note; *Approve* starts the deploy."
            },
            "accessory": {
              "type": "static_select",
              "action_id": "env",
              "placeholder": {
                "type": "plain_text",
                "text": "Environment"
              },
              "options": [
                {
                  "text": {
                    "type": "plain_text",
                    "text": "staging"
                  },
                  "value": "staging"
                },
                {
                  "text": {
                    "type": "plain_text",
                    "text": "canary"
                  },
                  "value": "canary"
                },
                {
                  "text": {
                    "type": "plain_text",
                    "text": "prod"
                  },
                  "value": "prod"
                }
              ]
            }
          },
          {
            "type": "context",
            "elements": [
              {
                "type": "plain_text",
                "text": "Environment: {{selection}}",
                "emoji": false
              }
            ]
          },
          {
            "type": "input",
            "block_id": "note",
            "dispatch_action": true,
            "label": {
              "type": "plain_text",
              "text": "Note for the deploy log"
            },
            "element": {
              "type": "plain_text_input",
              "action_id": "note_text",
              "placeholder": {
                "type": "plain_text",
                "text": "optional"
              }
            }
          },
          {
            "type": "actions",
            "block_id": "decide",
            "elements": [
              {
                "type": "button",
                "action_id": "approve",
                "style": "primary",
                "value": "approve",
                "text": {
                  "type": "plain_text",
                  "text": "Approve"
                }
              },
              {
                "type": "button",
                "action_id": "cancel",
                "style": "danger",
                "value": "cancel",
                "text": {
                  "type": "plain_text",
                  "text": "Cancel"
                }
              }
            ]
          }
        ]
      },
      "noted": {
        "text": "Note received: {{selection}}",
        "blocks": [
          {
            "type": "header",
            "text": {
              "type": "plain_text",
              "text": "Deploy build 4812"
            }
          },
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "Pick the environment and, if useful, leave a note; *Approve* starts the deploy."
            },
            "accessory": {
              "type": "static_select",
              "action_id": "env",
              "placeholder": {
                "type": "plain_text",
                "text": "Environment"
              },
              "options": [
                {
                  "text": {
                    "type": "plain_text",
                    "text": "staging"
                  },
                  "value": "staging"
                },
                {
                  "text": {
                    "type": "plain_text",
                    "text": "canary"
                  },
                  "value": "canary"
                },
                {
                  "text": {
                    "type": "plain_text",
                    "text": "prod"
                  },
                  "value": "prod"
                }
              ]
            }
          },
          {
            "type": "input",
            "block_id": "note",
            "dispatch_action": true,
            "label": {
              "type": "plain_text",
              "text": "Note for the deploy log"
            },
            "element": {
              "type": "plain_text_input",
              "action_id": "note_text",
              "placeholder": {
                "type": "plain_text",
                "text": "optional"
              }
            }
          },
          {
            "type": "context",
            "elements": [
              {
                "type": "plain_text",
                "text": "Note received: {{selection}}",
                "emoji": false
              }
            ]
          },
          {
            "type": "actions",
            "block_id": "decide",
            "elements": [
              {
                "type": "button",
                "action_id": "approve",
                "style": "primary",
                "value": "approve",
                "text": {
                  "type": "plain_text",
                  "text": "Approve"
                }
              },
              {
                "type": "button",
                "action_id": "cancel",
                "style": "danger",
                "value": "cancel",
                "text": {
                  "type": "plain_text",
                  "text": "Cancel"
                }
              }
            ]
          }
        ]
      },
      "approving": {
        "text": "✅ Approve · deploying…",
        "blocks": [
          {
            "type": "context",
            "elements": [
              {
                "type": "plain_text",
                "text": "✅ Approve · deploying…",
                "emoji": false
              }
            ]
          }
        ]
      },
      "cancelled": {
        "text": "Cancelled — nothing deployed.",
        "blocks": [
          {
            "type": "context",
            "elements": [
              {
                "type": "plain_text",
                "text": "Cancelled — nothing deployed.",
                "emoji": false
              }
            ]
          }
        ]
      },
      "deployed": {
        "text": "✅ Deployed.",
        "blocks": [
          {
            "type": "context",
            "elements": [
              {
                "type": "plain_text",
                "text": "✅ Deployed.",
                "emoji": false
              }
            ]
          }
        ]
      }
    },
    "on_action": {
      "env": {
        "kind": "presentation",
        "transition": "selection_summary",
        "state_key": "env",
        "show_template": "picked"
      },
      "note_text": {
        "kind": "presentation",
        "transition": "selection_summary",
        "state_key": "note_text",
        "show_template": "noted"
      },
      "approve": {
        "kind": "business_submission",
        "show_template": "approving"
      },
      "cancel": {
        "kind": "business_submission",
        "show_template": "cancelled"
      }
    }
  }
}
MSG
```

### 10. A question with several answers

Not every question has one right answer. When the requester may want
several of the named things at once — which checks to run, which files to
include, which environments to deploy to — a select is the wrong control
(it takes one), and a numbered list of combinations (`1. tests + lint, 2.
tests only …`) is worse: it leaves them typing. A card can be submitted
once, so a multi-pick is tick, then Submit: post `checkboxes` in an actions
block with exactly one Submit button beside them; a `multi_static_select`
as a section accessory is the same shape as a dropdown, for a long or
long-labelled list, and its events arrive the same way with
`multi_static_select` in the parentheses. A tick changes nothing on the
card — Slack keeps the boxes ticked and the relay renders no view for it —
and nothing reaches you: ticks are silent to the coordinator (the connector
holds them; its own log notes each one), because a half-made selection is
not an answer and a line per tick would have you act on it. Submit is the
one event you see, and the only submission the card takes:
`c3 U0456 [ui]: submit (button) = submit · state checks=dry_run,lint` —
read the answer from that `state` clause (the option `value`s, never the
labels; every box ticked at the press); no `state` clause means nothing
was ticked. At the press the relay
drops the controls and adds `✅ Submit · working…` under the card; your next
call answers the press and names the set — `Noted: dry run and lint.` when
you are only recording it; `Running dry run and lint; results here in about
3 min.` only when that same turn then runs them (a coordinator that posted
the running line and ran nothing left the requester waiting); the result
card when they already ran — and the line becomes `✅ Submit`. A single-answer question stays buttons or a select
(examples 2 and 8). On a relay that speaks only version 1 the ticks are
held the same way; the answer is still the Submit press and its `state`
clause.

```bash
python3 <connector-script> reply --to c3 --message-json - <<'MSG'
{
  "text": "Which checks should run before the merge: dry run, lint, unit tests, integration tests? Tick any number, then Submit; reply with the names if the boxes do not render.",
  "blocks": [
    {"type": "header", "text": {"type": "plain_text", "text": "Pre-merge checks"}},
    {"type": "section", "text": {"type": "mrkdwn", "text": "The branch is rebased and builds. Tick every check you want before I merge — several are fine — then *Submit*. Unit tests take about 4 min, integration about 12."}},
    {"type": "actions", "block_id": "checks_row", "elements": [
      {"type": "checkboxes", "action_id": "checks", "options": [
        {"text": {"type": "plain_text", "text": "Dry run"}, "value": "dry_run", "description": {"type": "plain_text", "text": "plan only, nothing written"}},
        {"text": {"type": "plain_text", "text": "Lint"}, "value": "lint"},
        {"text": {"type": "plain_text", "text": "Unit tests"}, "value": "unit", "description": {"type": "plain_text", "text": "about 4 min"}},
        {"text": {"type": "plain_text", "text": "Integration tests"}, "value": "integration", "description": {"type": "plain_text", "text": "about 12 min, needs the staging database"}}
      ]},
      {"type": "button", "action_id": "submit", "style": "primary", "text": {"type": "plain_text", "text": "Submit"}, "value": "submit"}
    ]},
    {"type": "context", "elements": [{"type": "plain_text", "text": "Submit with nothing ticked means merge without checks; I will ask once more.", "emoji": false}]}
  ],
  "expires_in_seconds": 3600
}
MSG
```

## What `pending` means, and what comes back

The `reply` line `{"outcome":"pending", ...}` means the mailbox queued the
operation. Slack has not rendered it; the relay confirms asynchronously and
that confirmation is silent — your next line in the lane is one of:

- a click: `c3 U0456 [ui]: approve (button) = apply_now`. The sender slot is the
  Slack user id; `values` are the button value or the selected options.
  Treat it as the newest message in the conversation and act on it under the
  same policy as typed input — a click grants no extra authority.
- a result you must act on:
  `c3 <relay mailbox id> [ui]: post rejected · reason: invalid_blocks · errors: blocks[1].elements[0].action_id:pattern · next: fix the blocks and send a new post; nothing was posted`.
  The line names the operation (`post` or `update`), the relay's verbatim
  `status`, `reason` and `errors`, and a `next` you can follow as written:
  a rejected post — `fix the blocks and send a new post; nothing was
  posted`; a rejected update — `the card is unchanged; fix the blocks and
  update again, or send a new post`; `conflict` — `the card moved; re-read
  it and update again`, or, when its revision is unknown, `send a new post`;
  `unavailable` — `wait, then send a new post`, except a post answered
  `reason: disabled`, which is the relay's verdict on this identity, not a
  transient: on a version 2 card, `version 2 is switched off on this relay
  for you; send the card again without `behavior` — it goes out as version
  1 (taps still reach you; the card does not react by itself)`, and later lines read
  `cards: yes (version 1)`; on a version 1 card, `cards are switched off on
  this relay; answer in a plain --text reply (a numbered list for a
  choice)`, and later lines read `cards: no`; the next connect re-probes;
  `uncertain` (including no
  result within 600 s) — `the card may exist; do not repost; clicks are not
  routed until the relay's confirmation is read`; `not_sent` (a `reply` that
  died before its send left) — `send the post again`; a late `confirmed
  after uncertain` — `the card is live; clicks now reach this lane`. One
  exception to "update again": a card past its `expires_in_seconds` is
  closed — do not update it again; post a new card or a plain reply. The
  line is complete: no `status --json`, state file, session log or script
  read adds to it, and none comes before the call `next` names. `re-read
  it` means the card content you last sent (your own call), not the
  connector's state; `wait` is a pause of seconds inside your turn, never a
  `sleep 60`.
- nothing: a confirmed card with nobody clicking yet, or a `fallback_sent`
  result (the relay showed your `text` as plain Slack text; there are no
  controls to wait for). Keep working.

A `workflow_button` press produces no event; do not wait for one. The same
`reply` again before any new inbound line reprints its `pending` line and
sends nothing, so a lost exit is safe to retry.

## Fail-closed errors and their fixes

Nothing is sent and nothing is recorded when any of these fires — except
the two `[ui]` rows, the relay's answer to a card it did not render, and
the last two rows, which are stderr notes beside a card that did go out.

| You see | Fix |
| --- | --- |
| usage error: `--text` with `--message-json`, or `--attach` with it | One or the other; put fallback text in the object's `text`; send files with a plain `--text` reply. |
| `ui_needs_relay_lane` | The lane is Slack-direct or a mailbox lane the relay did not originate; reply there with `--text`. |
| `message JSON is not valid JSON` / `must be a JSON object` | Fix the JSON; use the heredoc form so quoting cannot mangle it. |
| `member … not accepted for a post` (or `an update`) | Remove it. A post takes `text`, `blocks`, `expires_in_seconds`, `single_use`, `on_invalid`, `option_sources`; an update takes `text`, `blocks`, `option_sources`. |
| `text` missing or empty; `blocks` missing, empty, or more than 49 | Write the fallback `text`; send 1–49 blocks (the relay keeps the fiftieth for its expiry notice). |
| `… control '<id>' and no button with its own action_id: a multi-pick is read at the Submit press` | Add one Submit button, with its own `action_id`, beside the checkboxes or multi-select (example 10): ticks never reach you, so without a press the answer would never arrive. |
| `action_id … is used by N controls` | Give every button, select, input and checkbox group its own `action_id` (three branch buttons are `pick_a`, `pick_b`, `pick_c`, not one `pick_branch`): the click line and the tap-time `✅ <label>` line are keyed by it, and Slack refuses duplicates too. |
| serialized size over 16 KiB; nesting too deep (the relay's 16-level bound counts the envelope) | Shorten the card: fewer fields, shorter mrkdwn, split into a card and a plain reply. |
| `expires_in_seconds` not an integer 1–604800; `single_use` not a boolean; `on_invalid` not `fallback`/`reject`; `option_sources` not an object | Fix the member's type or range. |
| `{"outcome":"refused","reason":"kind_mismatch", ..., "next": ...}` (exit 2) | `--replace-last --text` while the lane's newest outbound is a card: the kinds never cross; do what `next` says — update the card with `--replace-last --message-json -` (after waiting for its pending result, when `next` says so), or send a new plain reply beside it. |
| `refused` `presentation_pending` | A post in this lane (the card's own or a newer one) or your previous update of the card still awaits the relay's result; wait for it (the same words again only reprint that call's line), then update, or post a new card. |
| `refused` `no_live_presentation` | No card is live in this lane — none posted, or the last one ended without confirmation (rejected or lost), fell back to text, or expired (marked a day after its `expires_in_seconds`; before that the relay answers the update `rejected` or `conflict`); there is nothing to update — post a new card. |
| `refused` `revision_unknown` | The card moved under a conflicting update that reported no revision; post a new card. |
| `refused` `ui_operations_full` | 200 posts and updates still await the relay's result; `next` names when the oldest resolves — wait for it, then send the same call again. |
| the send itself failed (exit 1) | Run the same call again; the same operation id is reused, nothing duplicates. |
| `[ui]: post unavailable · reason: disabled · next: version 2 is switched off on this relay for you; send the card again without `behavior` — it goes out as version 1 …` | Nothing to fix in the card: the relay advertises version 2 but does not admit it for this identity yet; the connector learned it and the same call now posts version 1 (`cards: yes (version 1)` on the line); a card that declares `behavior` is refused there until the relay serves version 2 for you — drop `behavior`. Ask the relay's owner to enable version 2 if the tap-time reaction matters. |
| `[ui]: post unavailable · reason: disabled · next: cards are switched off on this relay; answer in a plain --text reply (a numbered list for a choice)` | This relay renders no cards for this identity: say it in text — a numbered list for a choice, ☐ / ✅ lines for a plan — and post no more cards here until a later connect says `cards: yes`. |
| stderr `custom.slack.ui version 2: per-control templates make this card N bytes (at most 65536 fit a version 2 request); posting per-block templates (M bytes)` (exit 0, card sent as version 2) | Nothing to fix: a form's pick summaries each copy the form, and past the relay's request bound the controls of one row share a view with a label-neutral line (`Selected: …`, `✅ working…`); a press's view is one line on every rung. To keep per-control summaries, shorten the card: fewer long sections, or the plan in a plain reply and the controls in a small card. |
| stderr `custom.slack.ui version 2: … make this card N bytes …; posting version 1 (no early reply at the tap)` (exit 0, card sent as version 1) | Nothing to fix: even one view per row of controls would not fit, so the card went out as today's version 1 card (taps reach you; the card does not react by itself). Shorten the card or split it if the tap-time reaction matters. |

## Non-goals

- The object never carries `channel`, `thread_ts`, a Slack token, a mailbox
  id, a signed conversation token, an operation id, a `ui_id` or a revision:
  the connector injects transport identity from the lane.
- No modals, App Home, raw interaction webhooks, file blocks, or Calls API;
  message-surface Block Kit only. The relay validates the block grammar and
  is the authorization boundary.
- The 46 KiB capability schema is never pasted into a prompt or fetched on a
  send, and the scripts are never read for it: write Block Kit as you know
  it and let the relay's result tell you if a shape is unsupported.
