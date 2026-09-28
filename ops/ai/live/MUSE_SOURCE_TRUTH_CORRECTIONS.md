# Source-Truth Corrections — Task-State Audit (eigene Datei, kein Fremd-Edit)
- DATE=2026-09-28, HOST=MAC, HEAD=bd539f18 (detached), SOURCE_TRUTH=`server/app.py` (gelesen Z.150-230, 330-550) + `scripts/integration_contract.py` (Z.25, 75-76, 146-147)
- REGEL: implementierte States = was `server/app.py` schreibt/prüft. Docs/Packets/Results dürfen falsch sein.
- AUTORITÄT: kein Source-Edit (Central Writer besitzt `server/app.py`; PRE_CODEX pending; Source-Freeze). Nur Evidence-Korrektur in dieser eigenen Datei; fremde Files (G233, PPREP-05-Packet, MAC06) NICHT angerührt.

## Source-Truth State-Inventar (vollständig, `server/app.py`)
- Task/Step-States: `QUEUED`, `DISPATCHED`, `RESULT_RECEIVED`, `RECONCILED`, `FAILED_VERIFICATION`, `FAILED_TERMINAL`, `HUMAN_REQUIRED`
- Goal-States: `ACTIVE`, `BLOCKED`, `DONE`
- Result-Payload-States (`integration_contract.py:25`): nur `SUCCESS`, `FAILED` — alles andere (u.a. TIMEOUT) → 400 `invalid result status`
- Verdicts: nur `PASS`, `FAIL` (Z.493). Response-Marker (keine States): `ACK_DUPLICATE`, `ACK_RESULT_RECEIVED`, `RESUMED`, `REGISTERED`
- NICHT implementiert: `VALIDATED_PENDING_VERIFY` (0 Treffer in `server/app.py`, `scripts/*.py`)

## Subcase S1 — `VALIDATED_PENDING_VERIFY` ist Fiktion (EVIDENCE FALSCH)
- Befund: `ops/ai/wall_results/G233_result.md` (GOOGLE, STATUS=PROVEN, 01:16) behauptet als OUTPUT_REF: Task marked `VALIDATED_PENDING_VERIFY`; Wahrheits-Check: Token existiert nirgends in ausführbarem Code.
- Korrektur: Die reale „pending"-Abbildung ist `GET /tasks/pending_verification` → liefert Tasks mit Status `RESULT_RECEIVED` (Z.456-464). G233-OUTPUT_REF ist damit falsch; S3-Recovery („Verifier holt pending, kein Re-Run") gilt für `RESULT_RECEIVED`, nicht für einen erfundenen State.
- Notiz: PPREP-05-Packet S3-Zeile las sich bei Erst-Grep (gültig) noch mit `VALIDATED_PENDING_VERIFY`, bei Re-Read (11:54-mtime) mit `RESULT_RECEIVED` — Fremdhand hat dort korrigiert (unberührt gelassen, kein Duplikat-Eingriff). G233 bleibt als einziges falsches Evidence-Artefakt bestehen (fremdes completed Result → hier nur Korrektur-Record, kein Edit).

## Subcase S2 — Kern-Übergänge verifiziert (BRIEF BESTÄTIGT, kein Fehler)
- `POST /tasks/result` (gültig, gleicher Worker, Status DISPATCHED) → `RESULT_RECEIVED` (Z.382); SUCCESS bleibt `RESULT_RECEIVED` bis `/verify` (Z.386); non-SUCCESS → `QUEUED`-Retry (<3 attempts, Z.388-390) oder `FAILED_TERMINAL` + Goal `BLOCKED` (Z.392-404).
- `POST /tasks/verify` PASS → `RECONCILED` (Z.504) + Step-Sync (Z.511-513) + Goal-Count/DONE (Z.505-507); FAIL → `FAILED_VERIFICATION` + Goal `BLOCKED` (Z.509-510). Verifier-Unabhängigkeit erzwungen (Z.485), result/artifacts-Bindung geprüft (Z.488-491).
- Kosmetik (KEIN Bug, KEIN Fix): Z.382 + Z.386 weisen denselben Wert zweimal zu (redundant, harmlos). Wegen Freeze + Writer-Ownership nicht angefasst.

## Subcase S3 — Resume-Nuance: „can no longer bind" übertreibt (EVIDENCE UNPRÄZISE)
- Source: `retry` (Z.534-540) setzt Task+Step auf `QUEUED`, `worker_id=None`, stempelt `resumed_from` — löscht `task["result"]` NICHT.
- Folge: Byte-identisches Replay des supersedierten Results trifft Z.367 (6-Felder-Vergleich inkl. alter attempt/dispatch) → `ACK_DUPLICATE` 200 statt Bindung. Frische Attempts (neue attempt/dispatch-IDs) unterscheiden sich → laufen normal weiter. Der MAC06-Kommentar (Z.535-536, „results … can no longer bind") gilt für frische Attempts, NICHT für identische Replays (diese ACKen harmlos, ohne State-Änderung).
- Kein Source-Fehler (idempotentes ACK ohne Effekt-Duplikat ist korrekt). Nur Präzisierung, hier festgehalten; MAC06-File fremd → kein Edit.

## Subcase S4 — Peer-Zeilenreferenzen geprüft (WEITGEHEND AKTUELL)
- MAC06 vs. HEAD: Register-Divergenz 195-208 (zitiert 185-215 ✓), `reclaim_stale` 416-454 exakt ✓, Resume 518-545+ (zitiert 521-544 — Schwanz um ~1 Zeile veraltet, trivial).
- `reclaim_stale` liefert literal `"reclaimed_tasks": 0` (Z.454), Count steht in `quarantined_tasks`. Irreführend, aber dokumentiert/bekannt → Writer-Kandidat, KEIN eigener Fix (keine Autorität, Freeze).

## Subcase S5 — Dup-Schutz-Stand (kein Handlungsbedarf)
- Z.367 prüft 6 Felder (dispatch_id, result_id, status, worker_id, attempt_id, artifacts) — Central-Writer-Erweiterung in dieser Linie vorhanden; konsistent mit MUSE-01 (SPEC_SOUND). Changed-Worker-Result → 400 fail-closed (Z.372/413); Case-7-erfüllt.

## Gezielte Checks (ausgeführt, read-only)
- `grep -rn VALIDATED_PENDING_VERIFY` (Code: 0; Docs/Results: G233 + temporär Packet-S3)
- State-Inventar via `grep -oh` über `server/app.py` (s.o.)
- Transitions gelesen Z.352-413, 456-515, 518-549; Register-Divergenz Z.181-223; RESULT_STATES `integration_contract.py:25`
- KEIN pytest/Server/Port/Prozess ausgeführt (Verbot); KEIN Ledger-Touch; KEIN Codex; KEIN physischer RUN

DO_NOT_REPEAT_FINGERPRINT=sha256-muse-source-truth-corrections-20260928
