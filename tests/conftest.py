import os

# Fail-closed API keys require dummy values in local testing.
if "COURIER_API_KEY" not in os.environ:
    os.environ["COURIER_API_KEY"] = "local-test-key"
if "COURIER_VERIFIER_API_KEY" not in os.environ:
    os.environ["COURIER_VERIFIER_API_KEY"] = "local-verifier-key"
