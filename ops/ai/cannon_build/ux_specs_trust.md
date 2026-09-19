# Courier UX Specs — Trust, money, audit, config, modes (MUSE 73,75–81,83–95,96–98,101,104,105)

## 73 — Human gate reason catalog
| Code | Developer code | User title (DE) | User explanation |
|---|---|---|---|
| PAYMENT | gate:payment | "Kostenpflichtige Aktion" | "Dieser Schritt kann Geld kosten. Bitte Betrag prüfen und freigeben." |
| AUTH | gate:auth | "Anmeldung erforderlich" | "Der Zugang ist abgelaufen oder fehlt. Nur dieser Worker ist blockiert." |
| PUBLICATION | gate:publication | "Veröffentlichung" | "Inhalte verlassen den geschützten Bereich. Bitte prüfen und freigeben." |
| DELETE | gate:delete | "Löschen" | "Daten werden unwiderruflich gelöscht. Gilt nur für exakt diesen Pfad." |
| SECRET | gate:secret | "Geheimer Wert betroffen" | "Ein Secret ist im Spiel. Es wird nie angezeigt oder protokolliert." |
| LEGAL_COMMITMENT | gate:legal | "Verbindliche Zusage" | "Rechtlich bindende Aktion. Nur mit ausdrücklicher Freigabe." |
| UNKNOWN_EFFECT | gate:unknown_effect | "Unklare Wirkung" | "Die Wirkung des letzten Versuchs ist unbekannt. Erst klären, dann weiter." |
| BUDGET | gate:budget | "Budgetgrenze" | "Das Limit wäre überschritten. Betrag prüfen und freigeben oder ablehnen." |
| SCOPE_ESCALATION | gate:scope | "Erweiterter Zugriff" | "Mehr Zugriff als ursprünglich geplant. Nur exakt diesen Scope freigeben." |
| EXTERNAL_ACCOUNT | gate:account | "Externes Konto" | "Aktion auf einem externen Konto. Konto und Umfang stehen in der Freigabe." |

## 75 — Approval receipt
approved action · scope (exact) · task · execution/attempt · timestamp · approver
· one-time/reusable (default one-time) · expiry · cost limit. No invisible blanket powers.

## 76 — Budget gate
Shows incremental expected cost · run spend · project spend · remaining budget · estimate
confidence. Approval binds exact amount + exact action only.

## 77 — Night budget report
CONFIRMED_SPEND (receipts) · ESTIMATED_SPEND · UNKNOWN_SPEND (never 0 when unknown —
show "unknown") · CREDITS/REFUNDS · PROVIDER_CALLS · BUDGET_LIMIT · REMAINING.

## 78 — Cost confidence
HIGH (provider receipt) · MEDIUM (usage response) · LOW (local estimate) · UNKNOWN
(missing telemetry). UI badges each spend line accordingly.

## 79 — Usage record
provider · model · worker · execution · raw usage · normalized estimate · currency
· timestamp · source · confidence. No billing engine.

## 80 — Provider limit UX
temporary_429→"Pause mit Countdown, dann ein Probeversuch" · daily_cap→"Heute gestoppt,
morgen weiter oder Kontingent erhöhen" · monthly_cap→"Monatslimit, Human-Entscheid"
· account_quota→"Kontingent am Konto, kein automatischer Kontowechsel"
· billing_blocked→"Abrechnung blockiert, Human-Gate" · unknown_restriction→"Unbekannte
Einschränkung — fail closed, diagnostizieren".

## 81 — Backpressure visualizer
"THROTTLED because: <provider limit | resource yellow/red | scope lock | budget |
result backlog | verification backlog | human gate>". User always sees why nothing starts.

## 83 — Verification queue view
Columns: result_id · task · verifier · age · priority · reason · status. Header: "DONE ≠ VERIFIED".

## 84 — Verifier identity card
verifier_id · type · version/build · policy · input result_id · decision · timestamp
· independence class. No independence claim when writer verifies own work.

## 85 — Independence labels
SELF_CHECK (writer==verifier, evidence: same id) · AUTOMATED_SECONDARY (different
automated verifier, evidence: verifier build id) · INDEPENDENT_REVIEW (separate
reviewer/system, evidence: reviewer id + policy) · HUMAN_REVIEW (human receipt).

## 86 — Acceptance hierarchy
RESULT RECEIVED (missing: task binding) → RESULT BOUND (missing: verification)
→ VERIFIED (missing: acceptance) → ACCEPTED. Each step shows what is still missing.

## 87 — Audit trail view
Filters: task · execution · worker · result · verifier · gate · build · provider.
Views: chronological and causal chain (via caused_by links).

## 88 — Event export format (JSONL)
event_id · schema_version · timestamp · entity_type · entity_id · caused_by · event_type
· status · redacted_metadata. No secrets, ever.

## 89 — Exit export pack ("Export my Courier project")
Projects · Goals · Work Packages · Tasks · Results · Artifacts metadata · Verifications
· Audit events · Provider mappings. No credentials.

## 90 — Import roundtrip
Export A → fresh install → import → compare. Stable: semantic IDs, result links,
provenance. May change: local runtime IDs, import session IDs.

## 91 — Schema versioning
schema_version on every record; readers ignore unknown fields (forward compatible);
migrations keep backup, never silently drop data; failure → fail-closed screen.

## 92 — Migration failure UX
"MIGRATION FAILED — from <v> to <v>. Backup: <location>. Affected store: <name>.
Candidate: <build>. Safe rollback available: yes/no." No auto-repair without evidence.

## 93 — Config identity (secret-free fingerprint)
Include: decision-relevant options, mode limits, feature flags, adapter types.
Exclude: tokens, passwords, private user content.

## 94 — Config drift
Tested config ≠ loaded config → "CONFIG DRIFT" with categories only: mode · worker
adapters · security · storage · feature flags. Never diff secrets.

## 95 — Feature flag truth
Per flag (NORMAL/FAST/TURBO/NIGHT/MUSE/AUTO_UPDATE/...): SPEC_ONLY · IMPLEMENTED
· TESTED · PHYSICALLY_VERIFIED · ENABLED. Current classification is Codex-verified
FAST/NORMAL; TURBO>2 and NIGHT remain SPEC_ONLY until physical verification.

## 96 — Turbo lock UI
"Mehr als zwei reale parallele Worker sind noch nicht physisch verifiziert." Never a bare "Coming soon".

## 97 — Fast mode education
"FAST bedeutet: bis zu zwei unabhängige sichere Arbeitsbahnen. Nicht automatisch
doppelt so schnell. Scope-Konflikte können Parallelität reduzieren."

## 98 — Normal mode education
"Normal: maximal eine externe aktive Aufgabe. Sicherer Default für Nachtlauf und große
Queues. Große Queue bedeutet nicht parallele Provider-Flut."

## 101 — Resource RED UX
Shows trigger · affected resource · running tasks · new tasks blocked: YES · recovery
requirement. No new external work starts while RED.

## 104 — Bounded log view
Last N events, pagination, filter, export. Never full-log render.

## 105 — Error dedup
500 identical errors → one Error Group: count · first · last · affected tasks ·
representative error. Originals stay in audit trail.
