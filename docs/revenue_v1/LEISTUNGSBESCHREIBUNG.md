# Leistungsbeschreibung: GitHub Actions Safety Baseline (Revenue V1)

## Sie bekommen
- Prüfung der GitHub-Actions-Workflows (`.github/workflows/`) **eines öffentlichen** GitHub-Repos an **einem festen Commit-SHA** (40 Zeichen).
- Bericht als `report.md` und `report.json` mit SHA-256 jeder geprüften Datei und Commit-SHA, damit nachvollziehbar ist, was geprüft wurde.
- Geprüfte Punkte: fehlender `timeout-minutes`, fehlender `permissions`-Block bzw. `write-all`, fehlender `concurrency`-Block, Self-hosted-Runner, `git push` im Workflow.
- Manuelle Durchsicht durch einen Menschen vor Auslieferung.

## Ablauf und Dauer
1. Sie nennen Repo + SHA. 2. Automatischer Lauf (Minuten). 3. Menschliche Prüfung. 4. Auslieferung an die vereinbarte Adresse. Zielzeit: innerhalb von 2 Werktagen nach Eingang von Repo und SHA (Festlegung offen, siehe MISSING).

## Voraussetzungen
Nur öffentliche Repos. Keine Zugangsdaten, kein Schreibzugriff, keine Codeausführung bei Ihnen.

## Nicht enthalten / nicht garantiert
- Kein Penetrationstest, keine Compliance-Zertifizierung, keine vollständige Sicherheitsgarantie.
- Kein Prüfen von Anwendungscode, Abhängigkeiten, Secrets, Actions-Pinning, `pull_request_target`, Script-Injection (Stand heute nicht im Regelwerk).
- Fehlende Befunde bedeuten nicht, dass die Workflows sicher sind.
- Keine Fixes/PRs im Kundenrepo.
