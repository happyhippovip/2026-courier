# User Acceptance H — Support / Diagnose / Privacy (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.

## USER_PROBLEM

Als Nutzer klemmt etwas — und ich weiß nicht: was schicke ich dem Support,
damit er helfen kann, ohne dass ich Secrets (Keys, Tokens, private Pfade)
leake? Heute müsste ich raten, welche Logs/Files relevant sind.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- Kein Diagnose-Bundle-Mechanismus vorhanden (kein Skript, kein Endpoint,
  kein Manifest). Evidenz liegt verstreut: `logs/` (Run-Logs),
  State-DBs (`central_state.json`, `ledger_run1.db`), `artifacts/`,
  `events/agent-states/`, Slot-States unter `runtime/slots/`.
- Secrets-Landschaft (Code-Fakten): `COURIER_API_KEY` (env, Bearer),
  optionale `client_secret.json`/`.env` (Run-Prep verlangt Trennung pro
  Umgebung), Keychain-Setup-Skript auf Mac-Seite.
- Positiv: `/workers`-Endpoint maskiert Keys (mit Kommentar, sie gehörten
  gar nicht in Worker-Definitionen). Negativ: keine allgemeine
  Redaktions-Regel für Logs/Bundles/Exports.
- Privacy-Randbedingungen existieren als Absicht (Master-Control-Plane:
  Privacy Boundary; Growth-Plan: privacy-aware), aber nicht als
  Redaktions-Spec: Was ist shareable vs. local-only?
- Support-Fall-Identitäten wären verfügbar (goal/task/attempt/dispatch/
  result-IDs), werden aber nirgends als Bundle-Kopf verlangt.

## ACCEPTANCE_REQUIREMENT

- H1: Ein Diagnose-Bundle enthält per Manifest: Bundle-Kopf (IDs aus
  goal→result, Candidate-SHA, Proof-Level, Zeit, Host-Klasse ohne
  Host-Geheimnisse), State-Zusammenfassung, relevante Log-Ausschnitte,
  Fingerprints — und nichts sonst.
- H2: Geschlossene Redaktionsliste (mindestens): API-Keys, Bearer-Token,
  Secrets-Dateien, private Nutzernamen/Home-Pfade in Logzeilen,
  Provider-Account-IDs. Redaktion ist Default, nicht Opt-in.
- H3: Zwei Privacy-Klassen: SHAREABLE (darf an Support) vs. LOCAL_ONLY
  (bleibt auf dem Rechner; Bundle verweist nur auf Existenz + Hash).
  Jede Bundle-Sektion trägt ihre Klasse.
- H4: Bundle-Erzeugung ist ein Schritt ("Diagnose exportieren") mit
  Vorschau: Der Nutzer sieht VOR dem Senden, was drin ist.
- H5: Support-Antwort referenziert Bundle-Hash + IDs; keine
  "schick nochmal alles"-Schleifen ohne neue Fragestellung.

## MISSING_SYSTEM_SUPPORT

- Kein Bundle-Builder (Skript/Endpoint), kein Manifest, keine
  Redaktions-Implementierung, keine Vorschau-Fläche.

## PREPARABLE_NOW

- Dieses Dokument (H1–H5 + erste Redaktionsliste).
- Bundle-Manifest-Entwurf (Sektionen aus H1, Klassen aus H3) — als Spec,
  die ein späterer Builder 1:1 implementieren kann.
- Sofort-Regel für manuelle Diagnose bis dahin: Keys/Token schwärzen,
  immer goal/task/attempt/dispatch-IDs + SHA + Zeit mitschicken.

## BLOCKED_UNTIL

- Builder-Implementierung durch Runtime-Owner (nach Pilot, mit echten
  Failure-Daten zum Kalibrieren, was relevant ist).
- Privacy-Klassen final durch Plan-Owner.

## NEXT

I (Pilot-Feedback): wie gebe ich Feedback, das als Signal zählt —
inkl. Messmethoden und 5-vs-15-Minuten-Klärbedarf.
