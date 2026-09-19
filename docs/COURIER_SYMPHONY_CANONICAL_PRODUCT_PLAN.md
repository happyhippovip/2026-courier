# COURIER SYMPHONY — KANONISCHER PRODUKTPLAN

**Status:** Kanonische Arbeitsgrundlage bis zur nächsten ausdrücklich freigegebenen Revision  
**Stand:** 2026-09-19  
**Prinzip:** Finish vor Ausbau  
**Steuerungsregel:** **Critical Path · Later · Non-Goal**  
**Beweisregel:** **No Evidence -> No PASS**  
**Aenderungsregel:** **No Authorization -> No Scope Expansion**

## Externes Kernversprechen

**„Courier bringt dich am naechsten Tag genau dort weiter, wo du aufgehoert hast.“**

Dieses Versprechen ist die externe Produktbotschaft. Interne Begriffe wie Ledger, Attempts, Evidence, Autonomy Grade oder Earned Autonomy werden nur gezeigt, wenn sie fuer Vertrauen oder Bedienung wirklich helfen.

## 0. Steuerungsmodell

Der Plan trennt:
1. **Gate-Status** — wie weit ist der Beweis?
2. **Arbeitsfreigabe** — darf daran aktuell gearbeitet werden?
3. **Prioritaet** — ist es der aktuelle Critical Path?

Arbeitsfreigaben:
- **ACTIVE:** aktueller Critical Path.
- **ACTIVE_BOUNDED:** nur Arbeit, die das vorherige Gate nicht destabilisiert.
- **PREP_ONLY:** Tests/Fixtures/Pläne vorbereiten; Gate noch nicht beanspruchen.
- **NON_CODE_PREP:** Pilotkandidaten, Zahlungsweg, Datenschutz und Baseline vorbereiten.
- **LOCKED:** nicht bauen.

Status wird durch Evidenz geaendert, nicht durch Einschaetzung.

## 1. Produktziel

Courier Symphony fuehrt begonnene Arbeit zuverlaessig, nachvollziehbar und wiederaufnehmbar weiter.

Der Nutzer definiert ein Ziel. Courier speichert dauerhaft mindestens:
- Goal
- Goal Contract
- Tasks
- Dependencies
- Zustaendigkeiten
- Attempts
- Executions
- Results
- Evidence
- Entscheidungen
- Fortsetzungszustand

Courier setzt autorisierte Arbeit selbststaendig fort, ohne dass der Nutzer fortlaufend Prompts kopiert, Ergebnisse zwischen Agenten verschiebt, Worker auswaehlt, Anbieter manuell wechselt, Status korrigiert oder „weiter“ schreibt.

Courier stoppt nur an einer echten Grenze:
- menschliche Entscheidung
- Geldfreigabe
- Berechtigung
- Sicherheit
- rechtliche Freigabe
- nicht aufloesbarer Zielkonflikt
- ausdruecklich verlangte menschliche Kontrolle

**Kernnutzen:** nachweisbare, wiederaufnehmbare Autonomie ueber Tools, Worker, Provider und Sessions hinweg.

## 2. Internes Wettbewerbsverstaendnis

Nur intern:

**„Nicht Codex oder Claude Code im Hintergrund, sondern tool-uebergreifende, beweisbare Autonomie mit Ledger und pruefbaren Autonomy Grades.“**

Der Wettbewerbsvorteil ist nicht die Anzahl der Modelle. Courier weiss nachweisbar, was passiert ist, was als Naechstes passieren darf und ob es nach einem Abbruch korrekt weitergeht.

## 3. Verbindliche Reihenfolge

1. Trusted Ledger
2. Reliable Courier Motor
3. Zero-Human A->B
4. Restart & Recovery
5. Bezahlter Minimalpilot
6. Pilotentscheidung
7. Product Shell
8. Wiederholbaren Vertrieb beweisen
9. Packaging und Updates
10. Connector-/Plattformausbau

Ein spaeteres Gate darf ein frueheres Gate niemals durch UI, Dokumentation, Simulation, Selbstbericht oder zusaetzliche Features ersetzen.

## 4. Gate 1 — Trusted Ledger

Courier besitzt dauerhaft rekonstruierbare Wahrheit ueber Auftrag, Goal Contract, Task, Worker, Attempt, Execution, Result, Evidence, Verifikation, Akzeptanz, Ablehnung und UNKNOWNs.

