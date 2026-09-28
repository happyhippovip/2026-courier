# Batch 26 Evidence

## Substep 1: Reparatur & Test für Execute Week 4 Blocks
- **Fehler:** Genau wie in den Wochen 1 bis 3 startete auch `scripts/execute_week4_blocks.py` beim puren File-Import ungefragt mit Ledger-Mutationen. Es besaß weder einen Scope Guard noch Unit-Tests.
- **Fix:** Refactoring durchgeführt: Implementierung des `def execute_all():` Wrappers. Zudem wurde in `tests/test_execute_week4_blocks.py` ein isolierter Test aufgebaut, der die Ausführung simuliert, Ledger und Claims ordentlich isoliert.
- **Check/Test:** Testsuite erfolgreich (`1 passed`).

## Substep 2: Reparatur & Test für Q14 Proof
- **Fehler:** Das Proof-Skript `scripts/q14_proof.py` startete seinen Flask-Server und die anschließende Assertion-Logik direkt auf dem Top-Level (Modul-Ebene). Das bedeutete, dass ein Import dieses Files im Test (oder anderswo) sofort den Port 8080 an sich riss, was zu bösen Seiteneffekten und `Address already in use` Fehlern führte.
- **Fix:** Alles in `def main():` mit `if __name__ == '__main__':` Guard verpackt. Dazu `tests/test_q14_proof.py` geschrieben, das `threading.Thread.start` sowie die `http_post` Funktion mockt, um das Skript deterministisch und blitzschnell CI/CD tauglich durchzutesten (ohne Netzwerk-Overhead).
- **Check/Test:** Testsuite erfolgreich (`1 passed`).

## Substep 3: Reparatur & Test für Routing Proof
- **Fehler:** Analog zu Q14 war auch `scripts/routing_proof.py` ungeschützt. Ein Import startete via `subprocess.Popen` sofort einen Background-Prozess der Courier Server-Applikation und müllte Test-Logs mit HTTP-Fehlern voll.
- **Fix:** Auch hier: `http_post` und Server-Spawn-Logik komplett in `def main():` gekapselt. Ein isolierter Test `tests/test_routing_proof.py` mockt `subprocess.Popen` sowie die `http_post` Antworten (um den Linux- und Windows-Worker korrekt zu bedienen) und verifiziert die Assertion-Reihenfolge.
- **Check/Test:** Testsuite erfolgreich (`1 passed`).
