# User Acceptance L — Kosten-Transparenz / Spend-Schutz (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: F-nah (Onboarding/Kosten) + B-nah (Geldfreigabe ist echte Human-Grenze).

## USER_PROBLEM

Als Nutzer weiß ich nicht: was kostet mich dieser Lauf? Greift Courier
zum teuren Provider, obwohl ein günstiger bereitsteht? Gibt es ein Limit —
und wer stoppt, bevor versehentlich Geld ausgegeben wird? Heute gibt es
weder Zähler noch Cap noch Beleg.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- Kosten-Label existiert: Worker registrieren `cost_class`
  (`server/app.py:212`, Default `"unknown"`); Live-State
  (`server/state/central_state.json`) zeigt `cost_class: unknown`.
- Spar-Logik existiert NUR als Claim-Deferral (`server/app.py:289-318`):
  teurer Worker tritt zurück, wenn ein billigerer qualifizierter Worker
  verfügbar ist.
- ABER — Befund L-a (Deferral blind für den Live-Default): Das Deferral
  greift nur bei `worker_cost in ("high", "medium")` (`:290`). Der
  ausgelieferte Default `"unknown"` fällt durch beide Seiten des
  Vergleichs: als Claimant kein Deferral (`:290`), als Alternative nie
  "billiger" (`:300/302` listen `unknown` nicht). Mit Default-Workern ist
  die Spar-Logik still abgeschaltet.
- Befund L-b (stille Ablehnung): Ein Deferral setzt nur `matched = False`
  (`:315-318`) — kein Log, keine Metrik, kein Grund. Der Nutzer sieht
  einen leeren Claim, nie "zurückgestellt für billigeren Worker".
- Befund L-c (zwei Kosten-Welten): `scripts/resource_policy.py`
  (`CostGate.evaluate_spend_request`) blockt `estimated_cost_eur > 0`
  ohne Human Gate — wird aber vom Server-Dispatch-Pfad NICHT aufgerufen
  (Aufrufer nur Chief/Autonomous-Loop + Tests; null Treffer in
  `server/`). Der Pfad, der wirklich dispatched, kennt kein Spend-Gate.
- Befund L-d (kein Zähler): Kein Spend-Meter, kein Budget-Cap, keine
  Per-Task-Kosten im State. Die Beacon-Kostenzeile rechnet gegen die
  nicht-existente Route `/system/metrics` (siehe E-Befund) und liefert
  in Dauerschleife nur Fehler. Pilot-Metrik "Provider Cost Class" und
  Dummy-Target `free_or_subscription` sind Ziele, keine Messungen.
- Positiv (Plan-Seite): Geldfreigabe ist als echte Human-Grenze definiert
  (kanonischer Plan; B-Taxonomie MONEY). Die Bremse ist spezifiziert,
  nur nicht an den Dispatch-Pfad angeschlossen.

## ACCEPTANCE_REQUIREMENT

- L1: Jeder Lauf zeigt VOR Start: erwartete Kostenklasse (aus deklarierten
  Worker-Klassen), Cap (Betrag oder explizit "kein Cap gesetzt"), und was
  bei Cap-Erreichen passiert (Stopp + B-Eintrag, nie stiller Weiterlauf).
- L2: Während des Laufs gibt es einen Spend-Zähler (Methode genannt:
  Provider-Abrechnung oder Zähler × Satz). "Unknown" ist als Zählerstand
  zulässig — als Verschleierung ("~0 €") verboten.
- L3: `cost_class: unknown` ist kein Normalzustand: Worker ohne deklarierte
  Klasse werden als UNDECLARED markiert; Deferral-Regel wird für sie
  definiert (konservativ = wie `high` behandeln) statt sie still
  auszunehmen. L-a-Fix durch Runtime-Owner.
- L4: Jede Deferral-/Kosten-Entscheidung ist sichtbar: "Task X an Worker Y
  (low) statt Z (high)" bzw. "kein billigerer verfügbar". Stille
  Claim-Leere (L-b) wird mit Grund geloggt.
- L5: Subscription-first ist belegbar: Solange das Pilot-Target
  "zero accidental PAYG spend" gilt, zeigt der Lauf den Nachweis
  (nur Abo-/Free-Klassen beteiligt) oder die Abweichung mit Human-Gate-Ref.
  CostGate und Dispatch-Pfad werden verbunden (L-c-Fix durch
  Runtime-Owner) oder die Trennung wird ehrlich dokumentiert.

## MISSING_SYSTEM_SUPPORT

- Kein Spend-Zähler, kein Cap-State, kein Cap-Enforcement im Dispatch-Pfad.
- Keine Deferral-Sichtbarkeit (Log/Metrik/Grund).
- Keine CostGate-Anbindung an Claim/Result; `unknown`-Default ohne Regel.
- Keine Messmethode für Pilot-Metrik "Provider Cost Class".

## PREPARABLE_NOW

- Dieses Dokument (L1–L5 + Befunde L-a bis L-d).
- Cap-Policy-Entwurf (Default: Pilot-Cap 0 € PAYG, Überschreitung →
  Stopp + MONEY-Wall an B-Liste; kein Auto-Upgrade).
- L-a/L-c-Notiz an Runtime-Owner (ein-Zeilen-Fix-Kandidaten:
  `unknown`→konservativ; CostGate-Check im Claim-Pfad oder dokumentierte
  Nicht-Anbindung).

## BLOCKED_UNTIL

- Echte Kostenmessung erst mit Pilot-Läufen (Provider-Abrechnungen).
- Runtime-Owner entscheidet Deferral-Default + CostGate-Anbindung.

## NEXT

M (Benachrichtigung): wie erfahre ich, dass Courier mich braucht —
ohne ständig nachzusehen? Poll-Vertrag statt Push-Versprechen.