Pflicht:
- stabile Goal-/Task-/Attempt-/Execution-/Result-ID
- eindeutige Result-Bindung
- idempotente Result-Verarbeitung
- identische Duplicates erzeugen keine Doppelwirkung
- widerspruechliche Duplicates werden abgelehnt
- stale Results ueberschreiben keine aktuelle Wahrheit
- Persistenz ueberlebt Restart
- Reconciliation ist idempotent
- unbelegte Historie bleibt UNKNOWN
- Provenienz wird nicht nachtraeglich erfunden

Ein PASS gilt nur fuer einen konkreten Candidate mit Source SHA, Tree/Fingerprint, relevanter Konfiguration, erforderlicher Loaded-Runtime-Identitaet und Acceptance-Evidence.

**PASS nur wenn:** exakter Candidate gebunden, Ledger-Fingerprint definiert, relevante Tests erfolgreich, erforderliche Runtime-Bindung vorhanden, keine gateverletzenden UNKNOWNs und erforderliche unabhaengige Abnahme vorhanden.

Danach: **LEDGER_FROZEN = YES**.

## 5. Goal Contract — harter Pruefanker

Vor autonomer Ausfuehrung bestaetigt der Mensch einmal den Goal Contract:
- gewuenschtes Endergebnis
- erlaubter Scope
- nicht erlaubter Scope
- relevante Constraints
- Akzeptanzkriterien
- erforderliche Evidenzklasse
- Side-Effect-Grenzen
- Human-/Money-/Safety-Gates

Courier darf daraus Task-Vertraege ableiten. Diese muessen auf den bestaetigten Goal Contract rueckfuehrbar sein. Courier darf zerlegen, aber Erfolgsvoraussetzungen nicht eigenmaechtig veraendern.

Erfordert neue Erkenntnis eine Erweiterung: **HUMAN_CONFIRMATION_REQUIRED**.

Fehlt ein ausreichender Pruefanker: **NOT_VERIFIABLE**, niemals automatisch PASS.

## 6. Unabhaengige Verifikation

Bevorzugte Reihenfolge:
1. deterministische Pruefung
2. reproduzierbarer automatisierter Test
3. unabhaengiger Reviewer
4. physischer End-to-End-Beweis

Ein AI-Reviewer ist nicht noetig, wenn ein deterministischer Test das Kriterium vollstaendig beweist.

Wenn ein unabhaengiger Reviewer erforderlich ist:
- nicht der Writer
- nicht dasselbe Modell
- nicht derselbe Arbeitskontext
- Writer-Selbsturteil ist keine unabhaengige Evidenz

## 7. Gate 2 — Reliable Courier Motor

Verbindlicher Pfad:

**Result -> persistieren -> validieren -> gegen Goal-/Task-Contract pruefen -> reconcile -> Dependencies aktualisieren -> READY neu berechnen -> Eligibility pruefen -> Worker auswaehlen -> dispatchen**

Regeln:
- kein menschlicher Continue-Befehl im Normalpfad
- Queue leer = IDLE
- IDLE erzeugt keine Arbeit
- kein AI-Polling
- kein Tight Polling
- Retries begrenzt
- Provider-Ausfall blockiert nur betroffene Arbeit
- unabhaengige READY-Arbeit darf weiterlaufen
- ein logischer Attempt hat hoechstens eine aktive externe Execution
- ein mutable Scope hat hoechstens einen aktiven Writer
- UNKNOWN Execution wird reconciled, nicht blind neu gestartet

## 8. Gate 3 — Zero-Human A->B

Physisch beweisen:

**ONE GOAL -> Task A -> realer Worker -> reales Result A -> automatische Verifikation -> automatische Reconciliation -> Task B READY -> automatische Worker-Auswahl -> automatischer Dispatch -> reales Result B -> DONE**

Pflichtmetrik: **HUMAN_RELAY_COUNT = 0**.

Nicht zulässig: Prompt kopieren, „Weiter“, Worker manuell waehlen, Result manuell uebertragen, Status manuell setzen, B manuell starten oder Result manuell injizieren. Fixtures duerfen vorbereiten, aber Gate 3 nicht beweisen.

## 9. Gate 4 — Restart & Recovery

Mindestens testen:
- Courier-Prozessrestart
- Worker verschwindet
- Result persistiert, Reconcile fehlt
- READY vor Dispatch
- Dispatch erfolgt, Result fehlt
- Provider temporaer nicht verfuegbar
- stale Result
- identisches Duplicate Result
- widerspruechliches Duplicate Result

