# Gate State Current — 2026-09-28

Status: DURABLE COORDINATION STATE

PRE_CODEX_STATE=DURABILITY_PENDING
REPORTED_PRE_CODEX_READY=YES
REPORTED_FINAL_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf
BASE_SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9
REMOTE_GITHUB_RESOLUTION=NOT_FOUND_AS_OF_2026-09-28
AUTHORITATIVE_READY=NO
REASON=Reported FINAL_SHA is not currently resolvable from the canonical GitHub repository, so repeated cross-window validation would be duplicate cost and cross-host binding is not yet durable.
NEXT=ONE_GATE_PERSISTENCE_OWNER_ONLY
MAX_GATE_PERSISTENCE_OWNERS=1

COST_GUARD:
Do not admit duplicate PRE_CODEX validators for this same reported SHA.
Other workers must take unrelated READY work, legal post-gate generic preparation that does not require binding to this SHA, or TRUE_IDLE.

INVALIDATION_TRIGGER:
- reported FINAL_SHA changes;
- candidate becomes durably resolvable;
- canonical durable candidate bundle is published;
- gate evidence fingerprint changes.
