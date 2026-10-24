# V43 · Integrationsabnahme · Claude Opus · 24.10.2026

Unabhängiger Bericht, **kein Merge**. Für keine Datei halte ich eine Writer-Lease. Produktdateien wurden nicht geändert. Neu sind nur zwei Negativtest-Vorschläge als Diff-Dateien.

## BASE_HEAD
`integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a` (VERIFIED). Gegenüber V40 hat sich nichts bewegt, und auch die PR-Heads #846, #836, #837, #843, #845, #788, #810 und #785 sind unverändert.

## Status der Pakete 1–8 (Belege aus V31, V38 und V40; nur neue Punkte sind hier markiert)
| # | Paket | Prüfbeleg | Unabhängige Abnahme | Status |
|---|---|---|---|---|
| 1 | F-C1 + Folgepatch = **PR #846** `2a07219c2` | baumgleich mit V31; PR-CI 7/7 | **fehlt** (L2) | INTEGRATION_CANDIDATE, Merge erst nach den Blockern unten |
| 2 | F-C1b `claude/v38-fc1b` `439b5999c` | eigene CI 40074791146 grün | fehlt (L3) | wartet auf 1 |
| 3 | PE-1 `claude/v38-pe1` `f41dbaf2d` | CI 40074793174 grün | fehlt (L3) | unabhängig |
| 4 | CDX-COST-1 `claude/v38-cdx` `30cc812e5` | CI 40074794708 grün | fehlt (L1) | Reihenfolge zu #810 |
| 5 | GUARD-1 v3 `claude/v38-guard1` `ad69f9ed6` | CI 40074788910 grün; 4 Subagenten-Reviews | **fehlt (Codex/Grok 57,50)** | Voraussetzung für 6 und 7 |
| 6 | H12 v3 `claude/v38-h12` `cde271f64` | Ubuntu grün; Windows 2× rot durch instabile Windows-Daemon-Tests, die H12 nicht berührt | fehlt (L4) | **BLOCKED**, bis #843 drin ist und ein Windows-Lauf grün ist |
| 7 | WIN-COST-1 v3 `claude/v38-win` `4ed111395` | CI 40074800411 grün; Tests aus #843/#845 grün (47) | fehlt (Cursor Windows, Google Windows) | Reihenfolge zu #788 |
| 8 | WQ-1b v2 `claude/v38-wq1b` `a2a6dfabd` | CI 40074796599 grün; Race-Probes | fehlt (L1/L3) | **Abhängigkeit neu, siehe R1** |

Bereits erledigt bzw. fremd belegt: VC-1 v3 = #835 (gemergt, byte-gleich); #830 (gemergt). Für #836 sind der Deadlock-Fix und der Test übergeben ([Kommentar](https://github.com/happyhippovip/2026-courier/pull/836#issuecomment-6381516229)). **#836 ist nicht releasefreigegeben.** #837 hat das Urteil ACCEPT_WITH_NITS.

