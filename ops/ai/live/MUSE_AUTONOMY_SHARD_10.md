# SHARD 10 — Context Pack Versioning
- BASE=bd539f188d19665d16f1b840d7a74009c4c0d4ac
- DATE=2026-09-28
- SRC=scripts/run_context_sync.py (462 Zeilen)

SHARD=10
STATUS=SHARD_DONE
SUBCASES_DONE=S1,S2,S3,S4,S5,S6
CONFIRMED_SOURCE_DEFECTS=S3b (fsync fehlt im current-swap)
EVIDENCE_GAPS=S2 (kein zeitinvarianter Content-Hash)
DISPROVEN=-
FIX_PACKETS=S3-packet (LATER)
NEXT_OWNER=Context-Sync-Owner (Chief-Lane; unbekannt → Dispatcher routet)
DO_NOT_REPEAT_FINGERPRINT=sha256-muse-shard-10-ctxpack-01

## S1 Hash-Determinismus — NO_ISSUE (executed)
- compute_sha256: sort_keys + kompakte Separatoren (:61-64). Live-Check: order-invariant True, stable True, hex64 True.

## S2 Zeitinvarianz — MISSING_EVIDENCE
- snapshot enthält generated_at (:337) → identischer Materialstand zu anderer Zeit = anderer Hash. Version/Hash vermengt Identität mit Wall-Clock; kein Content-Hash ohne Zeitfeld.

## S3 Atomarität — CONFIRMED_SOURCE_DEFECT (klein, LATER)
- Versionierte Datei direkt geschrieben, nicht atomar (:379, Crash→partiell).
- current-swap via mkstemp+replace ABER ohne flush/fsync (:383-387) — schwächer als Server-Standard (save_state mit fsync, app.py:65-72).
- FIX_PACKET: FILES=scripts/run_context_sync.py:_write_snapshot_atomically; CAUSAL_BUG=s.o.; MIN_FIX=versionierte Datei ebenfalls via tmp+fsync+replace, current-Pfad fsync vor replace; TARGETED_TEST=Kill -9 zwischen write und replace → kein partielles JSON; OWNER=Chief/Context-Sync-Owner; LATER.

## S4 Stale-Erkennung — NO_ISSUE
- check_task_staleness vergleicht Version+Hash (:412-430); Version≠ aber Hash= → current (kein Material-Change) — korrekt.

## S5 Ack-Verifikation — EVIDENCE_DOC_DEFECT
- Docstring verspricht Worker-Ack-Prüfung (context_version_seen, :16); null Code-Refs („seen" nur :16). attach (:393-410) hängt nur an, liest nie zurück.

## S6 Minimal/Bounded — NO_ISSUE
- bounded_context-Allowlist (:398-405), Decisions auf 5 gedeckelt (:403).
