# MUSE CASCADE WAVE B — Owner-Defect-Packets (aus eigener Wave A)

SESSION=cloud-octans · DATE=2026-09-28 · MODE=READ_ONLY · 0 edits, 0 runs
SOURCE=ops/ai/live/MUSE_WHATS_LEFT_CURRENT_cloud-octans.md (eigene Wave A)
Peer-Findings nicht wiederholt, fremde Files unberührt.

## B1 — C1 planner-duplicate→503
STATUS=READY_FOR_OWNER
OWNER=WINDOWS_ANTIGRAVITY_CENTRAL_WRITER (server/app.py)
CAUSAL_DEFECT=`server/app.py:149` mappt deterministischen Planner-Datenfehler
(`duplicate task_id from planner`) auf 503 statt 400 → löst Retry/Backoff für
einen niemals-erfolgreichen Retry aus (gleiche Bedingung aus goal_text → 400, :123).
MIN_FIX_SCOPE=1 Zeile: `:149` 503→400.
MIN_RETEST=Bestands-Claim/Contract-Tests grün + 1 neu: Planner-Duplikat → 400 erwartet.
BEFORE_CODEX=NO
BEFORE_RUN1=NO
CAN_DEFER=YES
DO_NOT_REPEAT=cascade-b-C1-503-app149

## B2 — W Adapter-Shadow-Ledger
STATUS=READY_FOR_OWNER
OWNER=Adapter-Lane-Owner (gemini_worker_adapter.py) + Central Writer (Vokabular)
CAUSAL_DEFECT=`scripts/gemini_worker_adapter.py:77-95 consume()`: (a) CWD-relatives
`central_state.json` statt Server-State (`server/state/central_state.json` /
$COURIER_STATE_FILE), silent fallback auf `{"tasks": {}}`; (b) Label `"state":
"RECONCILED"` für jede konsumierte Task inkl. FAILED — kollidiert mit Server-
RECONCILED (verify PASS). Adapter-Ledger als Reconcile-Beweis = false green;
CWD-Akkumulation = Kontaminationsvektor.
MIN_FIX_SCOPE=State-Pfad explizit (kein CWD-Implizit, kein silent fallback);
Label umbenennen (z.B. CONSUMED) oder an SUCCESS koppeln. Evidenz-Regel sofort:
Adapter-Ledger bis Fix als Reconcile-Beweis unzulässig.
MIN_RETEST=Adapter-Unit: FAILED-Run → kein RECONCILED-Label; fehlende State-Datei
→ expliziter Fehler statt Shadow-Neuanlage; Pfad-Test gegen $COURIER_STATE_FILE.
BEFORE_CODEX=NO (Code-Fix)
BEFORE_RUN1=YES (Evidenz-Quarantäne sofort)
CAN_DEFER=YES (Code) / NO (Evidenz-Regel)
DO_NOT_REPEAT=cascade-b-W-adapter-ledger

## B3 — D run_id-Belegregel (Evidence-only, kein Code)
STATUS=READY_FOR_OWNER
OWNER=Proof-Card-Autoren (alle Lanes)
CAUSAL_DEFECT=Kein Code-Defekt (harmlos): server-seitig ist run_id permanent None
(claim :343 setzt None, prepare_task nur setdefault, verify-Identität ohne run_id).
Jede Card, die run_id aus Server-State zitiert, zitiert None.
MIN_FIX_SCOPE=Docs-only Einzeiler in Card-Templates: run_id aus Server-State
streichen oder als None kennzeichnen.
MIN_RETEST=Keiner (Grep-Check: keine Card zitiert server-run_id).
BEFORE_CODEX=NO
BEFORE_RUN1=YES
CAN_DEFER=NO
DO_NOT_REPEAT=cascade-b-D-runid-rule

## B4 — Y RUN_2-Sheet-Rebind (Evidence-only, kein Code)
STATUS=READY_FOR_OWNER
OWNER=RUN_2-Sheet-Owner
CAUSAL_DEFECT=`RUN_2_RESTART_COMMAND_SHEET.md` befiehlt `python3 -m src.main`,
`ops.assert_state`, `runs/run_001/...`, ResourceAdmissionController — 0 Treffer
in server/scripts, kein `runs/`-Verzeichnis. Unbelegte Template-Prosa, als
ausführbar lesbar (Gate-Zeile korrekt).
MIN_FIX_SCOPE=Befehle auf claim/resume/reclaim-API umschreiben oder Datei als
TEMPLATE labeln.
MIN_RETEST=Jeder Befehl manuell gegen Repo auflösbar (Pfad-/Symbol-Grep).
BEFORE_CODEX=NO
BEFORE_RUN1=YES (sonst RUN_2-Prep-Verwirrung)
CAN_DEFER=NO
DO_NOT_REPEAT=cascade-b-Y-sheet-rebind

FAMILY_COMPLETE (eigene B-Packets; fremde B-Tasks unberührt)
