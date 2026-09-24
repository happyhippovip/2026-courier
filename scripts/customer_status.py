import json
import os
import sys

try:
    from scripts.customer_status_view import map_internal_to_customer_status
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from scripts.customer_status_view import map_internal_to_customer_status

STATUS_MAP = {
    "IDLE": "QUEUED",
    "ASSIGNED": "RUNNING",
    "EXECUTING": "RUNNING",
    "PENDING_PROVIDER": "WAITING",
    "PENDING_APPROVAL": "NEEDS_APPROVAL",
    "COMPLETED": "DONE",
    "FAILED": "FAILED",
    "ORPHANED": "QUEUED" # Retried
}

def get_customer_status(raw_status: str) -> str:
    mapped = STATUS_MAP.get(raw_status)
    if mapped:
        return mapped
    return map_internal_to_customer_status(raw_status)

if __name__ == "__main__":
    print(f"Test mapping EXECUTING -> {get_customer_status('EXECUTING')}")
