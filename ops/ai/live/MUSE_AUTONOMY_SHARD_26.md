# Shard 26 — Circuit Breaker (gold-planetesimal, READ_ONLY_C2)

SHARD=26
STATUS=SHARD_COMPLETE
SUBCASES_DONE=4 (S1 poison-quarantine; S2 poll-loop trip; S3 retry-bound;
S4 invocation model)
CONFIRMED_SOURCE_DEFECTS=2 (F1 poison; F2 endless-poll, beide LATER)
EVIDENCE_GAPS=1 (G1 motor retry bound)
DISPROVEN=(none)
FIX_PACKETS=
F1: FILES=scripts/queue_processor.py:21-24; CAUSAL_BUG=poison-Intake wird
  caught+printed, bleibt in intakes/pending -> jede (scheduler-getriebene)
  Invokation retryt ewig, keine Quarantaene, kein Counter; MIN_FIX=failed/-
  Quarantaene-Dir + Move nach deterministischem Fail (oder N-Strikes);
  TARGETED_TEST=poison-File -> 1x Fail -> quarantined, Rest laeuft;
  OWNER=Queue-Lane; LATER.
F2: FILES=scripts/courier_github_dispatcher.py:89-122; CAUSAL_BUG=persistente
  Fehler (401/Server down) -> except+log+sleep(5) ewig, kein
  Consecutive-Failure-Trip, kein Exit/Backoff; MIN_FIX=Failure-Counter mit
  Trip (Exit non-zero nach N) + Erfolgs-Reset; TARGETED_TEST=Mock-401 ->
  Trip nach N; OWNER=Dispatcher-Lane; LATER.
G1-MISSING_EVIDENCE: Provider/Motor-Retry-Bound (frueher PROVIDER_WAIT max N)
  im aktuellen Baum nicht lokalisierbar (kein cannon_motor.py, kein
  PROVIDER_WAIT in scripts/) -> Owner Worker/Motor-Lane.
S4-NOTE: process_queue selbst ist one-shot (kein while True); Endlosigkeit
  nur via Scheduler-Re-Invoke -> F1-Packet praezise so gefasst.
NEXT_OWNER=Queue-Lane (F1); Dispatcher-Lane (F2); Worker/Motor-Lane (G1)
DO_NOT_REPEAT=sha256-muse-shard-26-01
