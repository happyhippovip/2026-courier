# User Acceptance Q — Kapazität / Worker-Bestand / Fähigkeiten (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: A/E-nah (Status/Progress) + K-nah (Frische) — der Worker-Bestand
als Nutzer-Fläche: wer ist da, was kann er, ist er frei oder weg.

## USER_PROBLEM

Als Nutzer weiß ich nicht: welche Worker sind überhaupt da, was können sie
— und wartet meine Aufgabe auf einen Worker, den es gar nicht gibt? "Keine
Kapazität" und "falsche Kapazität" sehen heute beide aus wie: nichts passiert.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- `/workers` liefert Rohdaten: worker_id, platform, capabilities,
  last_seen (Epoch), available, current_task, cost_class, unregistered
  (`server/app.py:164-169,205-213`). Kein Urteil, keine Zusammenfassung.
- Unregister ist sticky: nur explizites Re-Register bringt einen Worker
  zurück (`:226-230`). `available=False` wird außerdem gesetzt bei Claim
  (`:336`), bei stale (`:425`) und bei Amnesie-Release; frei wird er bei
  Result (`:403-405`). Die Gründe für "nicht verfügbar" sind im State
  nicht unterscheidbar (belegt / stale-quarantäniert / explizit
  abgemeldet sehen gleich aus).
- ABER — Befund Q-a (ewiges Warten ohne Diagnose): Ein QUEUED-Head mit
  Target X und null registrierten Workern mit Capability X wartet für
  immer — kein "unbedienbar"-Signal, kein Capability-Gap-Hinweis. Der
  Claim-Match (`:279-283`, github/macos/windows/linux/antigravity) läuft
  ins Leere, der Nutzer sieht nur Stillstand.
- Befund Q-b (veralteter Bestand): Stale Worker (last_seen > 300 s) stehen
  weiter in `/workers` — mit `available=False` erst NACH Reclaim-Lauf
  (`:422-425`, braucht Watchdog, siehe K-a). Ohne Watchdog steht ein toter
  Worker als scheinbar-verfügbar im Bestand.
- Befund Q-c (keine Kapazitäts-Summe): "2 Worker da, 1 belegt, 0 mit
  mac-Fähigkeit" — diese Zeile existiert nirgends. `/status` zählt nur
  Worker insgesamt (`:83-92`).
- Positiv: Capabilities + Targets sind geschlossenes, kleines Vokabular —
  eine Gap-Analyse ist trivial ableitbar (Target-Menge der QUEUED-Heads
  minus Capability-Menge frischer Worker).

## ACCEPTANCE_REQUIREMENT

- Q1: Kapazitäts-Zeile (ableitbar aus heutigem State): "N Worker bekannt,
  F frisch (< 60 s), B belegt, S stale, G abgemeldet." Jede Zahl mit
  Worker-IDs belegbar. Kein Raten aus Rohdaten.
- Q2: Capability-Gap-Alarm: QUEUED-Head ohne frischen fähigen Worker →
  explizit "UNBEDIENBAR: kein <Target>-Worker (frisch) registriert",
  mit Handlungsoption (Worker starten/registrieren). Stillstand ohne
  Diagnose ist ungültig. (Q-a-Fix.)
- Q3: Nicht-verfügbar trägt einen Grund: BUSY (mit Task-Ref) /
  STALE (mit last-seen-Alter) / UNREGISTERED (mit Re-Register-Hinweis).
  Drei verschiedene Zustände, drei verschiedene Anzeigen. (Q-b/c-Fix.)
- Q4: Stale-Bestand wird gekennzeichnet, nicht versteckt: Worker mit
  last_seen > 300 s heißen STALE_OFFLINE — unabhängig davon, ob der
  Watchdog schon reclamiert hat. K-Frische und Q-Bestand widersprechen
  sich nie.
- Q5: Neu-Registrierung ist sichtbar: "Worker X (<Capabilities>) seit
  <Zeit> bereit" — der Nutzer sieht, dass seine Kapazitäts-Lücke (Q2)
  geschlossen wurde, ohne die Worker-Liste zu diffen.

## MISSING_SYSTEM_SUPPORT

- Keine Kapazitäts-Ableitung (Summe, Gaps, Gründe) im Runtime-Code.
- Kein UNBEDIENBAR-Signal, keine Gap-Analyse, keine Neu-Register-Notiz.
- `available`-Gründe nicht persistiert (nur Boolean).

## PREPARABLE_NOW

- Dieses Dokument (Q1–Q5 + Befunde Q-a bis Q-c).
- Gap-Regel-Entwurf (rein lesend): für jeden QUEUED-Head: frische Worker
  mit passender Capability suchen → 0 Treffer = Q2-Alarm.
- Q3-Grund-Ableitung aus heutigem State (current_task gesetzt = BUSY;
  unregistered-Flag = UNREGISTERED; last_seen > 300 s = STALE; sonst frei).

## BLOCKED_UNTIL

- Echter Worker-Bestand erst mit physischem RUN/Pilot (mehrere Worker,
  echte Capabilities).
- Runtime-Owner implementiert Kapazitäts-Sicht + Gründe.

## NEXT

R (Anbieterwechsel/Ausfall): was passiert, wenn ein Provider ausfällt —
wer übernimmt, was sehe ich, geht etwas verloren? (GQ44 legt vor;
R macht Provider-Resilienz zur Nutzer-Fläche.)
