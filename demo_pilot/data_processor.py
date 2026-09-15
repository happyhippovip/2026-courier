import uuid

def process_records(records, default_status="pending"):
    processed = []
    for r in records:
        rec = dict(r)
        if "id" not in rec or rec["id"] is None:
            rec["id"] = str(uuid.uuid4())
        rec["status"] = rec.get("status", default_status)
        processed.append(rec)
    return processed