Fuer jedes Szenario:
- kein Task verloren
- kein akzeptiertes Result verloren
- keine stille Doppelwirkung
- stale Daten ueberschreiben keine aktuelle Wahrheit
- Zustand bleibt ehrlich
- naechste zulaessige Aktion ist deterministisch

**RSR = bestandene Restart-Szenarien / definierte Restart-Szenarien. Ziel: 100 %.**

## 10. Proof Card

Pflichtfelder:
- Goal-ID
- Goal-Contract-Fingerprint
- Task-ID
- tatsaechliches Result
- Akzeptanzkriterien
- Evidence-IDs
- Pruefstufe
- Source-/Build-/Runtime-Fingerprint
- Covered Surface
- UNKNOWNs
- Human Interventions
- Revalidation-Status

Keine lange Agentenprosa.

## 11. Proof Levels

- **P0 — SELF_REPORTED:** Worker behauptet Erfolg.
- **P1 — DETERMINISTIC_TESTED:** deterministische Evidenz vorhanden.
- **P2 — INDEPENDENTLY_VERIFIED:** unabhaengige Pruefung vorhanden.
- **P3 — PHYSICAL_E2E:** realer End-to-End-Pfad physisch bewiesen.

Ein hoeherer Proof Level ersetzt keine fehlenden Akzeptanzkriterien.

## 12. Autonomy Grade

- **A0 — MANUAL:** menschlicher Relay-Schritt erforderlich.
- **A1 — SINGLE_STEP:** ein Task kann ohne Relay abgeschlossen werden.
- **A2 — AUTO_CONTINUE:** Result fuehrt automatisch zur naechsten zulaessigen Arbeit.
- **A3 — ZERO_RELAY_CHAIN:** mehrstufige reale Arbeit mit HUMAN_RELAY_COUNT=0.
- **A4 — RECOVERY_RESILIENT:** A3 plus vollstaendige definierte Restart-Matrix.

Jeder Grade gilt nur fuer seine konkrete Covered Surface.

## 13. Covered Surface und Revalidation

Covered Surface bindet Module, relevante Konfiguration, externe Vertraege, Connector-Vertraege, Contract-Fingerprint und notwendige Acceptance Tests.

Aendert sich ein entscheidungsrelevanter Bestandteil: **REVALIDATION_REQUIRED**. Der alte Grade wird bis zur erfolgreichen Revalidation nicht als aktuell gueltig angezeigt. Aenderungen ausserhalb der Covered Surface entwerten ihn nicht automatisch.

## 14. Gate 5 — Minimaler Pilot

Der Pilot kommt vor einer schoenen Product Shell.

Sichtbar benoetigt werden nur:
- **Arbeitet**
- **Braucht dich**
- **Fertig**
- Proof Card
- Proof Level
- Autonomy Grade
- naechste Aktion

Nicht erforderlich: grosses Home, umfangreiche Navigation, Marketplace, Update-UI, Enterprise-Admin oder grosses Dashboard.

## 15. Pilot-Installation

Ein automatischer Installer ist keine Pilotvoraussetzung. Erste Piloten duerfen begleitet, manuell eingerichtet und persoenlich onboarded werden.

Dieser Aufwand wird als **SETUP_MINUTES_PER_PILOT** gemessen. Manuelles Setup darf im Pilot existieren, aber nicht als skalierbarer Endzustand ausgegeben werden.

## 16. Pilot mit echten Menschen

Jeder Pilot besitzt klares Goal, menschlich bestaetigten Goal Contract, dokumentierte Baseline, Pilotdauer, vereinbarten Preis und Daten-/Permission-Scope.

Der Pilot testet ausschliesslich das Kernversprechen:

**„Courier bringt dich am naechsten Tag genau dort weiter, wo du aufgehoert hast.“**

## 17. Pilotmetriken

**HIPG = notwendige menschliche Fortsetzungseingriffe / abgeschlossene oder beendete Goals. Ziel: < 1,0.**

Normale initiale Goal-Bestaetigung wird nicht als Relay gezaehlt. Echte HUMAN_REQUIRED-Entscheidungen werden separat erfasst.

**RSR = bestandene Restart-Szenarien / ausgefuehrte definierte Restart-Szenarien. Ziel: 100 %.**

**NDR — Next-Day Return:** Nutzer verwendet Courier am Folgetag aus eigenem Interesse erneut oder fuehrt seinen begonnenen Goal-Pfad fort.

