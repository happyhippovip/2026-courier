import json
import uuid
import datetime

# In-memory registry for 21 genesis blocks
GENESIS_BLOCKS = {i: None for i in range(1, 22)}

def reserve_block(company_name, logo_url):
    """Reserves the next available Genesis block (1-21) and generates a BTC invoice stub."""
    for block_id in range(1, 22):
        if GENESIS_BLOCKS[block_id] is None:
            invoice_id = "INV-" + uuid.uuid4().hex[:8].upper()
            GENESIS_BLOCKS[block_id] = {
                "company_name": company_name,
                "logo_url": logo_url,
                "status": "PENDING_PAYMENT",
                "invoice_id": invoice_id,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "btc_address": "bc1q" + uuid.uuid4().hex[:30], # Stub address
                "amount_eur": 499,
                "amount_btc": 0.0125 # Stub exchange rate
            }
            return {"status": "success", "block_id": block_id, "invoice": GENESIS_BLOCKS[block_id]}
    return {"status": "error", "message": "All 21 Genesis blocks are reserved."}

def get_genesis_registry():
    return GENESIS_BLOCKS
