from courier_core.file_mutation_receipt import FileMutationReceipt
from courier_core.rollback_receipt import RollbackReceipt

def test_file_mutation_receipt():
    orig_content = "def foo(): pass"
    new_content = "def foo(): return True"
    
    receipt = FileMutationReceipt(
        filepath="/src/main.py",
        before_hash=FileMutationReceipt.hash_content(orig_content),
        after_hash=FileMutationReceipt.hash_content(new_content),
        evidence_snippet="return True",
        rollback_patch="--- orig\n+++ new\n"
    )
    
    assert receipt.verify_mutation_changed_state() is True
    
    # Identical hashes = mutation didn't actually change state
    noop_receipt = FileMutationReceipt("/src/main.py", "hash1", "hash1", "", None)
    assert noop_receipt.verify_mutation_changed_state() is False

def test_rollback_receipt_verification():
    original_hash = "hash_A"
    mutated_hash = "hash_B"
    
    # Successful rollback: goes from B back to A
    success_receipt = RollbackReceipt(
        target_mutation_id="mut-1",
        before_rollback_hash=mutated_hash,
        after_rollback_hash=original_hash,
        original_before_hash=original_hash
    )
    assert success_receipt.is_verified_success() is True
    
    # Failed rollback: goes from B to C (doesn't match A)
    fail_receipt = RollbackReceipt(
        target_mutation_id="mut-1",
        before_rollback_hash=mutated_hash,
        after_rollback_hash="hash_C",
        original_before_hash=original_hash
    )
    assert fail_receipt.is_verified_success() is False
