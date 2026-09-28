# MUSE MAC Window 4 — Process Isolation Checkpoint (PREP ONLY, NO KILLS)

- SLOT=MUSE_MAC_04_PROCESS_ISOLATION (unique C2; reuses MAC02/MAC03/MAC08, no duplicate review)
- HOST=Mac, REPO=/Users/user/Downloads/2026-courier, BASE=bd539f18
- GATE: PRE_CODEX=DURABILITY_PENDING, AUTHORITATIVE_READY=NO, READY_FOR_PHYSICAL_RUN=NO → keine Ausführung
- LEDGER_WORK=SKIP. Zero signals sent. Foreign processes protected.

## Ownership (observed read-only)
- SELF: shell PID 3217 / PGID 3217 (session shell; distinct from all below)
- FOREIGN (never signal): PID 606 (PPID 1, PGID 606, `python -m server.app`) LISTEN :8080; PID 620 (mac_worker daemon.py); PID 629 (courier_verifier.py)
- PORTS: :8081 free (lsof no LISTEN); :8080 foreign-owned → staging precondition holds, production untouched
- PGID RULE: TERM/KILL only own future staging PGID (`kill -TERM -<own_pgid>`); never bare-PID kill from pidfile

## Isolation verdicts
- STATE: production `server/state/central_state.json` + `artifacts/{blobs,records}` untouched; staging `isolated_run1/2` exist (peer MAC03, 11:36, je {artifacts,logs,temp,run_id.txt} leer) — fremd, nicht angerührt
- LOG: production `logs/*` (motor.err 3.8 MB u.a.) fremd-dirty, untouched; staging = `isolated_run1/logs` + `isolated_run2/logs` (leer)
- ARTIFACT: production blobs/records vs `isolated_run*/artifacts` (leer) — sauber getrennt
- TEMP: `/tmp/courier_heavy_job.lock` absent, `/tmp/courier_run*` absent → lane frei, nichts gehalten
- OWNED CLEANUP (nur Eigenes): dieser Checkpoint-Doc + künftig eigene Staging-PGID; NIEMALS fremde PGIDs, pidfile-PIDs, production-state/logs, peer-run-dirs

## Orphan behavior (no action taken)
- `logs/courier_daemon.pid`=46397 → `ps -p 46397` leer: orphan RECORD, kein Prozess; PID-Reuse-Risiko → nur recorden, nie darauf killen
- Keine live Orphans beobachtet (nur 606/620/629 als legitime Fremdprozesse)

## 4 Failure-Szenarien (konkret geprüft, code-grounded)
- F1 Port-Kollision: :8081 belegt → Boot-Abbruch (Preflight `lsof -i :8081`, RUN_1-Checkliste). Heute: frei → Punkt grün, Abbruch-Regel gebunden.
- F2 Heavy-Lock belegt: `/tmp/courier_heavy_job.lock` existent → Abbruch (MAX_HEAVY_JOBS=1). Heute: absent → lane frei.
- F3 Orphan-Child nach TERM: Staging-Server stirbt, Child überlebt (Timeout-ohne-kill/reap-Lücke, MMAC-073-Klasse; Vorlage run_muse-cleanup_group). Mitigation: PGID-SCAN auf eigene PGID begrenzt, dann `kill -TERM -<own_pgid>` + Port-frei-Verifikation (RUN_2-Harness-Sequenz). Heute nichts zu cleanen.
- F4 Pidfile-Reuse-Kill: 46397 könnte recycelt sein → Verbot von `kill $(cat *.pid)`; Pflicht: PGID- + Cmdline-Match (`ps -o pid,pgid,comm`), sonst Abort. Heute: kein Kill, nur Nachweis der toten PID.

## BACKUP (Hauptfamilie peer-fertig MAC01–11 → Resource Admission + Timeout)
- ADMISSION (fresh read): loadavg {5.81 10.49 10.91} → FAIL vs <4.0 → Boot weiter BLOCKIERT (Verschärfung ggü. MAC08 8.36); heavy/port/temp weiter grün; RAM: 17 GB total, free 7246 + purgeable 80269 Seiten (Beobachtung, kein Gate-Urteil ohne Spec-Schwelle)
- TIMEOUT (read-only grep): socket `settimeout(1)` (run_physical*.py:41–42); Boot-Liveness `sleep 2` + curl (RUN_1-Checkliste); RUN_2 kill→verify-port-free→restart; 50 ms-Sleeps (run_physical.py:85–91, restart:95–99) vs `sleep 1`-Minimum (NO_TIGHT_POLLING_AUDIT) → Writer-Finding aus MAC08 bleibt, kein Patch (Source-Freeze + Fremd-Lane)

## Result block
TASK_ID=MUSE_MAC_04_PROCESS_ISOLATION
FAMILY=runtime/process-isolation
STATUS=PREP_DONE (10/10 Punkte inventarisiert, 0 Signale, 0 Kills, 0 Writes außer diesem Doc)
RESULTS_REUSED=MAC02_PROCESS (ownership) + MAC03_ISOLATION (run-dirs) + MAC08_RESOURCES (admission-baseline)
FINDING=kein Blocker außer Load (5.81>4.0); Fremd-PIDs 606/620/629 geschützt; Orphan nur als Record
MISSING_EVIDENCE=RUN-time Staging-PGID (existiert erst bei Boot nach READY)
NEXT_EXACT_ACTION=Boot nur nach READY_FOR_PHYSICAL_RUN=YES + Load<4.0; dann eigene PGID tracken, F1–F4-Regeln exekutieren
DO_NOT_REPEAT_FINGERPRINT=sha256-muse-mac04-procisolation-01
