# MUSE MAC — Producer-Side False-Green (RUN_1/RUN_2 evidence producers)

POOL=muse | MODE=READ_ONLY_ADVERSARIAL_QA | BASE=bd539f18 | LEDGER=SKIP
Claim-Tool scripts/local_swarm_claim.py existiert nicht (Errno 2);
Ersatz: MT-DELTA-SCAN (MT-02_result 02:11 ist stale, 320 neuere Results).
Kein Claim geschrieben, kein wall_results-Touch, 0 Prozesse, 0 Ports.

## Befund (NEU — Peer MUSE_MAC_01_RUN1.md prüfte nur Contracts/Binder,
## nicht das Producer-Verhalten; dort Z.98: Binder "EXISTS" genügt)

`scripts/run_physical.py::execute_run1` (Z. 60–141) fabriziert das
komplette RUN_1-Evidenzbündel ohne eine einzige echte Ausführung:
kein Server-Boot, kein Worker-Spaw, kein HTTP (subprocess importiert,
0 Popen-Aufrufe in beiden Producer-Dateien; env PORT/STATE_DIR werden
gesetzt aber von nichts konsumiert).

Subcases (alle code-gelesen):
1. NO_EXECUTION: Funktionskörper schreibt nur Dateien (snapshot, logs,
   exit_code, metrics, hash). Kein Dispatch, kein Verify, kein Reconcile.
2. SCRIPTED_ORDER: BOOT→VERIFY→RECONCILE→A_COMPLETE→B_START→B_COMPLETE
   mit je 50 ms sleep (Z. 84–92) → alle Ordnungs-Checks vakant.
3. HARDCODED_PASS: counters {a:1, b:1, relay:0}, final_status SUCCESS,
   exit "0" (Z. 103–126) → A_ONCE/COUNT/ZERO_RELAY/NO_CONTAMINATION
   bestehen per Konstruktion.
4. SELF_HASH: "server_bytes_hash" = sha256 eigener Payload
   (candidate_sha/run_id/host/status, Z. 94–101); Verifier
   (verify_proof_contracts.py:47–57) hasht dieselbe Payload nach →
   Selbstkonsistenz, keine Server-Beobachtung.
5. RUN_2-GLEICH: execute_run2 (run_physical_restart.py:59ff) gleiches
   Muster (sleeps, relay 0, kein Popen/HTTP) → Restart/No-Replay-Evidenz
   aus diesem Pfad wäre gleichermaßen vakant.

## Konsequenz
Preflight (check_resources + check_port_free, Z. 143–157) ist echt;
alles danach ist Kulisse. Jeder künftige "RUN_1/2 PASS", der allein aus
verify_proof_contracts.py gegen dieses Snapshot stammt, ist False-Green.
PASS braucht unabhängigen Witness (central_state.json-Status +
Artifact-Bytes + Verifier-Identität), niemals Snapshot-Selbstcheck.
MAC11 (Assertions UNCHECKED) bleibt damit korrekt und muss genau so
bleiben bis echter Lauf.

DO_NOT_REPEAT_FINGERPRINT=musemac-producer-stub-bd539f18
NEXT=Writer: Producer entweder zu echtem Runner ausbauen oder als
DRAFT/STUB labeln + harten Gate-Vermerk, dass Snapshot allein kein PASS trägt.
