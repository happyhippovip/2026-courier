# SHARD 07 — Heavy Process Supervisor (cross-process HEAVY_JOB_LIMIT=1?)

SHARD=07
STATUS=COMPLETE (5 Subcases, 0 Executions, 0 Edits, Ledger frozen)

SUBCASES_DONE=5 (Source > Prosa):
1. Task-Lease kreuzprozess-sicher: O_EXCL-Create + O_EXCL-Reclaim-Lock +
   Re-Read-under-Lock + fsync (scripts/resource_policy.py:184ff). SOUND.
2. Supervisor-Single-Flight: flock LOCK_EX|LOCK_NB, zweiter exiting 1
   (scripts/mac_worker/muse_supervisor.py:309-322). SOUND.
3. control_lock: flock serialisiert STOP/Admission/Spawn/Claim
   (scripts/mac_worker/runtime_state.py:51-57). SOUND.
4. Deploy-Pin: gunicorn -w 1 --threads 4 "to avoid file locking issues"
   (deploy/run-supervisor.sh:21-23). Kreuzprozess-Sicherheit per
   Deployment-Constraint; -w>1 bräche still server-RLock +
   resource_admission-Counter (beide in-process). REUSE MMAC-023-pkg3.
5. LÜCKE (neu): HEAVY_JOB_LIMIT=1 hat KEINEN Lock — Counter in
   runtime/resource_admission.py:22-57 ist in-process;
   runtime/resource_guard/heavy.lock wird von keinem ausführbaren Code
   geöffnet/geflockt; HNI_30-"system-wide flock" existiert nur in
   Suite-Prosa. Zweiter Heavy-Producer (zweiter Server-Prozess, manuelle
   Runner) umgeht das Limit still. Deploy-Pin mildert (single-worker),
   ersetzt aber keine Enforcement.

CONFIRMED_SOURCE_DEFECTS=1 (Subcase 5, fehlende Enforcement).
EVIDENCE_GAPS=0. DISPROVEN=0.
FIX_PACKETS=1:
  FILES=runtime/resource_admission.py (+ Doku deploy/run-supervisor.sh)
  CAUSAL_BUG=active_heavy_jobs-Counter prozesslokal; kein flock um
    Admission/Release; heavy.lock unbenutzt.
  MIN_FIX=flock(LOCK_EX|LOCK_NB)-Section auf
    runtime/resource_guard/heavy.lock um Heavy-Admission; -w-1-Pin als
    Defense-in-Depth dokumentieren lassen.
  TARGETED_TEST=2 Prozesse kontendieren (tmp-Lockpfad, kein Heavy-Run):
    zweiter wird declined/BUSY statt mitzulaufen.
  OWNER=WINDOWS_ANTIGRAVITY_CENTRAL_WRITER
  CLASS=LATER (Pin mildert; kein aktiver Breach; nicht gate-kritisch)
NEXT_OWNER=Writer (Packet). DO_NOT_REPEAT_FINGERPRINT=muse-shard07-heavy-lock-e11749b6
