# MUSE TURBO A — ROLE=M05 PROCESS_KILL_REAP (Post-Codex-Paket, Codex absent)

ROLE=M05 (lowest free falsifier task; M01/M09 peer-done; M04/M06/M08/M10/M11/M12/M13/M14
lane-covered; M02/M03/M07 writer-owned; M15/M16 gated). Codex absent → Paket-Modus.
READ_ONLY_C2, 0 edits, 0 runs, 0 ledger. 5 Subcases, current source.

## S1 win run_task TimeoutExpired
CLAIM=Win-Task läuft nach Timeout verwaist weiter.
SOURCE_TRUTH=communicate(timeout=600) (:232); TimeoutExpired → taskkill /F /T
+ process.kill + communicate-Reap (:239-250, status FAILED :250); generischer
Exception-Pfad identisch (:251-262).
FALSE_GREEN_PATH=(none — FAILED ehrlich, Prozess tot).
INDEPENDENT_EVIDENCE=Source-Read (kein Exec).
MINIMUM_FIX_OR_GUARD=(none nötig).
MINIMUM_TEST=(none nötig).
DISPROVEN_OR_CONFIRMED=DISPROVEN (kill+reap vorhanden).

## S2 mac run_agy TimeoutExpired
CLAIM=Timeout (300s) lässt verwaisten agy-Prozess zurück.
SOURCE_TRUTH=Popen + communicate(timeout=300) (:303-305); bare except →
return FAILED-Dict, kein kill/kein reap in :291-327; Default-Modus ist
ANTIGRAVITY (:119/:519), run_agy ist der else-Default-Pfad (:537) → live.
FALSE_GREEN_PATH=FAILED wird sauber gemeldet, während der verwaiste agy-Prozess
unbeaufsichtigt weiter exekutiert (Doppel-Effekte, CPU, späte Side-Effects
außerhalb jeder Bindung).
INDEPENDENT_EVIDENCE=Source-Read (kein Exec).
MINIMUM_FIX_OR_GUARD=except/finally kill+communicate nach Win-Vorbild (:239-250)
oder cleanup_group wie run_muse (:385). 3-5 Zeilen, eine Funktion.
MINIMUM_TEST=Unit mit Stub-Popen (TimeoutExpired) → terminate aufgerufen +
FAILED zurück. Unexecuted (Packet).
DISPROVEN_OR_CONFIRMED=CONFIRMED (Lineage: MMAC-073 auf b-1; hier auf aktueller
Linie neu gegroundet — Persistenz, keine Neuerzählung).

## S3 github adapter Deadline
CLAIM=Deadline-Ablauf lässt lokale Prozesse/Tasks hängen.
SOURCE_TRUTH=Remote-Execution (kein lokales Child); Deadline → WAITING_FOR_WORKER
+ return 0, nächste Invokation setzt fort (:154-171); FAILED-Post nur auf
Exception-Pfad (:183-196, POSTED_FAILED).
FALSE_GREEN_PATH=(none).
INDEPENDENT_EVIDENCE=Source-Read.
MINIMUM_FIX_OR_GUARD=(none nötig).
MINIMUM_TEST=(none nötig).
DISPROVEN_OR_CONFIRMED=DISPROVEN (lokal nichts zu killen; Remote läuft weiter).

## S4 gemini dispatch TimeoutExpired
CLAIM=Timeout (60s) lässt verwaisten agy-Prozess zurück.
SOURCE_TRUTH=communicate(timeout=60) (:36); except :52 deckt nur JSON-Parse;
TimeoutExpired propagiert aus dispatch() — ABER: kein Produktions-Caller
(reine Test-Referenz tests/test_gemini_worker_adapter.py; eigenes
central_state-Ledger :75-98 spricht für Legacy/Scratch-Status).
FALSE_GREEN_PATH=(latent — unwired, kein Live-Pfad).
INDEPENDENT_EVIDENCE=Source-Read + Caller-Grep (leer).
MINIMUM_FIX_OR_GUARD=Gleiches kill-Muster wie S2, falls je gewired; oder als
Dead Code retirieren (Owner-Entscheid).
MINIMUM_TEST=Wie S2, falls gewired. Unexecuted.
DISPROVEN_OR_CONFIRMED=CONFIRMED-latent (Code-Lücke echt, aber kein Live-Pfad).

