# User Acceptance W — Mehr-Nutzer / Mehr-Geräte / Identität (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: F/B/H-nah (Permissions/Entscheidungs-Nachweis/Privacy) — die
Single-User-Annahme steht nirgends, aber der Pilot plant 5 Personen.

## USER_PROBLEM

Als Nutzer weiß ich nicht: sieht mein Pilot-Kollege meine Goals? Sehe ich
auf Gerät B, was Gerät A angestoßen hat? Und wenn jemand Resume drückt —
woher weiß ich, WER das war? "Ein Key für alles" ist keine Antwort auf
diese Fragen.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- Auth = ein Bearer-Key (`COURIER_API_KEY`) + ein Verifier-Key
  (`server/app.py:21-44`). Kein Nutzer, keine Session, kein Gerät, keine
  Rolle, kein Mandant — null Treffer für owner/tenant/user_id/created_by/
  decided_by/session/login/role in `server/` (einzig: fachfremdes
  `resource_owners` in demo_state.json).
- Wer den Key hat, sieht und darf alles: alle Goals (`/goals/<id>` ohne
  Ownership-Prüfung, `:154-162`), alle Worker, alle Walls, Claim, Result,
  Resume, Reclaim. Goals speichern keinen Ersteller (kein created_by),
  Resume-Entscheidungen keine Identität (B5 fordert wer/was/wann — das
  "wer" existiert nicht).
- Verifier-Unabhängigkeit = reine String-Ungleichheit
  (`verifier_id != worker_id`, `:482`). Ob hinter zwei IDs zwei
  verschiedene Akteure stehen, prüft niemand — Selbst-Zertifizierung mit
  zweitem String ist technisch möglich, nur per Policy verboten.
- BEFUND W-a (Pilot-Bruch vorprogrammiert): Die Readiness-Declaration
  plant eine "initial 5-person pilot cohort" — auf einem System ohne
  Nutzer-Trennung, ohne Ownership, ohne Entscheidungs-Attribution.
  Fünf Menschen, ein Key-Raum, keine Zurechenbarkeit.
- BEFUND W-b (Mehr-Geräte = Geister-Sitzungen): Gleicher Key auf zwei
  Geräten = gleiche Sicht, kein Sitzungs-Begriff, kein "andere Sitzung
  aktiv"-Hinweis, keine Konflikt-Handhabung (JSON last-write-wins).
  Zwei Resume-Klicks auf zwei Geräten: letzter gewinnt, erster erfährt
  nichts.
- Positiv: Die Lücke ist klein und explizit machbar — Single-User-Betrieb
  ist heute legitim, solange er DEKLARIERT ist statt implizit.

## ACCEPTANCE_REQUIREMENT

- W1: Single-User-Deklaration (sofort, Doku): "Diese Prep-Phase ist
  Single-User: Ein Key = ein Bediener. Key-Sharing zwischen Personen
  ist unzulässig, weil Entscheidungen sonst nicht zurechenbar sind."
  Steht an Onboarding (F) und B-Fläche, bis W2–W4 umgesetzt sind.
- W2: Pilot-Regel für 5 Personen (vor Cohort-Start, Spec-Owner): Entweder
  getrennte Instanzen/Keys pro Pilot-Nutzer mit getrennten Goals —
  oder explizite Shared-Pilot-Regel (alle sehen alles, Resume nur nach
  Absprache, Bruch wird als Pilot-Risiko protokolliert). Kein dritter
  Weg ("einfach teilen und hoffen").
- W3: Entscheidungs-Attribution (Prep-Schema, dann Code): Jede
  Human-Entscheidung (Resume, Wall-Antwort, ABANDONED nach O3, Löschung
  nach N4) persistiert wer/was/wann/auf-welche-Evidenz (B5). Das "wer"
  ist mindestens Key-Label + Gerät-Label, sobald Identitäten existieren:
  Nutzer-ID.
- W4: Spätere Mehr-Nutzer-Regeln (Prep, kein Bau): Ownership pro Goal
  (created_by), Sichtbarkeits-Regel (eigene vs. alle), Verifier-Bindung
  an echte Identitäten (statt String-Ungleichheit). Kein Ausbau vor
  Pilot-Signal — aber die Lücke bleibt als W-a-Protokoll offen.
- W5: Mehr-Geräte-Hinweis: Aktive Nutzung desselben Keys von zwei Stellen
  wird sichtbar ("letzte Aktion von <Gerät-Key-Label> um <Zeit>"), sobald
  Labels existieren. Bis dahin warnt W1 vor simultanem Zugriff.

## MISSING_SYSTEM_SUPPORT

- Keine Identitäten, keine Ownership, keine Attribution, keine Sitzungen.
- Keine Mandanten-Trennung, keine Konflikt-Erkennung.
- Keine Pilot-Nutzer-Regel (W2-Entscheidung ausstehend).

## PREPARABLE_NOW

- Dieses Dokument (W1–W5 + Befunde W-a/W-b).
- W1-Wording als sofortige ehrliche Onboarding-Regel.
- W2-Entscheidungs-Vorlage an Spec-Owner (getrennt vs. shared, mit
  Risiko-Protokoll).
- W3-Attributions-Schema-Entwurf (Felder: decision_id, actor_label,
  decided_at, wall_id/goal_id/task_id-Refs, evidence_refs, rationale).

## BLOCKED_UNTIL

- Spec-Owner entscheidet W2 vor Cohort-Start (echter Blocker, kein Prep).
- Identitäten/Attribution erst nach Pilot-Signal (Runtime-Owner).

## NEXT

X (Migrations-/Versions-Ehrlichkeit): was passiert mit meinen Goals beim
Update — welche State-Version gilt, was wird migriert, was verworfen?
(G definiert LKG; X definiert den Weg von LKG zu Neu.)
