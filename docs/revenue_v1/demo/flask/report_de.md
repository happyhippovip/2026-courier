# GitHub Actions Safety Baseline - Bericht

**Repository:** pallets/flask
**Commit:** d086db856be187255b8ec61ef409357393020f32
**Geprüfte Workflow-Dateien:** 5
**Befunde:** 5

## Befunde

### 1. Fehlendes timeout-minutes - `lock.yaml`

- **Regel:** `timeout`
- **Schweregrad:** NIEDRIG
- **Erklärung:** Ohne Zeitlimit kann ein hängender Job bis zum GitHub-Standardlimit (6 Stunden) laufen und Runner-Minuten verbrauchen.
- **Fix-Hinweis:** Pro Job ein passendes Zeitlimit setzen.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
```

### 2. Fehlendes timeout-minutes - `pre-commit.yaml`

- **Regel:** `timeout`
- **Schweregrad:** NIEDRIG
- **Erklärung:** Ohne Zeitlimit kann ein hängender Job bis zum GitHub-Standardlimit (6 Stunden) laufen und Runner-Minuten verbrauchen.
- **Fix-Hinweis:** Pro Job ein passendes Zeitlimit setzen.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
```

### 3. Fehlendes timeout-minutes - `publish.yaml`

- **Regel:** `timeout`
- **Schweregrad:** NIEDRIG
- **Erklärung:** Ohne Zeitlimit kann ein hängender Job bis zum GitHub-Standardlimit (6 Stunden) laufen und Runner-Minuten verbrauchen.
- **Fix-Hinweis:** Pro Job ein passendes Zeitlimit setzen.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
```

### 4. Fehlendes timeout-minutes - `tests.yaml`

- **Regel:** `timeout`
- **Schweregrad:** NIEDRIG
- **Erklärung:** Ohne Zeitlimit kann ein hängender Job bis zum GitHub-Standardlimit (6 Stunden) laufen und Runner-Minuten verbrauchen.
- **Fix-Hinweis:** Pro Job ein passendes Zeitlimit setzen.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
```

### 5. Fehlendes timeout-minutes - `zizmor.yaml`

- **Regel:** `timeout`
- **Schweregrad:** NIEDRIG
- **Erklärung:** Ohne Zeitlimit kann ein hängender Job bis zum GitHub-Standardlimit (6 Stunden) laufen und Runner-Minuten verbrauchen.
- **Fix-Hinweis:** Pro Job ein passendes Zeitlimit setzen.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
```

## Geprüfte Dateien (SHA-256)

- `lock.yaml`: `e05f221702cb1f6eb8548c2c9c7e7a296228f5eabb7bb3d5e7c9e34f766936a6`
- `pre-commit.yaml`: `eac3d145f47081e8ec73ce6f2b0b96738f9e64384b721863971bed2a8d8c10d1`
- `publish.yaml`: `adafd17df08c2bf08cf4c13968a2c11063abb990d06989cc8131b333a72bedde`
- `tests.yaml`: `b9e91de90c44bd4d2926296389d96e20c7105c979afbc228022c198c7b6bc51b`
- `zizmor.yaml`: `bb524d24d8f07bb47ccc5530e3dab8d98b92ab08fdd1acf8afa26bd5d42e9131`

## Wichtige Hinweise

- Geprüft wurden ausschließlich diese Regeln: Self-hosted Runner, timeout-minutes, permissions/write-all, concurrency, git push, pull_request_target, Actions ohne festen Commit-SHA, github.event-Ausdrücke direkt in run:. Die Prüfung erfolgt per Text-/Zeilensuche je Datei, ohne vollständiges YAML-Parsing.
- Nicht geprüft werden u. a. Anwendungscode, Abhängigkeiten, Secrets, wiederverwendbare Workflows/Composite Actions von außerhalb und weitere Injection-Quellen außer github.event.
- Es wird keine Garantie für Sicherheit oder Vollständigkeit gegeben. Fehlende Befunde bedeuten nicht, dass die Workflows sicher sind. Kein Penetrationstest, keine Zertifizierung.
- Dieser Bericht wurde automatisch erzeugt und erfordert vor Auslieferung eine menschliche Durchsicht.
