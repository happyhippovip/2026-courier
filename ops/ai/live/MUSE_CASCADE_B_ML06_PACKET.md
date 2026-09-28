# CASCADE B — Owner-Defect-Packet: ML-06 File-Claim-Liveness
- BASE=bd539f188d19665d16f1b840d7a74009c4c0d4ac
- DATE=2026-09-28
- QUELLE=Wave-A: wall_claims-Vollzählung (676 Files) vs ops/ai/wall_results/ML-06_result.md Punkte 2–3.

## Causal Defect
- ML-06 (STATUS=PROVEN, MISSING_EVIDENCE=NONE) behauptet File-Ebene: Claims enthalten worker_id; Reclaim erst nach Lease-Timeout UND toter PID.
- Zensus: worker_id=1/676, lease_until=1/676, attempt=1/676, dispatch_id=0/676, pid=0/676.
- Folge: Liveness-Entscheidung (live vs stale) hat auf File-Ebene keine durable Inputs; WALL_SYSTEM-Regel „never steal a live claim" dort nicht vollstreckbar. Server-Lease (GLEDGER-105, app.py) unberührt.

## Minimal Fix Scope (Doc-only, 1 File)
- ML-06_result.md-Verdikt splitten: Server-Lease PROVEN, File-Claim-Liveness OPEN (MISSING_EVIDENCE=File-Schema).
- Optional später: Claim-File-Pflichtfelder (worker_id, lease_until, pid) oder Doku „File-Claims tragen keine Lease-Autorität".

## Minimal Retest (kein pytest, kein Run)
1. Feldzensus re-run (read-only python über ops/ai/wall_claims, ~1s).
2. grep ML-06_result.md auf Split-Verdikt (PROVEN-Server / OPEN-File).

## Evidence-Anforderung
- Zensus-Output (8 Feldzähler) + ML-06-Diff (vorher/nachher MISSING_EVIDENCE).

## Klassifikation
- BEFORE_CODEX=NO (File-Layer nicht auf Codex-Pfad; Server-Lease autoritativ).
- BEFORE_RUN1=NO (RUN-Evidence nutzt Server-State, nicht wall_claim-Files).
- CAN_DEFER=YES (hinter RUN_1 einreihen; nur bei Authority-Upgrade der File-Claims vorziehen).

DO_NOT_REPEAT_FINGERPRINT=sha256-muse-cascade-b-ml06-01
