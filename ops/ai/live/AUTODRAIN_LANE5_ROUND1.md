# AUTODRAIN LANE 5 (changed-SHA invalidation) — ROUND 1 (READ_ONLY)

SEED=Session 01a0e78f first-segment digit-sum 55 mod 10 = 5 (hostname unreadable,
shell down; derivation documented, lane kept). HEAD during round: loose ref
fix-cb1-new = 34b0a42; worktree/commit correspondence UNKNOWN (see S4).

## S1 — Daemon/Contract-Payload-Mismatch (Mac-prebuild-S1) re-verifiziert
VERDICT=INVALIDATED-AS-FILED + NARROW SURVIVOR.
- e5751783-Mechanismen beide WEG im aktuellen Worktree: Contract verlangt keine
  execution_* mehr (0 Treffer file-wide) und erzwingt keinen kanonischen
  result_id mehr (nur Presence :141-143; kein identity-hash-Check).
- Daemon sendet weiter uuid4-run/result (:547-548, zeilengleich) ohne execution_*
  (0 Treffer) → Pflicht-9 erfüllt (:120-130), IDs echoed (:138-143), Status
  nativ SUCCESS/FAILED (:282) gegen RESULT_STATES=SUCCESS/FAILED (:25) ok,
  Artefakt-Formen passend (:152-171; :155/:156 Duplikat harmlos).
- SURVIVOR (NEU, kleiner): run_agy übernimmt LLM-"status" verbatim (:309-324;
  FAILED nur wenn UNparsed) → jeder Nicht-{SUCCESS,FAILED}-String → 400
  "invalid result status" (:146-147). MUSE-Adapter-Statusse UNVERIFIED.
- WRITER-PACKET (minimal, nicht selbst schreiben): run_agy-Status auf
  {SUCCESS,FAILED} zwingen (unbekannt→FAILED) vor Payload-Bau. OWNER: SOLE writer.

## S2 — Run-Skript-Isolation re-verifiziert
VERDICT=SURVIVES + NEUER TAIL.
- :1-31 byte-identisch zu e5751783-Read: --db ignoriert (:20), Worker-No-Op (:27),
  --target ignoriert (:31), kein Trap/Cleanup.
- NEU :33-39 (davor Echos): `$?`-Check auf nie-returnierenden Foreground-Verifier;
  Exit 0 → schreibt artifacts/RUN_1_SUCCESS + "Authorizing RUN_2" OHNE jede
  Evidenzprüfung → falscher SUCCESS-Autorisierer. (Skript wuchs post-e5751783,
  Actor unbekannt — passt zu Live-Mutations-Phänomen.)

## S3 — fix-cb1-new local/origin-Divergenz: operationale Consumer?
VERDICT=NO-OPERATIONAL-CONSUMERS (negativ, schließt Risiko).
- Nur Doku/Lane-Files + 1 Incident-Packet referenzieren fix-cb1-new/sync-Begriffe;
  KEINE Skripte/Prompts hängen operationell an local==origin. Divergenz
  (lokal 34b0a42 vs origin-Tracking e5751783) betrifft nur Prosa-Zitate.

## S4 — Worktree/Commit-Korrespondenz (Selbst-Falsifikation)
VERDICT=CONFIRMED-UNKNOWN → Umlabel-Regel.
- Reflog-Tail endet 9dba1505, loose Ref sagt 34b0a42, KEIN Move-Record dazwischen
  (Lane-21-Evidenz, reused); Worktree enthält post-34b0a42-Inhalt (Handoff).
- REGEL: Worktree-Reads = WORKTREE-truth @ dirty-unknown, NIEMALS "34b0a42-truth"
  ohne Blob-Beweis. INVALIDIERT die "-pinned"-Labels auf RESUME_UNIT1 und allen
  Post-Flip-Zeilenrefs (SLOT01, WALL_05, diese Runde S1-S3: alle worktree-observed).
  Mechanismus-Befunde bleiben stehen, Adressierung nicht.

NEXT_SUBCASES (Lane 5, Folgerunden): (a) MUSE-Adapter result-statuses vs
RESULT_STATES (S1-Rest); (b) REJECTED→Release-Pfad im Worktree re-verifizieren
(:572-581-Region, S1-Blast-Radius); (c) Server-Routen-Diff e5751783→Worktree an
Claim/Result/Verify-Stichproben (Invalidierungs-Scope schließen).
DO_NOT_REPEAT=Daemon-Payload-400 (erledigt/engeres Residuum filed); Run-Skript-.sh
(vollständig, inkl. Tail); Branch-Sync-Consumer (negativ geschlossen);
Gate-File-Existenz (W4); Sonnet-Blocker-Re-Review (Lane 21).
STATUS=ROUND1_DONE
