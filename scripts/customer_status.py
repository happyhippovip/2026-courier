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
    return STATUS_MAP.get(raw_status, "WAITING")

if __name__ == "__main__":
    print(f"Test mapping EXECUTING -> {get_customer_status('EXECUTING')}")
