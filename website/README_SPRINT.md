# Website-Quelle (Sprint 08.10., shell-less gebaut)

## Warum
`deploy-pages.yml` baut `website/` → `website/public/`, aber `website/` fehlt
auf main (404). Jeder Deploy-Versuch scheitert. Diese 4 Dateien schließen die
Lücke. Lokal gebaut, NICHT gepusht (Shell down): zum Übernehmen Ordner
`website/` auf main legen, Workflow manuell starten.

## Dateien
- `src/index.html` — Startseite (Deutsch, kein JS, kein Tracking, keine Cookies)
- `src/404.html` — Fehlerseite
- `build_site.sh` — Build (sh-only, kein Netzwerk; E-Mail nur wenn gesetzt)
- `README_SPRINT.md` — diese Datei (nicht Teil des Deploy-Artefakts)

## Danach (Dennis, ca. 5 Min, nur du kannst das)
1. STRATO DNS: Apex-A auf 185.199.108.109/110/111 + enforcing HTTPS in Pages.
2. Mail: SPF-Eintrag aus STRATO-Panel setzen (sonst DMARC-Rejects weiter).
3. GitHub → Actions → Deploy Courier Website → Run workflow.

## Absichtlich NICHT drin
Keine persönlichen Daten, keine Zahlung, kein Shop, kein Tracking.
