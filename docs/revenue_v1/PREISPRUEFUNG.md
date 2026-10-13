# Preisprüfung 99 € (Einführungspreis, erste 3 Kunden)

## Konsistenz im Repo / Memory
- Project-Memory `COURIER_AGENT_OPERATING_CONTEXT.md`: „EUR 99 for the first 3 customers“ – Referenz.
- Konsistent 99: `events/approvals/human_fast_gates/human_gate_REV-OPP-B2B-AUTONOMY-AUDIT.json:13` (€99, allerdings Name „AI Agent Reliability Check“), `scripts/invoice_generator.py:64`, `events/revenue-opportunities/market_intelligence/FINAL_P01_FOLLOWUP_SPEC.json:5`, `fixtures/test_intake.json:6` (`EUR_99`).
- Abweichend: `.github/workflows/revenue_v1_baseline.yml:23` Beispiel „USD 500.00“; `pilot/pricing_config.json` kennt nur audit 149 / pilot 390; `website/src/index.html:213` 5,00 €. Kein öffentlicher Ort nennt 99 € für dieses Produkt.

## Marktvergleich (Websuche 13.10.2026)
- zizmor: Open Source, 0 $, 38 Audits – https://rywalker.com/research/zizmor , https://github.com/marketplace/actions/zizmor-action
- StepSecurity: Community gratis für öffentliche Repos, Enterprise 16 $/Entwickler/Monat – https://www.stepsecurity.io/pricing
- Upwork-Auftrag: Review eines Workflows an festem SHA, 250 $ fix – https://www.upwork.com/freelance-jobs/apply/Independent-Azure-GitHub-Actions-Security-Reviewer_~022106853401122567421/
- Upwork-Richtwert „Pipeline audit and documentation“ 500–1.000 $ – https://www.upwork.com/hire/cicd-freelancers/
- Opsio GitHub-Actions-Assessment 6.000–12.000 $ – https://opsiocloud.com/github-actions-ci-cd/

## Bewertung
99 € liegen klar unter menschlichen Reviews (250–1.000 $) und sind als Einführungspreis plausibel. Aber: kostenlose Tools (zizmor, StepSecurity Community) decken für öffentliche Repos mehr Regeln ab als die heutigen 5 Textregeln. Der Preis ist nur durch die menschliche Durchsicht, deutsche Erklärung und SHA-gebundene Nachweisbarkeit begründbar. PRICE_VALIDATED: nur bedingt (kein zahlender Kunde, Wert stark von Bericht-Qualität abhängig).