## S5 Reap-Vollständigkeit (Sweep)
CLAIM=Weitere Live-Lücken jenseits S2/S4.
SOURCE_TRUTH=Win reapet (communicate nach kill :246-247/:259-260); run_muse
finally cleanup_group (:385); geprüfte Funktionen erschöpft (run_native nicht
geprüft — Boundary, kein Claim).
FALSE_GREEN_PATH=(none gefunden).
INDEPENDENT_EVIDENCE=Source-Read.
MINIMUM_FIX_OR_GUARD=(none).
MINIMUM_TEST=(none).
DISPROVEN_OR_CONFIRMED=DISPROVEN (keine dritte Live-Lücke in geprüftem Scope).

CONFIRMED=S2 (live/default), S4-latent (unwired)
DISPROVEN=S1,S3,S5
MISSING_EVIDENCE=(none — run_native außerhalb Scope, benannt nicht behauptet)
OWNER_PACKET=S2 → MAC/Worker-Owner (CENTRAL_WRITER fallback); S4 → retire-vs-wire Owner-Entscheid
BEFORE_RUN1=S2 (verwaiste agy-Prozesse untergraben Witness-Isolation genau dann,
wenn RUN_1-Mac-Tasks über Default-ANTIGRAVITY laufen — was der Default ist)
BEFORE_RUN2=(none beyond S2) BEFORE_FREEZE=(none) 
DEFER=S4-latent (unwired)
DO_NOT_REPEAT=muse-turbo-m05-a-01
STATUS=A_COMPLETE (proceed to TURBO B destruction)

## TURBO B — DESTROY YOUR OWN FINDING (same turn, only A-file + cited sources)
1. Counter-evidence? S2: caller :537 wraps only run_muse in try; run_agy call
   bare — no caller kill. No atexit/reaper in read scope. NONE FOUND.
   S4: no-caller fact already downgrades to latent inside A. NONE BEYOND THAT.
2. Doc drift only? No — all verdicts grounded in today-read source lines. NO.
3. Fixed by other commit? Defect textually present in current working tree. NO.
4. Witness independent? Claim evidence = absence of any kill call in :291-327
   (decisive by inspection; absence cannot be stale). Future unit (stub Popen:
   fail-pre/fix-post) is claim-independent. YES, SUFFICIENT.
5. Stale PASS? No PASS claimed; DISPROVENs rest on current source. NO.
6. Change oversized? S2 fix 3-5 lines/one function; S4 wire-or-retire. MINIMAL. NO.
7. Reuse? G06 win-pattern as fix template; 073 as lineage (both cited). NOTED.
8. Critical path? S2 YES (default ANTIGRAVITY :119/:519/:537 = mac default;
   orphans break witness isolation). S4 NO (unwired).
SURVIVING_CONFIRMED=S2-live, S4-latent
REMOVED_FALSE_POSITIVES=(none — A already downgraded S4; no inflation found)
EVIDENCE_REUSE=G06-win-pattern (fix template), MMAC-073 (lineage)
MINIMUM_OWNER_ACTION=S2: except/finally kill+communicate in run_agy (or
cleanup_group); S4: wire-or-retire decision
MINIMUM_TEST=stub-Popen TimeoutExpired unit → terminate called + FAILED (S2)
CRITICAL_PATH=YES (S2)
DO_NOT_REPEAT=muse-turbo-m05-b-01 (extends -a-01)
NEXT_OWNER=MAC worker owner (CENTRAL_WRITER fallback)
FAMILY_COMPLETE=YES
