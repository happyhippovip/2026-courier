# Shard 13 — Zero-Spend External Actions (gold-planetesimal, READ_ONLY_C2)

SHARD=13
STATUS=SHARD_COMPLETE
SUBCASES_DONE=6 (S1 publish_courier_result; S2 register_social_channel;
S3 execute_p01_transmission; S4 github_adapter gh-dispatch; S5 invoice;
S6 revenue_intake)
CONFIRMED_SOURCE_DEFECTS=1 (F1 dispatch-ref fallback, LATER)
EVIDENCE_GAPS=0
DISPROVEN=S1 scripts/publish_courier_result.py:64-78 (local file + GITHUB_OUTPUT
  only, fail-closed envelope); S2 scripts/register_social_channel.py (kein
  Send-Call; publishing_policy REQUIRE_EXPLICIT_HUMAN_APPROVAL :123);
  S3 scripts/execute_p01_transmission.py (nur lokaler JSON-Flip, kein Netz —
  Human-Gate-Override als Handoff an Shard 17, nicht mein Packet);
  S5 scripts/invoice_generator.py:56-57 (nur Print/File);
  S6 scripts/revenue_customer_intake.py:8,35 (POST nur an lokalen Server
  127.0.0.1:8080; CLI-Lauf = explizite Human-Aktion).
FIX_PACKETS=F1: FILES=scripts/github_worker_adapter.py:143;
  CAUSAL_BUG=Dispatch-Ref faellt auf `git branch --show-current` zurueck —
  CI-Runs (externer Compute-Spend) koennen auf beliebigem Host-Branch
  landen; MIN_FIX=GITHUB_WORKER_REF required (fail-closed) oder Default auf
  kanonischen Candidate-Branch; TARGETED_TEST=Adapter-Test mit gesetztem/
  ungesetztem Ref + detached HEAD; OWNER=Dispatcher-Lane; LATER.
NEXT_OWNER=Dispatcher-Lane (F1); Shard 17 (P-01-Gate-Note)
DO_NOT_REPEAT=sha256-muse-shard-13-01
