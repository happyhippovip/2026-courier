# Shard 23 — Recovery Package (gold-planetesimal, READ_ONLY_C2)

SHARD=23
STATUS=SHARD_COMPLETE
SUBCASES_DONE=4 (S1 state model; S2 lease/reclaim; S3 portability; S4 package)
CONFIRMED_SOURCE_DEFECTS=0
EVIDENCE_GAPS=1 (R1 boot-recovery runbook, Supervisor-Lane)
DISPROVEN=(none; S3 portability OK: STATE_FILE env + relativ :11,
  ARTIFACT_DIR env + relativ artifact_store.py:74-75, Secrets via Env
  :12-17; S1 atomic save server/app.py:65-72)
R1-MISSING_EVIDENCE: Kein Recovery-Runbook. Befund: kein Claim-Lease mit
  Expiry (Ownership = worker.current_task + last_seen); Recovery nur via
  manuellem POST /tasks/reclaim_stale (300s, :439-477), kein Boot-Reclaim.
  Neues Blech braucht: (1) Repo-Checkout am Candidate-SHA, (2) Env-Keys
  (API + VERIFIER, Import-pflicht), (3) server/state/central_state.json,
  (4) Artifact-Dir, (5) events/github-dispatch-Packets (dispatcher-durable,
  ausserhalb central_state), (6) reclaim_stale-Call + Worker-Re-Register.
  Boot-Auto-Reclaim NICHT empfohlen ohne Partitionsschutz (Duplikat-Risiko)
  -> erst Runbook, dann ggf. Design. OWNER=Supervisor-Lane; LATER.
NEXT_OWNER=Supervisor-Lane (R1)
DO_NOT_REPEAT=sha256-muse-shard-23-01