Erste 5er-Kohorte:
- **3–5 / 5 -> GO**
- **2 / 5 -> ITERATE ONCE**: genau ein begrenzter Iterationszyklus, danach neue Kohorte
- **0–1 / 5 -> REVIEW CORE PROMISE**

Fuenf Piloten sind **ein Entscheidungssignal, kein Marktbeweis**.

## 18. Zahlung im Pilot

Der erste Umsatz wartet nicht auf Billing-Plattform oder Installer.

Orientierung: **49–99 EUR Setup-/Pilotgebuehr**.

Preis ist ein Experiment. Zu messen:
- PAYMENT_YES/NO
- tatsaechlicher Betrag
- Setup-Aufwand
- Wiederkehr
- Support-Aufwand
- Providerkosten

Feedback ohne Zahlungsbereitschaft ist schwaechere Evidenz als eine echte Zahlung.

## 19. Pilot-Voraussetzungen

Vor dem ersten bezahlten externen Pilot ausreichend klaeren:
- einfacher Zahlungsweg
- verarbeitete Nutzerdaten
- Speicherort
- beteiligte Provider
- Berechtigungen
- Aufbewahrung und Loeschung
- notwendige Datenschutzhinweise
- organisatorische DSGVO-Pflichten
- steuerliche/gewerbliche Voraussetzungen

Der Produktplan ersetzt keine individuelle Rechts- oder Steuerberatung.

## 20. Parallelspur ab sofort

Waehren Gate 1–4 darf Nicht-Code-Arbeit parallel laufen:
- Pilotkandidaten ansprechen
- Kandidatenliste fuehren
- Baseline-Fragebogen vorbereiten
- Pilotgespraech vorbereiten
- Zahlungsweg vorbereiten
- Datenfluss inventarisieren
- Pilotunterlagen vorbereiten
- Pilotpreis testen

Nicht erlaubt: grosse Marketingkampagne, Product Shell vorziehen, Billing-Plattform bauen oder Features aus ungeprueften Interviewwuenschen bauen.

## 21. Gate 6 — Product Shell

Nur nach positivem Pilotsignal.

Zielpfad:

**Connect -> Goal -> Arbeitet -> Braucht dich -> Fertig**

Optional: Details oeffnen. Interne Komplexitaet bleibt intern.

## 22. Gate 7 — Packaging / Updates

Erst nach Core- und Pilotnachweis.

Spaeter erforderlich:
- reproduzierbarer Build
- Source-Identitaet
- Build-Identitaet
- Loaded-Runtime-Identitaet
- Single Instance
- sicheres Update
- Rollback
- Last Known Good
- State-Kompatibilitaet
- keine verlorene laufende Arbeit

## 23. Non-Goals / Scope Freeze

Bis zum positiven Pilotnachweis nicht bauen:
- Marketplace
- vollstaendige Billing-Plattform
- Enterprise-Admin
- Kubernetes
- Multi-Region
- grosses Dashboard
- vollstaendige Social-Automation
- Spieleplattform
- Millionen-Task-Cannon als Produktionsziel
- zusaetzliche Ledger
- zusaetzliche Scheduler ohne belegte Luecke
- zusaetzliche Watchdogs ohne belegte Luecke
- perfekte Desktop-Shell
- App-Store-Optimierung
- spekulative Enterprise-Funktionen

**Default = nicht bauen.** Nicht im Plan -> keine Implementierung ohne ausdrueckliche Freigabe.

## 24. Agenten-Grenzen

Agenten duerfen Code implementieren, Tests ausfuehren, Evidenz erzeugen, Reviews durchfuehren, Fehler klassifizieren, dependency-sichere autorisierte Arbeit fortsetzen und Metriken auswerten.

Agenten duerfen nicht eigene Rechte/Scope/Geldgrenzen/Sicherheitsgrenzen erweitern, Kundendaten unautorisiert freigeben, ungefragt publizieren, UNKNOWN zu PASS machen, Proof Levels erfinden, Erfolg erfinden oder neue Arbeit nur zur Beschaeftigung erzeugen.

## 25. Gate-Timeboxes

Timeboxes sind **Review-Grenzen**, keine kuenstlichen PASS-Deadlines.

Default:
- Gate 1–4: 5 Arbeitstage bis zwingender Scope-/Blocker-Review
- Pilotvorbereitung: 5 Arbeitstage fuer Minimalvoraussetzungen
- erste Pilotkohorte: 10–14 Kalendertage
- erste Product Shell: maximal 10 Arbeitstage bis Review

