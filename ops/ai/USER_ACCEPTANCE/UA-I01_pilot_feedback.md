# UA-I01 — Pilot-Feedback: Wann zaehlt meine Erfahrung als Signal?

Prioritaet: I (Pilot Feedback)
Stand: 2026-09-28, Quelle: Repo-Reads (kein RUN, kein Ledger)

## USER_PROBLEM
Ich soll Pilot-Feedback geben — aber was zaehlt als "positives Pilot-Signal"
(fuer die Product-Shell-Freigabe), was ist nur Meinung? Ohne Kriterien ist jedes
"lief gut" gleichzeitig alles und nichts.

## CURRENT_RUNTIME_TRUTH (belegt)
- `END_TO_END_FINISH_TO_PILOT_PLAYBOOK_2026-09-27.md`: PHASE 7 = erste
  5-Personen-Kohorte; PHASE 8 = Product Shell NUR nach positivem Pilot-Signal.
- `CRITICAL_PATH_SYNTHESIS.md:22`: HIPG-Metriken beobachten (Ziel: 0) — eine
  Definition von HIPG liegt im gelesenen Ausschnitt NICHT vor.
- Pocket-Ledger "Return-after-away": Die Demo ist: weggehen → zurueckkommen →
  Zusammenfassung (verifizierte Schritte, wartende, vermiedene, Braucht-dich?).
  Zahlen MUESSEN aus echtem State kommen.
- `PILOT_READINESS_DECLARATION.md` verlangt menschliche Autorisierung VOR
  Pilot-Start (UA-B01); ein Feedback-Schema existiert nicht.
- Heute laeuft nichts (Shell down, kein Server beobachtet) — jedes Signal waere
  derzeit leer.

## ACCEPTANCE_REQUIREMENT
UA-I01.1: Ein Pilot-Signal besteht aus: `reales Goal + Away-Return-Protokoll +
i/n verifizierte Schritte (aus State) + HIPG-Wert + GO/NO_GO + 1 Satz Begruendung`.
  Meinung ohne State-Beleg ist Kommentar, kein Signal.
UA-I01.2: Negativ-Signale zaehlen gleichwertig (NO_GO mit Beleg stoppt die
  Shell-Freigabe genauso wie fehlendes GO).
UA-I01.3: Sammelstelle ist benannt (Datei/Pfad + Format), Duplikate werden per
  Goal-ID dedupliziert, nicht per Bauchgefuehl.
UA-I01.4: Mindestens 1 vollstaendiger Away-Return-Zyklus pro Pilot-Teilnehmer,
  sonst `INSUFFICIENT_EVIDENCE`.

## MISSING_SYSTEM_SUPPORT
- Kein Feedback-Template, keine HIPG-Definition im Repo, keine Sammelstelle.
- Keine Away-Return-Protokoll-Vorlage.

## PREPARABLE_NOW
- Dieses Dokument + Signal-Kriterien + Template-Entwurf (1 Seite).
- Hinweis: Aktuell ist jedes Signal `INSUFFICIENT_EVIDENCE` (nichts laeuft).

## BLOCKED_UNTIL
- Pilot-Autorisierung durch Operator (Human-Gate, UA-B01).
- HIPG-Definition durch Owner + Sammelstellen-Entscheid.

## NEXT
UA-J01 (Product-Shell-Tor).
