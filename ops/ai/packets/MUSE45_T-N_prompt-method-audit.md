# MUSE-45 T-N — Muse CLI prompt-method audit (read-only)

Branch fix-cb1-new @ 329abd80. Closes the START_HERE open item
"Muse CLI prompt-method audit" for the Mac adapter path. Shell DOWN; static
only. No edits. First MUSE-45 audit of this boundary.

## Question

START_HERE session record: "Muse prompt method must be declared (MUSE_CLI
prompt_via arg|stdin), else MUSE_PROMPT_METHOD_UNCONFIRMED."

## Evidence (OBSERVED)

- muse_adapter.py:60/:69: prompt appended as ARGV element
  (`cmd.append(prompt ...)`); :72 returns `(cmd, None)` — the stdin-payload
  slot exists in the tuple shape but is ALWAYS None.
- daemon.py:349: `argv, _ = build_muse_command(...)` — the second element is
  explicitly DISCARDED at the only call site.
- daemon.py:364: `Popen(argv, stdin=subprocess.DEVNULL, ...)` — stdin channel
  is provably closed at spawn; a stdin prompt method is IMPOSSIBLE here.
- No `prompt_via` / `MUSE_PROMPT_METHOD` string anywhere in muse_adapter.py,
  daemon.py, muse_supervisor.py, or mac_worker/config.json (searched).
- Surrounding discipline (corroborated GOOD): prompt persisted pre-spawn
  (:348 prepare_prompt), admission gates before spawn (:362, CLAIMED retained
  :531-534), timeout min(config,3600)s + 8MB output cap (:368-372), no-retry
  on ambiguity (:372), --yolo capability-gated (:58-59,:70-71, never default).

## Verdict

- Mechanism: OBSERVED = arg (only channel physically possible; stdin DEVNULL).
- Declaration: MISSING. Per the START_HERE rule the status stays
  MUSE_PROMPT_METHOD_UNCONFIRMED until `prompt_via: arg` (or equivalent) is
  declared in MUSE_CLI capabilities/config and pinned by a test.
- Severity LOW (declaration/docs gap, zero behavioral ambiguity). Owner: Mac
  adapter steward. One-line declaration + one assertion closes it; needs a
  shell session for the test run (parked).
- REFINEMENT (T-P cross-check): fail-closed on missing protocol is TEST-PINNED
  (test_muse_supervisor.py:286-296); prompt_via exists in test vocabulary but
  production never reads it — the declaration mechanism is half-built (asserted
  insufficient-alone, never asserted as declared-with-protocol).
