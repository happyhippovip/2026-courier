from dataclasses import dataclass
from courier_core.file_mutation_receipt import FileMutationReceipt

@dataclass
class RollbackReceipt:
    """MAC-24: Prove rollback result rather than merely claiming success."""
    target_mutation_id: str
    before_rollback_hash: str
    after_rollback_hash: str
    original_before_hash: str
    
    def is_verified_success(self) -> bool:
        # A rollback is only proven successful if the state after rollback matches the state before the original mutation
        return self.after_rollback_hash == self.original_before_hash
