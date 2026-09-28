# WAVE B PACKET — Producer-Side False-Green (aus Wave-A-Finding)

STATUS=PACKET_READY (kein Source-Edit, keine Revalidierung, kein Run)
OWNER=WINDOWS_ANTIGRAVITY_CENTRAL_WRITER (scripts/run_physical*.py + run1_physical/-Verifier)
WAVE_A_REF=ops/ai/live/MUSE_MAC_04_FALSEGREEN_PRODUCER.md
(NICHT neu geprüft: Peer MUSE_MAC_01_RUN1 Contracts; G233/G231/G237 bereits
peer-korrigiert; S2-Vakuum; Timestamps — alle DO_NOT_REPEAT.)

CAUSAL_DEFECT=scripts/run_physical.py::execute_run1 (Z. 60–141) und
scripts/run_physical_restart.py::execute_run2 erzeugen das komplette
RUN_1/RUN_2-Evidenzbündel ohne Ausführung: 0 Popen/HTTP/Dispatch bei
importiertem subprocess; Transitions per 50-ms-sleep geskriptet;
Counters {1,1,0} + SUCCESS + Exit 0 hardcoded; "server_bytes_hash" =
sha256 selbstverfasster Payload. scripts/run1_physical/verify_proof_
contracts.py prüft dieselbe Payload nach (Selbstkonsistenz) → PASS per
Konstruktion. Preflight (Resources/Port) ist echt, Rest Kulisse.

MIN_FIX_SCOPE=kleinste Variante (kein Runner-Ausbau nötig): Snapshot erhält
Provenienz-Feld (z. B. "synthetic": true) + Verifier REJECTET synthetische
Snapshots als PASS-Basis; DRAFT/STUB-Label an beide Producer + Gate-Vermerk
"Snapshot allein trägt kein PASS". Echter Runner-Ausbau wäre größer und ist
NICHT Teil dieses Packets.

MIN_RETEST=1 Negativ-Test (Writer): Contracts gegen Producer-Output müssen
FAILen (synthetic rejected); Positiv-Pfad erst mit unabhängigem Witness
(central_state.json + Artifact-Bytes + Verifier-Identität) wieder grün.

BEFORE_CODEX=NO (Codex prüft Candidate, nicht Harness)
BEFORE_RUN1=YES (muss stehen VOR jedem RUN_1-PASS-Verdikt)
CAN_DEFER=NO (bewacht das wichtigste Verdikt; Defer = False-Green-Risiko)

DO_NOT_REPEAT_FINGERPRINT=musemac-producer-stub-bd539f18; musewb01-producer-packet
FAMILY=WAVE_B_MUSE_PRODUCER → bei Writer-Übernahme: FAMILY_COMPLETE.
