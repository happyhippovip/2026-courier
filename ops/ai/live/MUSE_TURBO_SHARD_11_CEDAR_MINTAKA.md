# TURBO SHARD 11 — CLAIM + Post-Codex-Paket (read-only prep, keine Ausführung)

OWNER=MUSE cedar-mintaka / HOST=MAC / 2026-09-28T13:45Z
CLAIM: SHARD=11 (Reconcile→NEXT_READY→B autostart). Alle 16 Shards unbelegt
vorgefunden (keine Turbo-Claims in live/wall_claims); Master-Prompt ENOENT →
eingebettete Shard-Liste verwendet. CODEX_HIGH_RESULT_CURRENT.md ENOENT →
CODEX NOCH NICHT DA → nur Paket vorbereiten (kein RUN, keine Suite, keine Edits).
Bans: keine 65-96, keine Cascade-Wiederholung, kein Gate-Re-Proof, kein Ledger,
kein Canary, keine alten Findings als neu erklärt (nur Fingerprint-Refs).

## OUTPUT
SHARD=11 Reconcile→NEXT_READY→B autostart
FILES=server/app.py (verify :515-527, claim :286-360), scripts/run1_physical/RUN1_B_AUTOSTART_PROOF_CONTRACT.md (per MAC05-Evidence-Slot referenziert, Ausführung nach Codex)
CAUSAL_RISK=Advance-Bruch → B startet nie (Stall) oder B startet vor A-Verify (Relay-Verletzung). Source-Stand gelesen: PASS→RECONCILED+index+1 (:515-519), Step-Sync (:523-526), Claim bedient nur plan[idx]+QUEUED+Capability-Match (:288-301) — Logik sound gelesen, Paket ist Verifikation, kein Fix behauptet.
MIN_FIX=(keiner — Verifikations-Paket; Fix nur falls Paket-Test fehlschlägt, dann Owner-Patch)
MIN_TEST=Isolierter Flask-Test-Client-Ablauf (post-Codex, kein physischer RUN):
 T1 Kette: 2-Step-Goal (A,B,linux) → A claimen → SUCCESS+Artifact posten →
   verify PASS → assert A=RECONCILED, index=1, B claimbar (task!=None).
 T2 Negativ: verify FAIL → A=FAILED_VERIFICATION, goal=BLOCKED, B-Claim → task None.
 T3 Retry: FAILED-Result (attempt<3) → A=QUEUED, index unverändert, B weiter gegated.
EVIDENCE=Request/Response-Payloads (claim/result/verify), State-Snapshots (tasks+plan) mit sha256, A-Execution-Count ≤1 (Grenze zu Shard 09, dort geprüft).
OWNER=Paket: cedar-mintaka. Ausführung: Post-Codex-Runner (Mac/MUSE). Fix-Owner bei Fail: SERVER_WRITER.
BEFORE_RUN1 (kettet RUN_1-B-Phase; Codex-GREEN ist Eingangsvoraussetzung)
DO_NOT_REPEAT_FINGERPRINT=sha256-muse-turbo-shard11-01
DO_NOT_REPEAT=shard-11-claim (cedar-mintaka); T1/T2/T3-Paket; Vorgänger-FPs (CASCADE-C, NO-OPUS, WHATS_LEFT) nur zitiert
STATUS=SHARD_CLAIMED + PAKET_BEREIT (Ausführung erst nach CODEX GREEN)
