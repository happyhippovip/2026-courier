"""Global pytest configuration and default safe test environment."""
import os

# Provide dummy test keys so importing server/app.py during test collection
# does not abort with SystemExit("Missing COURIER_API_KEY environment variable").
os.environ.setdefault("COURIER_API_KEY", "test-courier-key")
os.environ.setdefault("COURIER_VERIFIER_API_KEY", "test-verifier-key")
