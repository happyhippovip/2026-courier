# User Acceptance Z — Serien-Stand / Übergabe-Protokoll (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Lesend erstellt (Shell down: kein Prozess-/Port-/Test-Nachweis
aus diesem Fenster; alle Befunde statisch an Code + Docs belegt).

## Serien-Stand (25 Dokumente)

| Doc | Frage des Nutzers | Kern-Regel |
|---|---|---|
| A Status/Phase | Was macht Courier gerade? | Eine Statuszeile: Phase + State + SHA + Next |
| B Braucht-dich | Was wartet auf mich? | Explizite NEEDS_YOU-Liste mit Wall-Klasse |
| C Failure/Retry | Darf ich Retry/Restart? | Retry-Verdikt an jeder Failure-Anzeige |
| D Proof | Was wurde wirklich verifiziert? | Proof-Level + SHA + Evidenz-IDs an jedem Grün |
| E Progress/Next | Wie weit, was als Nächstes? | Prozent nur aus verifizierten Gates |
| F Onboarding/Permissions | Welche Daten/Rechte? | Permission-Manifest + gemessene Setup-Zeit |
| G Update/Rollback | Komme ich zurück? | LKG-Record + ein Endzustand pro Update |
| H Support/Privacy | Was schicke ich dem Support? | Bundle-Manifest + Redaktionsliste |
| I Pilot-Feedback | Zählt mein Feedback? | Feedback-Record + Messmethoden, kein Auto-Unlock |
| J Product-Shell-Gate | Wann gibt es UI? | Tor: GREEN + J2 + expliziter Unlock-Eintrag |
| K Liveness | Hängt es oder arbeitet es? | Frische-Stufen + Watchdog-Nachweis |
| L Kosten | Was kostet der Lauf? | Spend-Zähler + Cap + Deferral-Sichtbarkeit |
| M Benachrichtigung | Erfahre ich es ohne Pollen? | Poll-Vertrag + Gesehen-Status |
| N Daten/Löschung | Wo liegen Daten, wie weg? | Manifest + Wachstums-Anzeige + Lösch-Regel |
| O Fertig-Zertifikat | Woran erkenne ich FERTIG? | Zertifikat + ABANDONED statt ewig-BLOCKED |
| P Queue/Fairness | Warum wartet meine Aufgabe? | Claim-Gründe + sichtbare Bedien-Reihenfolge |
| Q Kapazität | Welche Worker sind da? | Kapazitäts-Zeile + Capability-Gap-Alarm |
| R Failover | Wer übernimmt bei Ausfall? | GQ44 dispositionieren + Übernahme-Protokoll |
| S Selbsttest | Womit fange ich an? | Ein Hello-Goal + Messung statt Literale |
| T Vokabular | Was bedeuten die Wörter? | Geschlossenes Glossar, kein Leak |
| U Fehler-Texte | Was tue ich jetzt? | Fünf-Teile-Satz + keine rohen Exceptions |
| V Uhren | Nach welcher Uhr? | Monotonic-Intervalle + ISO-mit-Zone + Quelle |
| W Identität | Wer sieht/darf was? | Single-User-Deklaration + W2 vor Cohort-Start |
| X Migration | Was wird aus Goals beim Update? | State-Version + Backup + Forward-Guard |
| Y Umzug | Was zieht aufs neue Gerät mit? | Kein Leer-Start + host-eindeutige IDs + Checkliste |
| 01 Grandma-Mapping | Arbeitet/braucht/fertig? | 4-Zustands-Ableitung aus State |
| 02 Artifact-Receipt | Ist das Ergebnis echt/vollständig? | Quittung mit Hash + Größe + Integrität |

## Offene Owner-Entscheidungen (nicht dieses Fenster)

Spec-Owner: 5-vs-15-Minuten (F3/I5/S-c, auch Code-Fakt S-b/:13);
GQ44 streichen-vs-bauen (R2); Anzeigen-Sprache (U5); Glossar-Abnahme (T).
Runtime-Owner: Frische-Urteil + Watchdog-Liveness (K); Deferral-Default
`unknown` + CostGate-Anbindung (L-a/L-c); Claim-Gründe (P1); VERIFIED/
PENDING dispositionieren (T-a/T-b); Timestamps (O-a); Exception-Leak
stopfen (U-b); monotonic + Sprung-Hinweis (V); State-Version/Migration
(X); Leer-Start-Hinweis + ID-Regel + Server-Default (Y).
Run-Prep-Owner: Watchdog-Precondition (K); Uhren-Precondition (V4);
Y4-Checkliste abnehmen.
Plan-/Gate-Owner: D3-Notizen (51-vs-57, SCOPE_OK=NO); W2
Cohort-Regel VOR Pilot-Start (Blocker); N-b Fristen; E5 Beacon
(fixen/deprecieren); Gate-Datei-Encoding (A-Befund: GATE_STATE_CURRENT.md
nicht UTF-8-lesbar — auch 01 + PILOT_READINESS_DECLARATION.md betroffen).

## Mess-Lücken bis Pilot (nichts davon ist heute messbar)

T_setup (eine Zahl fehlt), HIPG-Zählung, RSR/NDR aus State-Ableitung,
Spend (kein Zähler), TTUR, Support-Aufwand, Uhren-Offsets, Retry-Historie.
Erste echte Messwerte: frühestens Mac-Canary, vollständig erst Pilot.

## Nächster Operator: Einstieg

1. Gate-/Queue-Files lesen (A-Stand prüfen). 2. Diese Tabelle gegen
Offen-Liste prüfen (was wurde entschieden/gebaut). 3. Mit ersten
Pilot-Daten: A–Y-Kriterien gegen echte Messwerte halten, Diskrepanzen an
Owner zurückgeben. 4. Kein neuer Scope ohne Freigabe (J4-Reihe ist
vollständig; neue Docs nur bei neuer echter Nutzer-Lücke).
