# User Acceptance T — Anzeige-Vokabular / Glossar-Disziplin (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: Querschnitt (zieht die Vokabular-Regeln aus A2/B1/C2/K2/P1/Q3
aufs ganze Produkt: kein Freitext-Status, kein totes Wort, kein Leak).

## USER_PROBLEM

Als Nutzer sehe ich Wörter wie ACTIVE, DISPATCHED, RESULT_READY,
RECONCILED, PENDING, STALE, VERIFIED — teils in Anzeigen, teils in Logs.
Welche bedeuten was für MICH? Welche sind intern? Und welche existieren
überhaupt noch? Heute ist jede Anzeige ein Ratespiel mit wechselndem
Wortschatz.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- Server-Vokabular (tatsächlich geschrieben): Goals ACTIVE/DONE/BLOCKED;
  Tasks/Steps QUEUED/DISPATCHED/RESULT_RECEIVED/RECONCILED/
  FAILED_VERIFICATION/FAILED_TERMINAL/HUMAN_REQUIRED/PENDING
  (`server/app.py`: :107, :115, :200, :332, :379-389, :434, :446, :504-510).
- Anzeigen-Mappings existieren als Spec: 01 (4 Nutzer-Zustände), A2
  (Phasen), B1 (Wall-Klassen), C2 (Retry-Verdikte), K2 (Frische), P1
  (Claim-Gründe), Q3 (Kapazitäts-Gründe), E-Flags. Unverbunden nebeneinander.
- ABER — Befund T-a (totes Wort im lebendigen Guard): `register`
  prüft `task.status not in ["VERIFIED", "HUMAN_REQUIRED"]` (`:199`),
  aber `"VERIFIED"` wird in `server/` + `scripts/` NIRGENDS geschrieben
  (einzige Treffer: fachfremde Sync-/Kurator-Skripte). Der Guard meint
  faktisch "≠ HUMAN_REQUIRED" — das Wort VERIFIED ist totes Vokabular
  im aktiven Codepfad.
- Befund T-b (Falle ohne Ausgang, ungemappt): `register` schreibt
  `task.status = "PENDING"` bei Worker-Amnesie (`:200`). Aber: Claim
  bedient nur QUEUED-Heads (`:275`), Resume lehnt alles außer
  HUMAN_REQUIRED/FAILED_VERIFICATION/FAILED_TERMINAL ab (`:531`).
  PENDING steht in keinem Anzeige-Mapping (01 kennt es nicht), und sein
  regulärer Ausgang ist aus dem Code nicht ersichtlich. Belegt
  geschrieben, nirgends erklärt, Ausgang unklar.
- Befund T-c (Vokabular-Leak): Daemon-interne `worker_phase`-Werte
  (CLAIMED/STARTED/RESULT_READY/RECOVERY_BLOCKED), Slot-Zustände
  (READY/RUNNING/IDLE/BACKOFF) und Bridge-Dateinamen (RESULT_READY)
  sickern in Logs/Anzeigen durch — ohne Glossar, ohne
  "intern, für dich bedeutungslos"-Markierung. Der Nutzer deutet
  Interna als Versprechen ("READY heißt bereit für mich?").

## ACCEPTANCE_REQUIREMENT

- T1: Geschlossenes Anzeige-Vokabular: Jedes Wort, das der Nutzer sieht,
  steht im Glossar mit (Bedeutung, Quelle, mögliche Folgezüge).
  Was nicht im Glossar steht, wird nicht angezeigt — Interna werden
  gemappt (01-Regel) oder als `(intern)` markiert, nie roh durchgereicht.
- T2: T-a wird dispositioniert (Runtime-Owner): VERIFIED entweder als
  echten Status einführen (mit Schreiber + Mapping) oder aus dem Guard
  entfernen. Totes Wort im Guard ist ab Annahme verboten.
- T3: T-b wird dispositioniert (Runtime-Owner): PENDING erhält einen
  belegten Ausgang (Claim- oder Resume-Pfad) + Anzeige-Mapping — oder
  wird durch einen gemappten Status ersetzt. Status ohne Ausgang und
  ohne Anzeige ist ab Annahme verboten.
- T4: Leak-Regel: worker_phase, Slot-States, Bridge-Dateinamen und alle
  künftigen Interna erscheinen in Nutzer-Flächen nur gemappt auf T1-Wörter.
  Roh-Logs dürfen Interna enthalten, müssen sie aber per Glossar-Anhang
  erklärbar machen.
- T5: Vokabular-Änderung ist Spec-Änderung: Neue/veränderte Status-Wörter
  brauchen Glossar-Eintrag + Mapping-Update + Invalidation-Check (D5),
  bevor sie einen Nutzer erreichen. Kein Freitext-Status je.

## MISSING_SYSTEM_SUPPORT

- Kein Glossar, keine Mapping-Tabelle Code-Status → Anzeige-Wort.
- T-a/T-b unentschieden (Code-Owner-Sache).
- Keine Leak-Prüfung (welche Interna erreichen heute Anzeigen/Logs).

## PREPARABLE_NOW

- Dieses Dokument (T1–T5 + Befunde T-a bis T-c).
- Glossar-Keim (aus belegtem Vokabular + 01/A2/B1/C2/K2/P1/Q3-Specs):
  Tabelle Wort → Bedeutung → Quelle → Nutzer-Folgezug. Als Doku-Anhang.
- T-a/T-b-Notizen an Runtime-Owner (ein-Zeilen-Entscheidungen mit
  großer Anzeige-Wirkung).

## BLOCKED_UNTIL

- Runtime-Owner dispositioniert T-a/T-b.
- Glossar-Vollständigkeit erst mit Pilot-Vokabular (echte Nutzer-Wörter).

## NEXT

U (Fehler-Texte/Sprach-Disziplin): was steht WÖRTLICH da, wenn etwas
schiefgeht — jede Fehlermeldung mit Klasse + Verdikt + Next (C1) statt
roher Exceptions. (T liefert die Wörter; U liefert die Sätze.)
