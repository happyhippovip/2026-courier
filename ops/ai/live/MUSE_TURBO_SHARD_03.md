# TURBO Shard 03 — Q3 crash-window/quarantine (post-Codex packet, READ_ONLY_C2)
- BASE=ee2bb49b | DATE=2026-09-28 | CODEX: kein Result (Paket vorbereitet, kein Gate-Claim)
- FILES: scripts/queue_processor.py (ganz, 27 Zeilen), scripts/intake_dispatcher.py:7-68

SHARD=03
FILES=scripts/queue_processor.py:18-19 (order), :21-24 (poison-loop); scripts/intake_dispatcher.py:11,26,36,52-66
CAUSAL_RISK=Crash zwischen externem Dispatch und File-Move feuert beim nächsten Lauf den kompletten externen Workflow NEU (neue task_id per uuid :11 + neues `gh workflow run` :26 = echte Doppel-Ausführung mit Fremd-Cost); Poison-Files loopen ewig (kein Quarantäne-Pfad); non-atomarer State-Write + Clobber bei Read-Error
MIN_FIX=Move-vor-Dispatch geht nicht (Dispatch braucht File); daher: (1) idempotente Intake-Keys (customer_reference→stabile task_id statt uuid :11) ODER Move nach processed VOR Dispatch mit Status-Persistenz; (2) Quarantäne-Dir + Move-aside nach N Fehlversuchen; (3) tmp/replace + kein Clobber (:49-50, :65-66)
MIN_TEST=kill-zwischen-:26-und-:19 → genau 1 externer Run; Poison-File (fehlende Keys) → nach N Versuchen in quarantine/ statt Endlos-Print; korruptes State-File → kein {"tasks":{}}-Clobber
EVIDENCE=Order :18→:19 gelesen; Neu-UUID :11 + Neu-Dispatch :26 gelesen (Idempotenz-Behauptung damit DISPROVEN am aktuellen Stand); Quarantäne-Abwesenheit per Vollread; take-latest :36 als Cross-Link zu Shard 02 (nicht erneut geprüft); Same-File-Schema-Mix ("state":"DISPATCHED_TO_EXTERNAL" :59 vs kanonisch "status") als Minor-Note
OWNER=WINDOWS_CENTRAL_WRITER (Intake/Queue-Lane)
BEFORE_RUN1|RUN2|FREEZE|PILOT=LATER (Revenue-Intake-Pfad, kein RUN_1/2-Pfad; kein Codex-Gate: kein kausaler Pre-Codex-Pfad)
DO_NOT_REPEAT=Q1-take-latest-Details (Shard 02); W1-makedirs/W2-gemini (gleiche Write-Klasse, eigene Instanz hier nur referenziert); VPV/RESULT_RECEIVED-Klassen
STATUS=SHARD_DONE (5 Subcases, 0 Edits, 0 Runs)
