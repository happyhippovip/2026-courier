# WIN-BB-10 BB10-05 — Handoff/scope truth + worktree-vs-candidate divergence (pool-evidence round)

TREE examined=fix-cb1-new @ 329abd80 (read-only files). Pool evidence newly
reachable this session (C:\Users\lol\courier_work\reports\...): read
FINAL_CANDIDATE_HANDOFF.md, MUSE_WIN_P3_PATCH_AUDIT.md (full),
google_win_queue_50/QUEUE_STATUS.md + FINAL_CONVERGENCE.md (headers),
NIGHT_HARVESTER_2026-09-27 (round-2 excerpt), wall_10_20260926 WALL01-R001
(full), MW5 idle-cost (S1 excerpt), responsibility_wall heartbeats
(one-liners). SHELL=DOWN → no git; R001's git-derived rows ADOPTED (not
re-verified), code rows verified against the worktree where overlapping.

## S1. Scope verdict: FIVE vs SIX vs SEVEN (escalate, then freeze)

- Mission FINAL_FIVE: app.py, courier_verifier.py, integration_contract.py,
  test_artifact_upload_flow.py, test_p3_server_idempotency.py.
- Handoff CHANGED_FILES (SIX): app.py, verifier, windows daemon.py, the two
  suites, p3_preview.py (contract MISSING).
- R001 git truth: writer range 7a90e673..4c1e24c touches SEVEN (handoff six +
  integration_contract.py — the expected_sha256 5-key fix, 7b993162).
- Handoff AUTHORIZED_SCOPE_MATCH=YES is FALSE against the mission five
  (daemon unambiguously out of stated scope) and INCOMPLETE against bytes
  (contract omitted). "No sixth file" is already false on bytes.
- BB-10 RECOMMENDATION (decision: Central Writer): freeze the gate on an
  EXPLICIT list = the SEVEN true-delta files (five + daemon.py + p3_preview.py
  as pinned riders: daemon changes are RUN1 load-bearing; p3_preview is
  import-required by both suites). Alternatives (enforce-five by reverting
  daemon/p3_preview) break suite imports and windows upload — incoherent.
  ALSO: handoff BASE_SHA=e7d047d is WRONG-BASE (56 commits/102 files);
  true writer base 7a90e673 (R001) — re-baseline all delta claims to it.

## S2. Worktree-vs-candidate DIVERGENCE hypothesis (needs one git diff)

R001:19 proves candidate-b-1@4c1e24cc contract ACCEPTS 5-key artifact shape
({path,sha256,expected_sha256[,…]}? — exact keys per 7b993162, shell session
to quote). Worktree @329abd80 contract:155-156 accepts EXACTLY 4-key-max
shapes (worker-set expected_sha256 → 400). IF the diff confirms, the trees
DIVERGE on load-bearing validation logic and my/peer case-4 verdicts
("worker expected rejected", peer PKG-C + BB10-01 G1-4) are
REVERSAL-SENSITIVE: true-on-worktree, false-on-candidate. Corroborated SAME
on both: base64 powershell, utf-8 Popen, msvcrt held-fd lock, ftruncate+pid
(R001:26-29 vs my daemon :210-216/:252-260). Extends peer BB01-4 (mint from
live bytes, not patches) to: mint from CANDIDATE bytes, not worktree bytes.
SHELL ACTION (exact): `git diff candidate-b-1 HEAD -- scripts/
integration_contract.py scripts/artifact_store.py` + re-run case-4 pin
against candidate bytes. Until then: all BB-10/BB-01 verdicts stay
@329abd80-bound (labeled as such, no silent transfer).

## S3. Handoff field verdicts (adopted R001 + BB-10 deltas)

- CANDIDATE/REMOTE_SHA TRUE; ARTIFACT/IDEMPOTENCY/EXPECTED markers TRUE (audit
  TOP finding FIXED at candidate — supersedes the 15:05 audit on that item).
- TEST_COMMANDS NON-EXECUTABLE: `py -m unittest` collects 0 tests (zero
  TestCase markers — R001 + harvester H1; BB-10 yields the finding, had
  reached the same conclusion independently). Combined with
  TEST_RESULTS=SKIPPED: ZERO execution evidence for the candidate. REQUIRED:
  `py -m pytest` (or .venv pytest) with exported keys (BB10-01 G0-a).
- UNRELATED_CHANGES=NONE: GRAY (R001) — BB-10 adds: daemon.py is RELATED but
  out-of-stated-scope; disposition per S1.
