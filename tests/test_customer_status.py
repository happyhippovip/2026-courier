import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import customer_status

def test_get_customer_status_known_states():
    assert customer_status.get_customer_status("IDLE") == "QUEUED"
    assert customer_status.get_customer_status("ASSIGNED") == "RUNNING"
    assert customer_status.get_customer_status("EXECUTING") == "RUNNING"
    assert customer_status.get_customer_status("PENDING_PROVIDER") == "WAITING"
    assert customer_status.get_customer_status("PENDING_APPROVAL") == "NEEDS_APPROVAL"
    assert customer_status.get_customer_status("COMPLETED") == "DONE"
    assert customer_status.get_customer_status("FAILED") == "FAILED"
    assert customer_status.get_customer_status("ORPHANED") == "QUEUED"

def test_get_customer_status_unknown_state():
    assert customer_status.get_customer_status("SOMETHING_RANDOM") == "WAITING"
    assert customer_status.get_customer_status("") == "WAITING"
    assert customer_status.get_customer_status(None) == "WAITING"

