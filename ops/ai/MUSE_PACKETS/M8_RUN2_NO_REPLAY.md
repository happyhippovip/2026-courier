# M8 — RUN2_NO_REPLAY (Muse 8)

Stand: 2026-09-28. Statisch. Kein RUN, kein Kill, kein Neustart.

## Befund: Mechanik kohärent, Ansteuerung fiktiv
HALT (Code gelesen):
- H1. Server-Recovery: Register mit `current_task=None` bei Server-Dispatch →
  HUMAN_REQUIRED + `WORKER_RESTARTED_AND_LOST_STATE` statt Replay
  (`app.py:195-202`).
- H2. Stale-Quarantaene: 300-s-Schwelle, DISPATCHED→HUMAN_REQUIRED, Goal BLOCKED,
  nie stilles Re-Queue (`app.py:419-458`).
- H3. Resume-retry: Re-Queue + frische IDs beim naechsten Claim; alte Results
  binden nicht mehr (`app.py:542-553` + `:323-325`).
- H4. Atomarer State: `save_state` = tmp + fsync + `os.replace` (`app.py:65-72`);
  `kill -9` kann letzte Schreibung verlieren, aber kein torn JSON erzeugen
  (POSIX-replace). Restart liest immer einen ganzen Stand.
- H5. Daemon-Phasen: STARTED→freigeben, RESULT_READY→nur redelivern
  (Server antwortet ACK_DUPLICATE), RELEASE_PENDING→freigeben (beide Daemons).

BRICHT (Skript/Ansteuerung):
- B1. `run_2_mac.sh:28` nutzt dieselben ignorierten `--db`-Flags (M7-B1) →
  "same db"-Behauptung (`:27`) ist falsch; Restart trifft Live-State.
- B2. Es wird NUR der Server gekillt (`:9-14`); ein echter Daemon liefe weiter
  und hielte `current_task.json` + Lock — Neustart-Szenario unvollstaendig.
- B3. Der "Worker" ist wieder das `integration_contract`-No-Op (`:35`, M7-B2) →
  die Daemon-Recovery-Pfade (H5) werden von RUN_2 gar nicht gefahren.
- B4. Checker (`verify_run2_evidence.py`) erwartet SQLite + Abwesenheit von
  Log-Strings, die nie geloggt werden (M7-B4/B5) → wuerde fälschlich BESTEHEN
  (kein "Claimed task A" findbar, weil nie geschrieben — Vakuum-Gruen).

## Urteil
No-Replay-LOGIK ist sauber gezeichnet (H1–H5), aber RUN_2 in heutiger Form
faehrt sie nicht und sein Checker ist vakuum-gruen (B4 ist die gefaehrlichste
Stelle: Bestehen ohne Pruefung).

## ACCEPTANCE / REQUIREMENT (Prep, kein RUN)
- M8.1: RUN_2-Szenario vollstaendig: Server-kill UND Daemon-kill (getrennt
  dokumentiert: je ein Fall), danach Neustart beider gegen ISOLIERTEN State.
- M8.2: Checker-Negativfaelle: "A nie redispatched" wird ueber
  Dispatch-Zaehlung/IDs im State bewiesen (attempts==1, genau 1 dispatch_id
  fuer A), nicht ueber Abwesenheit nie-geloggter Strings.
- M8.3: Vakuum-Verbot: Jeder Checker nennt seine POSITIV-Kontrolle
  (welcher Satz MUSS da sein, damit "nichts gefunden"456 kein Freifahrtschein ist).
  B4 wird der Referenzfall fuer diese Regel.

## BLOCKED_UNTIL
- M7-Umbau (echter Daemon, echter State) + M8.1–M8.3. Echter RUN erst danach.

## NEXT
M9 (Konvergenz: ein NEXT, keine Duplikate, keine neue Arbeit ohne Tor).
