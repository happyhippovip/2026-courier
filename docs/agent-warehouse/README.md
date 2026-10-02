# Agent Warehouse / Lagerhalle

Status: PUBLIC-SAFE WORKING DOCUMENTATION  
Created: 2026-09-20  
Repository: `happyhippovip/2026-courier`

## Zweck

Dieser Ordner ist die geordnete Übergabe für Menschen, Agenten und eine spätere Cloud-Migration. Er sammelt Produktvision, Feature-Map, AI-/Community-Wissen, Content-Pipelines, Cloud-Handoff und IP-/Branding-Hinweise so, dass ein späterer Agent nicht wieder bei null anfangen muss.

## Wichtiger Sicherheitsrahmen

Dieses GitHub-Repository ist öffentlich. Deshalb gehören hier **keine** Passwörter, API-Keys, Tokens, Cookies, OAuth-Secrets, Kundendaten, privaten E-Mails, personenbezogenen Archive, Zahlungsdaten oder nicht veröffentlichungsfähigen Geheimnisse hinein.

Interne Secrets müssen später in einen Secret Manager / eine private Infrastruktur. Dieses Verzeichnis dokumentiert nur Struktur, Verträge, Migrationslogik und öffentlich vertretbare Produktinformationen.

## Canonical files

1. `PRODUCT_VISION_AND_FEATURE_MAP_2026-09-20.md`  
   Was Courier Symphony sein soll: Ziel rein -> Plan -> Agentenarbeit -> Prüfung -> Ergebnis.

2. `AI_COMMUNITY_KNOWLEDGE_ARCHITECTURE_2026-09-20.md`  
   Günstiger integrierter Chat, eigenes Wissenssystem, Community-Bestätigungen, RAG und Lernschleife ohne unkontrolliertes "Training auf allem".

3. `CONTENT_PIPELINES_2026-09-20.md`  
   Bestehende YouTube-/TikTok-Produktionspfade, Trennung von Produktion und Veröffentlichung, Freigabe-Gates.

4. `CLOUD_MIGRATION_HANDOFF_2026-09-20.md`  
   Provider-neutrale Checkliste für Cloud-Kauf, Migration, Datenklassen, Storage, Compute, DB, Secrets, Backups und Cutover.

5. `IP_BRAND_LEGAL_DRAFT_2026-09-20.md`  
   Schutztext für öffentliche Darstellung, klare Anti-Copy-Sprache, aber ohne falsche Behauptung, allgemeine Ideen monopolartig zu besitzen.

6. `AGENT_WAREHOUSE_MANIFEST.json`  
   Maschinenlesbares Inhaltsverzeichnis für Agenten.

## Bereits vorhandene Projektquellen

Die vorhandenen Dokumente unter `docs/` bleiben maßgeblich für technische Betriebsregeln. Besonders relevant:

- `COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md`
- `COURIER_4_FORWARD_ONLY_OPERATING_CONTRACT.md`
- `MULTI_AGENT_CONVERGENCE_POLICY.md`
- `MULTI_AGENT_TASK_GROUP_PROTOCOL.md`
- `EMAIL_SENDER_POLICY.md`
- `PRODUCT_REVENUE_AND_REINVESTMENT_STRATEGY.md`

Dieser neue Warehouse-Ordner ersetzt sie nicht. Er ist ein **Index + Produkt-/Cloud-Handoff**.

## Branding

Im Gespräch wurde zusätzlich ein grünes Logo-Konzept mit vier Infinity-Symbolen für "Corineria Symphonie" erstellt. Die Namensfrage `Courier Symphony` vs. `Corineria Symphonie` ist vor finalem Marken-/Domain-Rollout noch ausdrücklich zu entscheiden. Bis dahin keine stillschweigende Umbenennung des Produkts im Code.

## Prinzip für zukünftige Agenten

Wenn ein Agent neue Erkenntnisse erzeugt:

1. Quelle angeben.
2. Fakt, Annahme und Idee trennen.
3. Keine Secrets committen.
4. Keine produktiven Veröffentlichungsaktionen ohne vorhandene Freigabe-Gates.
5. Bestehende Canonical Docs referenzieren statt Parallelwahrheiten zu bauen.
6. Bei Cloud-Migration zuerst Backup + Restore-Probe, dann Cutover.


7. `CUSTOMER_PACKAGING_AND_COST_GUARDRAILS_2026-09-20.md`  
   Founder-selected working packaging direction: roughly EUR 99–100/month hypothesis, routine AI/agent work included, internal fair-use/cost controls, and explicit extra quotes for unusually expensive work.
