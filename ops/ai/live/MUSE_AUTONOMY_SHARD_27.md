# Shard 27 — Durable State Atomicity (gold-planetesimal, READ_ONLY_C2)

SHARD=27
STATUS=SHARD_COMPLETE
SUBCASES_DONE=4 (S1 server state; S2 dispatch packets; S3 artifact store;
S4 residual windows)
CONFIRMED_SOURCE_DEFECTS=0
EVIDENCE_GAPS=0
DISPROVEN=S3 (kein Defect): scripts/artifact_store.py:_atomic_write
  mkstemp+fsync+replace+cleanup (:52-64); put() Blob + Record je atomar,
  content-adressiert, korrupt/konflikt-erkennend (:100-115). Sound.
REUSE_EVIDENCE=S1 server/app.py:65-72 (tmp+fsync+replace, single-proc);
  S2 courier_github_dispatcher.py:35-41 (dito).
S4-NOTE (fremde Owner, kein Packet): dispatch-then-move-Fenster
  (queue_processor.py:18-19, Queue-Lane); Repo-Root central_state RMW
  (Intake-Q2, Writer-Lane); load_state ohne JSON-Guard (app.py:57-58, bekannt).
NEXT_OWNER=(keiner; Shard deckt nur ab)
DO_NOT_REPEAT=sha256-muse-shard-27-01