Ist ein Gate nach der Timebox nicht PASS: stoppen, ersten kausalen Blocker benennen, Scope pruefen, nicht kausale Arbeit entfernen, Evidenzlage pruefen und entscheiden: weiter, enger schneiden, blockieren oder Ansatz aendern.

## 26. Gate-Zustaende

Erlaubt:
- NOT_STARTED
- PREP_ONLY
- IN_PROGRESS
- BLOCKED
- REVALIDATION_REQUIRED
- PASS
- FROZEN

Nur PASS erlaubt den regulaeren Uebergang. Nur FROZEN beendet regulaere Arbeit am abgeschlossenen Gate. „Fast fertig“ ist kein Zustand.

## 27. Evidence Invalidation

Ein bestehender PASS wird ungueltig, wenn Covered Surface relevant geaendert wurde, Candidate gewechselt hat, Runtime nicht mehr zum akzeptierten Build passt, Akzeptanzvertrag geaendert wurde, relevante Konfiguration geaendert wurde oder vorherige Evidence nachweislich falsch/unvollstaendig war.

Dann: **REVALIDATION_REQUIRED**.

## 28. Definition von Core fertig

Core fertig bedeutet:
- Ledger PASS + FROZEN
- Motor PASS
- Result -> Verify -> Reconcile -> Next READY bewiesen
- A->B ohne Relay physisch bewiesen
- Restart-Matrix PASS
- Autonomy Grade mindestens A4 fuer den definierten Core-Scope
- Ressourcenbetrieb bounded
- keine Tight-Polling-Schleifen
- Proof Cards korrekt
- Covered Surface gebunden

Dann: **CORE_FREEZE**.

Danach Core-Aenderungen nur bei beobachtetem kausalen Defekt, Sicherheitsproblem, notwendiger Revalidation, realer Kundenanforderung oder nachgewiesenem wirtschaftlichem Vorteil.

## 29. Entscheidungsregel fuer jede neue Idee

**CRITICAL PATH:** Ohne diese Arbeit kann das aktuelle Gate nicht PASS werden -> jetzt bearbeiten.

**LATER:** Wertvoll, aber fuer das aktuelle Gate nicht erforderlich -> notieren, nicht bauen.

**NON-GOAL:** Verletzt Scope Freeze oder lenkt vom Kernversprechen ab -> nicht bauen.

Unklar -> nicht starten.

Technische Interessantheit, Agentenbegeisterung oder freie Rechenzeit machen eine Idee nicht zum Critical Path.

## 30. Kanonischer kritischer Pfad

**JETZT:** Ledger remote, exakt gebunden und unabhaengig schliessen.

Parallel ausschliesslich: Pilotkandidaten, Baseline, Zahlungsweg, Daten-/Compliance-Vorbereitung.

**DANACH:** Reliable Motor PASS.

**DANN:** Zero-Human A->B.

**DANN:** Restart-Matrix und A4.

**DANN:** Minimaler bezahlter Pilot.

**DANN:** HIPG, RSR, NDR, Zahlung und Supportaufwand auswerten.

**BEI POSITIVEM SIGNAL:** Product Shell.

**ERST DANACH:** Packaging, Updates, breitere Connectoren, skalierter Vertrieb.

## 31. Kanonische Stop-Regel

Arbeit wird beendet, wenn:
- aktuelles Gate PASS und anschliessend FROZEN ist
- kein dependency-sicheres autorisiertes Critical-Path-Item verbleibt
- echte menschliche Entscheidung erforderlich ist
- Permission-/Safety-/Money-Grenze erreicht wurde
- weitere Arbeit nur LATER oder NON-GOAL waere

**Kein Agent erfindet Arbeit, nur weil noch Zeit oder Compute verfuegbar ist.**

## 32. Produktprinzip

**Courier gewinnt nicht dadurch, dass es mehr Dinge gleichzeitig tut. Courier gewinnt dadurch, dass begonnene Arbeit morgen zuverlaessig, beweisbar und ohne menschliches Relay weitergeht.**

---

## Datenschutz-/Speicherhinweis

Persoenliche Zahlungs-, Konto-, Steuer- oder Identifikationsdaten gehoeren **nicht** in das oeffentliche Courier-Repository. Private Zahlungsdaten werden nur in dafuer vorgesehenen privaten Nutzerunterlagen verwaltet.
