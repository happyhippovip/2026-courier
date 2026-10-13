# GitHub Actions Safety Baseline - Bericht

**Repository:** psf/requests
**Commit:** 611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60
**Geprüfte Workflow-Dateien:** 8
**Befunde:** 13

## Befunde

### 1. Fehlendes timeout-minutes - `close-issues.yml`

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

### 2. Fehlender concurrency-Block - `close-issues.yml`

- **Regel:** `concurrency`
- **Schweregrad:** NIEDRIG
- **Erklärung:** Mehrere Läufe desselben Workflows können parallel laufen, sich gegenseitig stören und unnötig Minuten verbrauchen.
- **Fix-Hinweis:** Läufe pro Branch gruppieren und veraltete Läufe abbrechen (bei Deploy/Release ggf. cancel-in-progress: false).

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

### 3. Fehlendes timeout-minutes - `codeql-analysis.yml`

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

### 4. Fehlender concurrency-Block - `codeql-analysis.yml`

- **Regel:** `concurrency`
- **Schweregrad:** NIEDRIG
- **Erklärung:** Mehrere Läufe desselben Workflows können parallel laufen, sich gegenseitig stören und unnötig Minuten verbrauchen.
- **Fix-Hinweis:** Läufe pro Branch gruppieren und veraltete Läufe abbrechen (bei Deploy/Release ggf. cancel-in-progress: false).

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

### 5. Fehlender concurrency-Block - `lint.yml`

- **Regel:** `concurrency`
- **Schweregrad:** NIEDRIG
- **Erklärung:** Mehrere Läufe desselben Workflows können parallel laufen, sich gegenseitig stören und unnötig Minuten verbrauchen.
- **Fix-Hinweis:** Läufe pro Branch gruppieren und veraltete Läufe abbrechen (bei Deploy/Release ggf. cancel-in-progress: false).

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

### 6. Fehlendes timeout-minutes - `lock-issues.yml`

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

### 7. Fehlender concurrency-Block - `lock-issues.yml`

- **Regel:** `concurrency`
- **Schweregrad:** NIEDRIG
- **Erklärung:** Mehrere Läufe desselben Workflows können parallel laufen, sich gegenseitig stören und unnötig Minuten verbrauchen.
- **Fix-Hinweis:** Läufe pro Branch gruppieren und veraltete Läufe abbrechen (bei Deploy/Release ggf. cancel-in-progress: false).

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

### 8. Fehlendes timeout-minutes - `publish.yml`

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

### 9. Fehlender concurrency-Block - `publish.yml`

- **Regel:** `concurrency`
- **Schweregrad:** NIEDRIG
- **Erklärung:** Mehrere Läufe desselben Workflows können parallel laufen, sich gegenseitig stören und unnötig Minuten verbrauchen.
- **Fix-Hinweis:** Läufe pro Branch gruppieren und veraltete Läufe abbrechen (bei Deploy/Release ggf. cancel-in-progress: false).

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

### 10. Fehlender concurrency-Block - `run-tests.yml`

- **Regel:** `concurrency`
- **Schweregrad:** NIEDRIG
- **Erklärung:** Mehrere Läufe desselben Workflows können parallel laufen, sich gegenseitig stören und unnötig Minuten verbrauchen.
- **Fix-Hinweis:** Läufe pro Branch gruppieren und veraltete Läufe abbrechen (bei Deploy/Release ggf. cancel-in-progress: false).

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

### 11. Fehlender concurrency-Block - `typecheck.yml`

- **Regel:** `concurrency`
- **Schweregrad:** NIEDRIG
- **Erklärung:** Mehrere Läufe desselben Workflows können parallel laufen, sich gegenseitig stören und unnötig Minuten verbrauchen.
- **Fix-Hinweis:** Läufe pro Branch gruppieren und veraltete Läufe abbrechen (bei Deploy/Release ggf. cancel-in-progress: false).

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

### 12. Fehlendes timeout-minutes - `zizmor.yml`

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

### 13. Fehlender concurrency-Block - `zizmor.yml`

- **Regel:** `concurrency`
- **Schweregrad:** NIEDRIG
- **Erklärung:** Mehrere Läufe desselben Workflows können parallel laufen, sich gegenseitig stören und unnötig Minuten verbrauchen.
- **Fix-Hinweis:** Läufe pro Branch gruppieren und veraltete Läufe abbrechen (bei Deploy/Release ggf. cancel-in-progress: false).

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

## Geprüfte Dateien (SHA-256)

- `close-issues.yml`: `3f9ea1ad83af25e895e749a3864b850c70cfc37ece203ee898cb548596a937dc`
- `codeql-analysis.yml`: `621837a2cb5c3aedc2a047a712235196f3d5f28508dcdb2b2f9160f67d078b9a`
- `lint.yml`: `2adbd62821e06ee622aff3e1e6e283a9cf3e2dcf694a04040b43fd4291d96f99`
- `lock-issues.yml`: `c97a0fb5242dfc6ea4b37ddd18dfe90f9b0c7b7aa8cb3a7575deeed9729bfe5b`
- `publish.yml`: `b55c9f39e16d0b99a73a9730e38bc5327538f52d5d5cc65cec425117b107c98b`
- `run-tests.yml`: `881865cff186f47787598b2a3d7e6e7eb4d56a3fe4c015414c3cd4d90d9cbb90`
- `typecheck.yml`: `8540a9bdf2f7b1797426d781d70a104ac98f2e161abe731d84fb6b29b901de32`
- `zizmor.yml`: `43f564565a5b53ab769ceb2b0d7070af0913137f47be349eec9a01b9c2ef52f2`

## Wichtige Hinweise

- Geprüft wurden ausschließlich diese Regeln: Self-hosted Runner, timeout-minutes, permissions/write-all, concurrency, git push, pull_request_target, Actions ohne festen Commit-SHA, github.event-Ausdrücke direkt in run:. Die Prüfung erfolgt per Text-/Zeilensuche je Datei, ohne vollständiges YAML-Parsing.
- Nicht geprüft werden u. a. Anwendungscode, Abhängigkeiten, Secrets, wiederverwendbare Workflows/Composite Actions von außerhalb und weitere Injection-Quellen außer github.event.
- Es wird keine Garantie für Sicherheit oder Vollständigkeit gegeben. Fehlende Befunde bedeuten nicht, dass die Workflows sicher sind. Kein Penetrationstest, keine Zertifizierung.
- Dieser Bericht wurde automatisch erzeugt und erfordert vor Auslieferung eine menschliche Durchsicht.
