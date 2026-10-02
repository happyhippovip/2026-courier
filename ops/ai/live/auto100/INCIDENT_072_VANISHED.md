# AUTO100 INCIDENT — 072 output vanished from disk (coordination note, READ_ONLY)

DATE=2026-09-28
REPORTER=AUTO100 Windows window (no shard claimed; see below)
FILE=ops/ai/live/auto100/AUTO100_072.md

## Observation (FACT)
- Direct disk read of AUTO100_072.md: NOT FOUND (os error 2), probed 2x.
- Search-index snapshot of the same path returns 14 COMPLETE lines (SHARD=072,
  STATUS=COMPLETE, LeRobot prior-art check, DO_NOT_REPEAT=YES).
- Neighbors disk-verified PRESENT: 070, 071, 073, 074 (all STATUS=COMPLETE).
  061-069 listed present via index. 075+: no output anywhere.
- Conclusion: exactly ONE shard output (072) is missing on disk while complete
  per index. Isolated incident, not a range wipe. Cause UNKNOWN (delete/cleanup/
  crash/restore artifact — no shell to investigate; no accusation).

## Last-known content (verbatim from index snapshot, NOT restored to a shard file)
SHARD=072 / STATUS=COMPLETE / MODE=READ_ONLY_OR_COORDINATION_ONLY
CURRENT_GATE_SEEN=PRE_CODEX_READY
SOURCES_READ=Web search for LeRobot "evaluated-to-deployed" identity binding.
FACTS=LeRobot: standardized datasets/configs, but struggles with exact behavioral
porting (action normalization, chunk_size vs action_horizon).
NEW_FINDING=LeRobot does NOT provide cryptographically assured evaluated-to-deployed
behavior identity binding; identical loss curves can still vary wildly on deploy.
DUPLICATE_CHECK=First LeRobot check for this moat feature.
WHAT_THIS_CHANGES=LeRobot = integrable toolchain, not a behavioral-assurance competitor.
WHAT_THIS_DOES_NOT_PROVE=Not proof nobody else has it.
KILL_OR_SURVIVE=SURVIVE / NEXT_OWNER=Strategy
NEXT_ACTION=Check OpenPI and GR00T for the same capability. (073=OpenPI and
074=GR00T exist on disk — chain continued, so 072's next action was consumed.)
DO_NOT_REPEAT=YES

## Routing
- DO NOT redo shard 072 (STATUS=COMPLETE + DO_NOT_REPEAT, chain consumed).
SUPPLEMENT 2026-09-28 (spaeter): 075, 076, 077, 078 je per Disk-Read STATUS=COMPLETE
verifiziert; 079 per Disk-Read ABWESENT (Frontier). HEAD weitergewandert auf 9dba1505;
GATE_STATE_CURRENT.md von Disk verschwunden (eigene Reads). Shard-Map inzwischen bis
095 erhalten (045-092 + 093-095); 096-100 weiter undefiniert.
- DO NOT recreate the file blindly (deletion may be intentional).
- OWNER=Chief: decide restore-from-snapshot vs accept-loss. Verbatim above is
  sufficient for restore (14 lines).
- Search index is stale in BOTH directions (072 indexed-but-absent, 074
  present-but-unindexed): never use index alone for existence claims.

## Why this window stopped (no shard taken)
1. CLAIM_INFRA_UNAVAILABLE: no atomic mkdir/O_EXCL (shell down, write_file
   overwrites); claims/ dir absent; shared claim root unreadable-or-empty.
2. NO defined task in Windows range 061..100 beyond 074: prompt map ends at 044,
   no map file in repo (searched). 075+ has neither output nor definition.
Resume triggers: (a) atomic-claim primitive restored or Chief assigns an explicit
shard (no race possible); (b) shard definitions for 075..100 published.
