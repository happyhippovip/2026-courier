from typing import Dict, Any, Optional

class IdempotencyCore:
    """MAC-04: Prevent duplicate execution after retries/restarts."""
    def __init__(self):
        self._record: Dict[str, Any] = {}

    def is_executed(self, transaction_id: str) -> bool:
        return transaction_id in self._record

    def get_result(self, transaction_id: str) -> Optional[Any]:
        return self._record.get(transaction_id)

    def store_result(self, transaction_id: str, result: Any) -> None:
        if self.is_executed(transaction_id):
            raise ValueError(f"Transaction {transaction_id} already executed.")
        self._record[transaction_id] = result
