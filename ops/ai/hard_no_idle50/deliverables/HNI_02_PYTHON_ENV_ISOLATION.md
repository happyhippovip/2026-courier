# HNI-02 — Python 3 Interpreter & Standard Library Isolation Verification

## 1. Overview & Authority
- **Task ID**: HNI_02
- **Area**: PYTHON_ENV_ISOLATION
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Authority**: GOOGLE_CLI (Hard No-Idle Finisher)
- **Status**: COMPLETE

## 2. Interpreter Boundary Specifications
- **Python Binary**: Standard `/usr/local/bin/python3` or virtual environment Python 3.9+.
- **Standard Library Isolation**:
  - Server and verification engines MUST rely strictly on built-in standard library packages:
    - `sqlite3` for durable ACID state persistence.
    - `hashlib` for SHA-256 cryptographic verification.
    - `http.server` & `urllib` for coordinator API and test clients.
    - `json` for structured event logging and wire protocol payloads.
    - `sys`, `os`, `signal`, `time` for runtime management.
- **sys.path Hygiene**:
  - System site-packages and user `.local` site-packages MUST NOT override project modules.
  - Isolated execution invoked via `python3 -S` or clean `PYTHONPATH` unset.
- **Environment Scrubbing**:
  - Strip `PYTHONSTARTUP`, `PYTHONHOME`, and non-essential `PYTHON*` environment variables prior to process spawn.
