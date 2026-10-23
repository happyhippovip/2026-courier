# Courier Symphony — Dual Dispatcher Hot Standby / Safe Failover V2
**Öffentliche Engineering-Strategie | 23.10.2026 | nicht installiert, nicht gemergt, keine produktive Übernahme**

> **ZIEL:** Der bisherige Mac/Grok-Master und der Windows/Grok-Standby dürfen technisch **beide jederzeit übernahmebereit** sein, aber **niemals gleichzeitig verteilen**. `STANDBY_READY` und `MASTER_ACTIVE` sind verschiedene Zustände. Vollautomatischer Failover ist **nicht** nachgewiesen. Dieser Markdown-Plan ist kein Dispatcher-Code, keine Writer-Lease, kein Scheduler und keine Freigabe zu einer Notfall-Übernahme.

## 1. Abgleich 23.10.2026 — beweisbarer vs. gemeldeter Stand

- [Öffentliches Failover V1](https://github.com/happyhippovip/2026-courier/blob/docs/public-workflow-2026-10-23/docs/public/GROKBOT_WINDOWS_MASTER_FAILOVER_STANDBY_V1_2026-10-23.md) erlaubt bereits read-only Standby, Trockenlauf, kontrollierte Übergabe. Es implementiert **keinen gemeinsamen Epoch-/Lease-Store** und **keine globale Fencing-Durchsetzung**.
- Aus der Mac-/Windows-Koordination wurden Trockenlauf-Belege für Windows-Standby (8 Tests und Wiederholungen) **gemeldet**. Sie belegen keine tatsächliche Übergabe und sind nicht mit einem unabhängig geprüften gemeinsamen Autoritätsdienst gleichzusetzen.
- `integration/v1` war zuletzt `81bbf224b0ae`, [Courier CI #40008119253](https://github.com/happyhippovip/2026-courier/actions/runs/40008119253) rot, [Customer-Reality #40008119364](https://github.com/happyhippovip/2026-courier/actions/runs/40008119364) grün.
- PRs [#836](https://github.com/happyhippovip/2026-courier/pull/836), [#837](https://github.com/happyhippovip/2026-courier/pull/837), [#843](https://github.com/happyhippovip/2026-courier/pull/843), [#844](https://github.com/happyhippovip/2026-courier/pull/844) und [#845](https://github.com/happyhippovip/2026-courier/pull/845) waren beim Abruf offen. SHAs, CI und Owner vor Arbeit neu prüfen.
- Die private Grok→Cursor-Proposed-Handoff-Datei existiert, aber der betreffende Cursor-Cloud-Agent meldet **ACCESS_BLOCKED / GitHub 404** zum privaten Repo. Ein GitHub-Push dorthin kann die bisherige PR-#836-Wache nicht wecken. **Kein privates Workkey-Material in öffentliche PRs kopieren.**

## 2. Sicherheitsarchitektur — ein fälschungssicherer aktiver Master

**Anforderung:** Ein einziger, dauerhafter und für Mac und Windows erreichbarerer **autoritärer** Master-State, der atomare Compare-And-Swap-/Transaktionsoperationen unterstützt. Ein Markdown-/GitHub-Commit ist Checkpoint-/Transport-Evidenz, **kein geeigneter alleiniger Live-Fencing-Dienst**.

Minimales Zustandsmodell (Strukturbeispiel, kein gespeicherter Token):

```text
authority_id        = courier_dispatch
epoch               = positive monotonic integer
holder_id           = authenticated coordinator identity
grant_id            = opaque random lease identifier
lease_deadline      = authoritative service-side deadline
workkey_snapshot    = canonical approved snapshot digest
status              = ACTIVE | RELEASED | EXPIRED_FENCED
version             = monotonic compare-and-swap revision
policy_ref          = approved takeover authority / human gate
```

**Erforderliche atomare Transition:**

1. `READ` aus echtem gemeinsamem Authority-Store, inklusive aktuellem Epoch/Revision/Lease.
2. `PREPARE`: beide Teilnehmer gleichen Workkey-Snapshot, offenen Dispatch und Checkpoints **lesend** ab. Neue Aufgaben sind während der kurzen exklusiven Übergabe zu pausieren.
3. `CAS_GRANT`: Nur der zuständige autorisierte Controller/Authority-Service darf nach geltender menschlicher Freigabe bzw. zuvor ausdrücklich genehmigter Failover-Policy `version`, `epoch`, `holder` und `grant` **in einer atomaren Transaktion** wechseln. Kein zweiter Schattenstore.
4. `FENCE`: **JEDER** Dispatcher-/Claim-/Workkey-Admission-Schreibpfad prüft den aktuellen `epoch+grant+holder` serverseitig. Ein altes Token wird **verweigert**, selbst wenn der Mac nach Netztrennung weiterläuft. Dispatch nie nur durch lokale Chat- oder Prozessflags sichern.
5. `ACK`: erst danach ist der neue Master `MASTER_ACTIVE`. Der alte Master sieht `FENCED` und kann nicht mehr zuteilen. Das muss in Negativtests bewiesen werden.
6. `RELEASE/HAND_BACK`: exakt dieselbe gesicherte Transition in Gegenrichtung, mit höherem Epoch; **keine** Epoch-Wiederverwendung.

**Kein sicheres CAS, keine gültige Fencing-Prüfung oder kein Zugriff auf gemeinsamen Store ⇒ KEIN aktiver Ersatz-Master.** Ausfall/Timeout eines Chatfensters allein ist **kein** Beweis, dass alte Dispatch-Zugriffe technisch gesperrt sind. Timeout/Lease-Ablauf darf nur durch den autoritativen Dienst bewertet werden, nicht durch divergente Mac-/Windows-Uhren.

### Zugang und Autorisierung

- Die Instanz, die den Authority-Store verändert, benötigt explizite rollen- und scopegebundene Rechte. Ein Prompt oder ein lokaler Bot-Screenshot ist keine Authentifizierung.
- Mac und Windows benötigen nur die jeweils erforderlichen Lese-/Schreibrechte; Secrets/Grant-Werte niemals in öffentlichem GitHub, Chat, Console-Logs oder öffentlichen PRs speichern.
- **Vorab genehmigte automatische Übernahme** wäre eine **separate zukünftige Policy-Entscheidung**. Bis solche Policy, sichere CAS-Lease und Fencing-Abnahme tatsächlich bestehen, bleibt der in Failover V1 festgelegte **Human-Gate** aktiv.
- Die technische Dispatcher-Autorität ist **nicht** die Produkt-Writer-Lease eines L1–L6-Owners. Auch der Master darf keine zweite Produkt-Writer-Lane gründen.

## 3. Zustände

```text
MAC_MASTER_ACTIVE --(healthy)--> WINDOWS_STANDBY_READ_ONLY
WINDOWS_STANDBY_READ_ONLY -> PREPARED -> AWAIT_TRANSFER
AWAIT_TRANSFER --(authorized CAS+fence proof)--> WINDOWS_MASTER_ACTIVE
WINDOWS_MASTER_ACTIVE --(authorized reverse CAS)--> MAC_MASTER_ACTIVE
any state --(unknown proof, partition, corrupt state)--> SAFE_HALT_FOR_DISPATCH
```

`SAFE_HALT_FOR_DISPATCH` betrifft **neue Zuteilungen**; bereits laufende autorisierte Prozesse werden nur nach ihren eigenen Eigentümer-/Stopregeln behandelt. Es gibt **keinen** globalen Prozess-Kill auf Verdacht.

## 4. Deterministische Abnahme vor echter Aktivierung

| ID | Isolierter Test | Erforderliches Ergebnis |
| --- | --- | --- |
| E1 | Zwei Kandidaten versuchen zeitgleich `CAS_GRANT` | Maximal einer erhält den neuen gültigen Epoch |
| E2 | Alter Mac sendet alten `epoch+grant` nach Windows-Übernahme | Jeder betroffene Dispatch-/Claim-Einlass lehnt ab, **0 neue Claims** |
| E3 | Mac ist still, aber Lease noch gültig | Windows bleibt read-only; kein passives Chat-Timeout-Failover |
| E4 | Autoritativer Lease-Ablauf und Human-/Policy-Gate erfüllt | Ein expliziter CAS-Wechsel, dokumentierter Fencing-Nachweis |
| E5 | Netzwerkpartition / Store nicht erreichbar | Keine Seite darf neue autoritative Zuteilung vortäuschen |
| E6 | Erfolgreiche Windows-Übernahme, Mac kehrt zurück | Mac erkennt höhere Epoch und darf nicht mehr verteilen |
| E7 | Rückübergabe an Mac | Höhere Epoch, gültiger neuer Grant, Windows alt-token-fenced |
| E8 | Doppelte GitHub-/Timer-Ereignisse, Crash kurz vor ACK | Genau eine autorisierte Reconciliation, kein doppelter Workkey-Claim |
| E9 | Gleicher Workkey / abweichender privater Ledger-SHA | Transfer bleibt BLOCKED, bis kanonischer Stand versöhnt |
| E10 | Kosten unbekannt / Quota unklar / RESOURCE_PAUSE | Kein kostenpflichtiger Agentenstart, kein Ressourcenspawn |
| E11 | Versuchte L1-Merge-/L2-Writer-Operation allein mit Master-Token | Abgelehnt: Dispatcher ist kein Produkt-Writer und kein Merge-GO |
| E12 | Dauerhafter Authority-Store-Neustart | Monotone Epoch bleibt erhalten; keine unbefugte alte Lease gültig |

Diese Tests müssen im isolierten, **nicht-produktiven** Authority-Store mit Wegwerf-Identitäten ablaufen. Die alten 8/8 lokalen Windows-Trockenläufe ersetzen sie nicht. Nach isoliertem PASS folgt eine getrennte kontrollierte Cross-Host-Abnahme unter zuständigem Owner; echte Produktumschaltung erst danach.

## 5. Mehr Leistung ohne Split-Brain

Zwei **parallele, unabhängige** Arbeitsspuren unter ein und derselben Master-Autorität:

- **Sicherheits-Spur A:** Windows-CI, #836 Provider-DONE, #837 A/B/C-Proof, Receipt/Task-/Attempt-Bindung, CostGate/F-C1, ACK-/Recovery-Negativtests. Tatsächlich offene Befunde präzise dem zuständigen vorhandenen Owner zuweisen, keine Doppelarbeit.
- **Produkt-Spur B:** Offline-Demo, echte Kundeneingaben mit synthetischen Testdaten, Hub/Installer, nachvollziehbare Artefakt-Ausgabe und Dokumentation. Sie darf unabhängig mit bestehenden Read-only-Prüfern fortschreiten, **ohne** roten Release-Gates auszuweichen.
- **Failover-Spur C:** Ein separater autorisierter Read-only-Architektur-Owner erstellt Store-/Fencing-Design + Negativtests. Produktcode nur mit tatsächlicher eigener Lease.

Pro Leistungsrunde: max. zwei **neue** leichte, voneinander verschiedene Read-only-Subagenten **nur wenn inkludierte Kontingente und vorhandene native Delegation verifiziert sind**, ansonsten bereits vorhandene Prüfer. Global `HEAVY_JOB_LIMIT=1` je Host und `SINGLE_WRITER=YES`. Mehr Subagentenplätze oder laufende Timer sind kein Beweis für mehr lieferbaren Produktfortschritt.

Ereignis-Dedupe `app|epoch|event_id|workkey|head|acceptance`. `RUNNING`-Doppelereignisse in `RECHECK_NEEDED` zusammenfassen. Kein neuer Sender oder zweiter 30-Minuten-Timer. Bisherige Project- und Google-Goals bleiben **getrennt**.

## 6. Folgeauftrag an zuständigen bestehenden Owner (nur Vorschlag)

**SAFE-FAILOVER-V2-PROPOSAL:** Einen echten autoritativen Store und serverseitiges Fencing als kleinen, testbaren Implementierungsauftrag spezifizieren, den richtigen Scope-/Writer-Owner und das gültige Human-Gate ermitteln. In einer eigenen autorisierten Test-Lane `E1–E12` erst Rot, dann Grün. Keine produktive Installation durch diese Dokumentation.

**Bis dahin gelten:** `CURRENT_MASTER=MAC_REPORTED`, `WINDOWS_STANDBY=PREPARED_REPORTED`, `FENCING=NOT_ENFORCED`, `MASTER_FAILOVER=BLOCKED`. Keine zweite aktive Queue.

## Quellen und Übergaben

- [Öffentliche Teamkoordination und Failover V1 in PR #839](https://github.com/happyhippovip/2026-courier/pull/839)
- [Release-Train-Strategie und fünf Rollen-Prompts in PR #841](https://github.com/happyhippovip/2026-courier/pull/841)
- [Goal/Windows-CI-Checkpoint V3](./GOAL_STOP_SCHEDULER_WINDOWS_CI_HANDOFF_V3_2026-10-23.md)
- [Wake-Coalescing-Vertrag](../v1/AUTOMATION_WAKE_COALESCING_CONTRACT.md)
- Interne Agenten-/Ledger-/Recovery-Daten und Token **bleiben ausschließlich privat**.

**Status: PROPOSED DESIGN / NO REAL TRANSFER / NO EXTRA SPEND / NO MERGE.**