- KNOWN_UNKNOWNS=NONE: OVERSTRONG — contradicts the filed gap corpus (G-C1
  idempotency declaration, G-C2 orphan, upload-default red window,
  BB01-NEW-1, BB01-5 github stall, BB01-2 antigravity loop, D-BB-3/4/5).
  Writer should replace with the gap register.
- SAFE_FOR_CODEX_REVIEW=YES: TRUE-as-fetchable (remote SHA matches) AND
  gate-untriggered (no FINAL_SHA — peer PKG-G's CODEX_READY=NO stands for
  the GATE; review of branch bytes can still proceed). Both true, different
  questions.
- QUEUE_STATUS 50/50 DONE + FINAL_CONVERGENCE all-VERIFIED/PASS/NONE at
  7b993162: REV-BOUND and STALE (candidate moved twice since: 7b993162 →
  4c1e24cc; worktree differs again). "UNKNOWN=NONE" contradicts gap corpus
  (same note as above). NEXT=AWAIT_MAC_CANARY is the live step (not BB-10).

## S4. Yield + adopt record (P3 audit, 2026-09-26 15:05, rev 7a90e673)

YIELDED (audit filed first): D-BB-1 completeness → audit §1 WHAT_REMAINS
("result may reference a subset"); G1-quarantine-resume → audit REQUIRED
additions (resume-from-HUMAN_REQUIRED); G1-changed-worker-409 → audit
(conflict-post by different worker); V-PKG3-1 core (red window) → audit
transition-cost (BB-10 keeps steady-state framing + :315-323 pin).
ADOPTED (new to BB-10 lane): instruction_override-reaches-claim pin gap;
resume-404-missing-step pin gap; stale-triple-ACK-after-requeue (ACK
oracle ignores CURRENT dispatch — test + one-line fix sketch);
ACK-before-worker-check INFO; goal["goal_id"].get hardening;
heartbeat-200-for-stopped monitoring note; corrupt-record-JSON 500
(400/404 fix + pin); tampered-blob no-heal; MAX_BYTES env skew;
GET-404-vs-400 inconsistency; chunked-413; upload-race safety;
from_env no-I/O; unregister/force_success callerless. SUPERSEDED (audit
rev only): TOP finding (verifier-side expected read moved task-side on
current tree — my case-1 stands).

## S5. WALL-01 reconciliation (candidate-anchored, adopted 2026-09-27)

WALL-01 (wall_10_20260926/reports/WALL-01.md, git-anchored @4c1e24c) CONFIRMS
S2 as INTENDED DELTA, not drift: committed 4c1e24c..fix-cb1-new = 5 files
+29/-10 = (1) verifier strict-allowlist + expected moved worker-ref→TASK-SPEC,
(2) contract dict-specs + result-shape drops worker expected, (3) app.py ACK
3→9-field + changed-result test. Consequences: (a) case-4 is
REVERSAL-CONFIRMED: worker self-attestation OPEN@candidate (5-key accepted +
art-side read = tautology) vs CLOSED@worktree (task-spec + strict shape) —
the ledger delta is a SECURITY FIX; gate MUST use worktree-or-later bytes
for case 4 (extends BB01-4 AGAIN: patches < candidate < worktree, strictness
monotonic). (b) daemon.py UNCHANGED candidate↔worktree ⇒ V-PKG1-1/N1-Q4/N3
≡ WALL-01 C-WIN-01/02/03, mutually corroborated on BOTH revs (strongest
joint verdict in the corpus). (c) ADOPTED from WALL-01 (their filings):
C-VF-01 revenue check_output w/o timeout, C-RV-01 urlopen w/o timeout,
C-RV-02 rmtree pre-clean, C-GH-01 torn-state re-spawn, C-GH-02 silent drop,
R003(f) sys.executable (T26 G-5 open cross-rev), HOLES list (≡ G1 set).
BB10-02 scope note: revenue-script defects D-BB-8/9/12 stand (WALL-01 did
not cover determinism/yml S1); D-BB-10/11 yielded earlier to BB01-NEW-2.
(d) Dirty-worktree note (9 modified + 22 untracked, ledger refactor
uncommitted) EXPLAINS the revision churn observed all session (T-Q/X1 vs
disk, MW1/D4 staleness): reads at different hours saw different bytes.

## Disposition

READ ONLY. S1/S2 need Writer + shell respectively; nothing further here is
provable statically. Dedupe current through: peer PKG-A..G, R001, P3 audit,
harvester R2, MW5-S1, QUEUE_STATUS, FINAL_CONVERGENCE, WALL-01 (TASK-A..D).
