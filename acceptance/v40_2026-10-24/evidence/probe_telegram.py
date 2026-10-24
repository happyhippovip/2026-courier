"""Does the controller accept the telegram_delivery task that ai_ranking_worker posts, before and after F-C1 (#846)?"""
import tempfile
from pathlib import Path
from courier_core.controller import Controller, ApiError
home = Path(tempfile.mkdtemp())
ctrl = Controller(home).boot()
body = {"adapter": "telegram_delivery", "effect_class": "idempotent", "max_attempts": 3, "lease_ttl_s": 60,
        "params": {"article_id": "a1", "title": "t", "content_text": "bitcoin"}, "idempotency_key": "telegram:a1"}
try:
    status, view = ctrl.create_task(body)
    print("ACCEPTED", status, view.get("status"))
except ApiError as exc:
    print("REJECTED", exc.status, exc.code, str(exc)[:120])
finally:
    ctrl.stop()