## CONFLICTS
Textuelle Konflikte mit offenen `integration/v1`-PRs gibt es nicht (V31/V40: #836, #810, #788, #785 per 3-way sauber; #846 + #836 zusammen ergeben 132 passed). #824 zielt auf `main` und ist hier nicht relevant.

## REGRESSIONS / neue Integrationslücken (VERIFIED)
| ID | Befund | Beleg | Negativtest-Vorschlag | Owner |
|---|---|---|---|---|
| **R1 (P1, neu)** | **Die Bridge postet eine vom Controller abgelehnte Mission endlos.** Das Spend-Gate der Bridge (`handoff_spend_block`, CostGate-Ressource + Schätzung) und das Controller-Gate von #846 (`COST_CLASS` des Adapters) können auseinanderlaufen. Lehnt der Controller mit 400 `cost_blocked` ab, meldet `_post_task` nur `rejected`: die Mission bleibt `posted=False`, wird **bei jedem Durchlauf erneut gepostet** und bekommt **nie** den Status BLOCKED. WQ-1b parkt nur bei ERROR/BLOCKED, deshalb bleibt der Queue-Holder dauerhaft belegt (Fail-closed bei den Kosten, aber Stillstand) | `evidence/probe_bridge_cost_divergence.py` mit echtem `Controller` von #846: 3 Durchläufe ergeben 3 POSTs, `posted=False`, `status=None`, Exit 2 | `V43_bridge_refusal_park_pin.diff` (sha256 `dbc11e2ea7ba86c72fe6d30507c3d223db250c131e3c17f1c8fb62763a6f4ed9`): strikter xfail; erwartet 1 POST und `status == "BLOCKED"`; auf #846: 1 xfailed | `scripts/ledger_v1_bridge.py` (Cursor A→B→C / L1). Minimalfix: Bei 4xx außer 409 die Mission mit `status=BLOCKED`, Grund `controller_rejected:<code>`, stempeln und nicht erneut posten |
| R2 (P2, V40) | `ai_ranking_worker` meldet Erfolg, obwohl der `telegram_delivery`-Task abgelehnt wurde | V40 | `../v40_2026-10-24/V40_ai_ranking_route_refused_pin.diff` (sha256 `b090e717…b319`) | Intake/L4 |
| R3 (P1, V34) | #836: Callback-Deadlock | V34 | Regressionstest im Fix-Diff (sha256 `2807873e…7156e`) | Cursor Mac/L3 |

## MISSING_ACCEPTANCE
Für keines der 8 Pakete gibt es bisher eine **unabhängige** Abnahme durch den Owner oder einen fremden Prüfer. Meine Subagenten-Reviews zählen nicht als unabhängig. Konkret nötig:
- L2 für #846;
- Codex oder Grok 57,50 für GUARD-1, H12 und WIN-COST-1;
- L1/L3 für WQ-1b und F-C1b;
- Cursor Windows bzw. Google Windows für den Windows-Lauf von WIN-COST-1 und H12.

## DEPENDENCY_ORDER (für den autorisierten Integrator)
1. **#846** (F-C1 + Folgepatch, ein Merge), **nur gemeinsam mit oder nach dem R1-Fix in der Bridge**. Sonst landen vom Controller abgelehnte Bridge-Missionen ab diesem Moment im Endlos-Repost.
2. F-C1b (braucht 1)
3. PE-1 und CDX-COST-1 (unabhängig; CDX nach Klärung mit #810)
4. GUARD-1 v3
5. WIN-COST-1 v3 (braucht 4; Reihenfolge zu #788)
6. H12 v3 (braucht 4; erst nach #843 und einem grünen Windows-Lauf)
7. WQ-1b v2 (unabhängig; parkt aber erst sinnvoll, wenn die Bridge BLOCKED stempelt, also nach dem R1-Fix; Rollout auf allen Homes gleichzeitig)

Nach **jedem** Schritt muss die v1-CI auf dem neuen Trunk-Head grün sein; sonst wird dieser eine Schritt zurückgenommen. Ein grüner Kombinationslauf ist **keine** Freigabe.

## MERGE_BLOCKERS
- **MERGE-GO** von Dennis/L1 je Schritt (fehlt).
- **owner_token:** 64 öffentliche Slot-Dateien; Rotation und Widerruf durch den Kontoinhaber (auch das Gate von #846).
- **R1** vor oder zusammen mit #846.
- **H12:** instabile Windows-Tests (#843).
- **POL-1:** BLOCKED (Kostenentscheidung).
- **#836:** nicht freigegeben (P1-Deadlock offen).

## NEXT_SAFE_INTEGRATION
Nichts mergen. Als nächster sicherer Schritt gilt nur:
- Der Bridge-Owner bewertet R1 (Pin + Minimalfix).
- L2 prüft #846 unabhängig.
- Danach entscheidet der Integrator über #846 zusammen mit dem R1-Fix.

## COST
0 €. Alle Prüfungen liefen lokal; keine neuen CI-Läufe in V43, kein PAYG, keine Provider-Aufrufe.
