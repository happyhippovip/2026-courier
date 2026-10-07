# M9 — NEXT_PHASE_CONVERGENCE (Muse 9)

Stand: 2026-09-28, Quelle: Synthese M1–M8 + Gate/Queue/Matrix (kein RUN, kein Ledger)

## USER_PROBLEM (Operator-Sicht)
Was fehlt noch bis zur naechsten Phase (physische RUNs)? Eine ehrliche Liste mit
Ownern — statt "fast fertig" plus Ueberraschungen.

## CURRENT_RUNTIME_TRUTH (Eingaenge M1–M8)
- M1: Targeted-Suites koharent-green; Voll-Suite ohne Keys collections-rot.
- M2: Mac-E2E-Coverage verwaist (1 Orphan).
- M3: 1 Einheiten-Verwirrung, 1 offener Widerspruch (diff --check), 1 Regel-Konflikt
  (Scope), 1 extern-unverifiziert, 1 offener Fingerprint-Check.
- M4/M5: Code-seitig replay-/restart-sicher (Quarantaene statt Replay).
- M6: HIGH offen (Timeout ohne Kill → Doppel-Effekt-Fenster).
- M7/M8: Harness kann RUN1/RUN2-Beweise nicht liefern (8 + 4 Luecken).
- Fremde Lanes: `FINAL_SHA`-Push BLOCKED (Mensch), Pilot-Autorisierung noetig
  (Mensch), Mac-Setup/Auth-Umgebung (Mensch), Mac-Branch in packed-refs nicht
  gefunden, HIPG undefiniert, Shell LOCKED.

## KONVERGENZ-REGEL (Eintritt physische RUNs)
Alle muessen erfuellt sein — kein"Wird schon":
1. Harness repariert (M7.1-8 + M8.1), Owner: RUN-Lane.
2. M3-Zahlentabelle steht; M3-2/M3-3 entschieden (nicht "geklaert irgendwann").
3. Mac-Branch existiert + Mac-Operator BENANNT (Name/Rolle) + Env steht.
4. M6: Fix ODER schriftliche Risiko-Akzeptanz VOR retry-lastigen Beweisen.
5. Pilot-Autorisierung bleibt SEPARATES Tor (wird nicht in RUN-Eintritt gebuendelt).
Ausdruecklich NICHT verlangt: Voll-Suite-green, PRE_CODEX-Revalidierung, Ledger.

## VERDIKT
M9-NOT_CONVERGED: 3 Menschen-Items (FINAL_SHA, Mac-Env/Operator, M6-Entscheid) +
Harness-Reparatur + M3-Tabelle stehen aus. Naechste Phase ist vorbereitet, nicht
betretbar. Ehrlicher Status statt Countdown.

## MISSING_SYSTEM_SUPPORT
- Kein Konvergenz-Tracker (Owner + Datum pro Item); keine Re-Entry-Prozedur.

## PREPARABLE_NOW
- Dieses Paket + Checkliste oben (5 Punkte, abhakbar ohne einen Lauf).

## BLOCKED_UNTIL
- Siehe Checkliste 1-4 (fremde Lanes + Owner-Entscheide).

## NEXT
Revisit-TRIGGER (nicht Datum): Harness-Reparatur gemeldet ODER Mac-Operator
benannt ODER FINAL_SHA gepusht ODER M6 entschieden. Bis dahin: IDLE, kein Busywork.
Verwandt, nicht dupliziert: `ops/ai/USER_ACCEPTANCE/*` (UA-A01..J01) und
`ops/ai/USER_ACCEPTANCE_*` (aeitere Einzeldateien C/D/H).
