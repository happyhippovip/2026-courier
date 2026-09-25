import json, subprocess

prompts = [
    ("analysis-tests", "Analysiere das gesamte Projekt gründlich. Fokus: Tests, fehlende Tests, Edge Cases und mögliche Regressionen. Arbeite selbstständig weiter.", "read_project"),
    ("analysis-performance", "Analysiere das gesamte Projekt gründlich. Fokus: Performance, langsame Abläufe, unnötige Arbeit und Bottlenecks. Arbeite selbstständig weiter.", "read_project"),
    ("analysis-errorhandling", "Analysiere das gesamte Projekt gründlich. Fokus: Fehlerbehandlung, Logging, Recovery und problematische Zustände. Arbeite selbstständig weiter.", "read_project"),
    ("analysis-codequality", "Analysiere das gesamte Projekt gründlich. Fokus: Codequalität, Duplikate, Dead Code, TODOs und unnötige Komplexität. Arbeite selbstständig weiter.", "read_project"),
    ("analysis-dependencies", "Analysiere das gesamte Projekt gründlich. Fokus: Abhängigkeiten, Konfiguration, Build-System und mögliche Inkonsistenzen. Arbeite selbstständig weiter.", "read_project"),
    ("analysis-security", "Analysiere das gesamte Projekt gründlich. Fokus: Security-Hygiene, Eingabevalidierung, Secrets und riskante Annahmen. Keine destruktiven Änderungen.", "read_project"),
    ("analysis-docs", "Analysiere das gesamte Projekt gründlich. Fokus: Dokumentation, unklare Schnittstellen und fehlende technische Erklärungen. Arbeite selbstständig weiter.", "read_project"),
    ("analysis-final", "Führe eine abschließende Gesamtanalyse des Projekts durch. Verbinde Erkenntnisse aus Architektur, Tests, Performance und Codequalität und suche weitere Probleme.", "read_project")
]

for task_id, prompt, scope in prompts:
    task = {
        "task_id": task_id,
        "package_id": "sys-audit",
        "description": prompt,
        "dependencies": [],
        "read_scopes": ["all"],
        "write_scopes": ["none"],
        "status": "READY"
    }
    payload = json.dumps(task)
    subprocess.run(["python3", "scripts/work_queue.py", "add", payload], capture_output=True)

