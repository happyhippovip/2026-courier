# MUSE TURBO B — Selbstangriff auf SHARD 06 S3 (read-only)

OWNER=MUSE aqua-phoenix / HOST=MAC / 2026-09-28
TARGET=ops/ai/live/MUSE_TURBO_SHARD_06_AQUA_PHOENIX.md (eigener Befund, heute).
ROLE-Platzhalter ungefuellt; Angriff gilt eigenem TURBO-Ergebnis (einzige
eigene TURBO-Arbeit). MODE=READ_ONLY_C2, LEDGER=FROZEN, 0 Edits, 0 Runs.
Gelesen NUR: Target-File + scripts/mac_worker/limit_wrapper.sh (neu, bounded)
+ kill/cleanup-Grep ueber scripts/mac_worker/daemon.py (bounded). Kein git
show (Commit-Fix-Check lane-unmoeglich), kein Re-Trace von S1/S2/S4.

## Angriffsverlauf (8 Pruefpunkte)

1. Disproof-Source? NEIN — limit_wrapper.sh (21 Zeilen) enthaelt nur
   renice/taskpolicy/wait, KEIN timeout, KEIN kill. Wrapper rettet nichts.
2. Doku-Drift? NEIN — S3 ist reine Source-Beobachtung (:291-323), keine
   Prosa-Abhaengigkeit.
3. Bereits gefixt (Commit)? LANE-UNPRUEFBAR (git show banned). Abgedeckt
   durch S4-Deferral (Byte-Bestaetigung auf FINAL_SHA, Codex/Owner).
4. Witness unabhaengig? TEILWEISE — vorgeschlagener Fake-Popen-Test beweist
   nur Handler-Logik, kein echtes Reaping. MINIMUM_TEST verschaerft (s.u.).
5. Stale-Evidence-PASS? N/A — S3 ist Defect-Claim, kein PASS-Claim.
6. Change zu gross? NEIN — 2-4 Zeilen Spiegel des Win-Handlers, minimal.
7. Evidence-Reuse? JA — Win-Handler als In-Repo-Vorbild, G06 zitiert.
8. Kritischer Pfad? JA — RUN_1 nutzt mac/agy-Pfad; Leak = Host-Last-Risiko
   im physischen Fenster. BEFORE_RUN1=YES bestaetigt.

## Verschaerfung (Angriffserfolg, kein Kill)

Wrapper erzeugt DOPPEL-Verwaistheit: Popen-Child = bash-Wrapper, Grandchild =
agy. Timeout verwaist BEIDE (reniced, taskpolicy-backgrounded). S3 damit
staerker als urspruenglich formuliert.

## Ausgabe

SURVIVING_CONFIRMED=S3 mac run_agy Timeout-Orphan (verschaerft: Doppel-Orphan via Wrapper)
REMOVED_FALSE_POSITIVES=(keine — S1/S2/S4 waren Pins, keine Defects)
EVIDENCE_REUSE=Win-Handler :241-249 als Fix-Vorbild; G06-Fingerprints (zitiert)
MINIMUM_OWNER_ACTION=run_agy TimeoutExpired-Zweig: Wrapper+Child killen (Prozessgruppe, da Grandchild!) + communicate; 2-5 Zeilen
MINIMUM_TEST=Integration statt Fake-Popen: echten sleep-Child via Wrapper starten, Timeout erzwingen, Reap per Poll behaupten (Mock-Test allein ungenuegend — Selbstkorrektur)
CRITICAL_PATH=YES
DO_NOT_REPEAT=sha256-muse-turbo-b-shard06-aqua-01; sha256-muse-turbo-shard06-aqua-01
NEXT_OWNER=CENTRAL_WRITER (Fix, Gruppen-Kill beachten) + CODEX_HIGH (S4-Bytes)
