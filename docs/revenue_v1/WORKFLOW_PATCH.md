# Workflow-Patch für revenue_v1_baseline.yml (nicht angewendet)

Grund: Der Push mit Änderung an `.github/workflows/` wurde abgelehnt, weil dem verwendeten Token der `workflow`-Scope fehlt. Die Workflow-Datei ist in diesem Branch daher unverändert (Stand 481fd0ba). Der ursprüngliche Commit mit der Workflow-Änderung liegt lokal im Backup-Branch `revenue-v1-with-workflow` (a4d58ed8).

Inhalt:
1. Zeile 23: Beispieltext `USD 500.00` → `EUR 99.00` (Preis Revenue V1).
2. Upload der Worker-Artefakte um `work_dir/report_de.md` ergänzen (sonst entsteht der deutsche Bericht im Lauf, landet aber nicht im Artefakt).

## Anwenden (nur durch jemanden mit `workflow`-Scope bzw. über die GitHub-Weboberfläche)
```bash
sed -n "/^```diff$/,/^```$/p" docs/revenue_v1/WORKFLOW_PATCH.md | sed "1d;\$d" > /tmp/wf.diff && git apply /tmp/wf.diff
git add .github/workflows/revenue_v1_baseline.yml
git commit -m "ci(revenue-v1): EUR 99.00 example, upload report_de.md"
```
Alternativ die zwei Zeilen direkt im GitHub-Editor ändern. Geprüft: `git apply --check` läuft auf diesem Stand sauber.

## Unified diff
```diff
--- a/.github/workflows/revenue_v1_baseline.yml
+++ b/.github/workflows/revenue_v1_baseline.yml
@@ -20,7 +20,7 @@
         required: true
         type: string
       price_currency:
-        description: 'Agreed Price and Currency (e.g. USD 500.00)'
+        description: 'Agreed Price and Currency (e.g. EUR 99.00)'
         required: true
         type: string
       delivery_destination:
@@ -100,6 +100,7 @@
             task.json
             work_dir/report.json
             work_dir/report.md
+            work_dir/report_de.md
             result.json
 
   verifier:
```
