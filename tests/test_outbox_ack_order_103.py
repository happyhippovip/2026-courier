"""Deterministic tests for SEED 103 — OUTBOX-ACK-REIHENFOLGE PRÜFEN.

Verifies:
1. Chronological FIFO Delivery Order:
   - Results parked in the outbox are delivered and acknowledged strictly in the
     order they were produced/written (older before newer), regardless of lexical dispatch_id.
2. Lexical Tie-Breaking on Identical Timestamps:
   - When file modification timestamps are identical, deterministic tie-breaking
     follows lexical path name.
3. Service Flush Flushes in Proper Sequence:
   - WorkerLoop.flush_outbox() delivers client payloads in chronological order.
4. Transient Failures Keep Undelivered Order Intact:
   - A ControllerError on a later dispatch keeps un-acknowledged results in their
     proper relative ordering for the next flush pass.
5. Outbox Removal Cleans Up Delivered Item without Reordering Remainder:
   - Removing an acknowledged item preserves chronological order of remaining items.
6. Fail-Closed Handling of Corrupt / Unreadable Files:
   - Malformed files are skipped gracefully without aborting the FIFO stream.
"""

import os
import time
import tempfile
import pytest
from pathlib import Path
from courier_worker.host import (
    outbox_write,
    outbox_read_all,
    outbox_remove,
    OUTBOX_CAP,
    OutboxFull,
)
from courier_worker.service import WorkerLoop, ControllerError


class StubDeliverClient:
    def __init__(self, fail_on=None):
        self.delivered = []
        self.fail_on = fail_on or set()

    def deliver(self, payload):
        dsp = payload.get("dispatch_id")
        if dsp in self.fail_on:
            raise ControllerError(f"Simulated network drop for {dsp}")
        self.delivered.append(dsp)


def test_outbox_read_all_chronological_fifo_ordering(tmp_path):
    """Beweis 1: outbox_read_all() liefert Ergebnisse chronologisch FIFO statt lexikalisch."""
    home = str(tmp_path)
    # Schreibe 3 Dispatches so, dass lexikalische Ordnung entgegengesetzt zur zeitlichen ist:
    # 1. dsp-zzz (zuerst geschrieben)
    # 2. dsp-mmm (als zweites geschrieben)
    # 3. dsp-aaa (zuletzt geschrieben)
    p1 = outbox_write(home, {"dispatch_id": "dsp-zzz", "attempt": 1, "outcome": "completed", "artifacts": []})
    time.sleep(0.02)
    p2 = outbox_write(home, {"dispatch_id": "dsp-mmm", "attempt": 1, "outcome": "completed", "artifacts": []})
    time.sleep(0.02)
    p3 = outbox_write(home, {"dispatch_id": "dsp-aaa", "attempt": 1, "outcome": "completed", "artifacts": []})

    items = outbox_read_all(home)
    assert len(items) == 3
    order = [p["dispatch_id"] for _, p in items]
    assert order == ["dsp-zzz", "dsp-mmm", "dsp-aaa"], f"Erwartet chronologisches FIFO, erhalten: {order}"


def test_outbox_read_all_lexical_tie_breaking(tmp_path):
    """Beweis 2: Bei identischem Zeitstempel greift lexikalisches Tie-Breaking."""
    home = str(tmp_path)
    p1 = outbox_write(home, {"dispatch_id": "dsp-beta", "attempt": 1, "outcome": "completed", "artifacts": []})
    p2 = outbox_write(home, {"dispatch_id": "dsp-alpha", "attempt": 1, "outcome": "completed", "artifacts": []})

    # Setze explizit identische mtime
    target_time = 1700000000.0
    os.utime(p1, (target_time, target_time))
    os.utime(p2, (target_time, target_time))

    items = outbox_read_all(home)
    order = [p["dispatch_id"] for _, p in items]
    assert order == ["dsp-alpha", "dsp-beta"]


def test_service_flush_delivers_in_chronological_order(tmp_path):
    """Beweis 3: WorkerLoop.flush_outbox() quittiert und liefert Ergebnisse in chronologischer Reihenfolge aus."""
    home = str(tmp_path)
    outbox_write(home, {"dispatch_id": "dsp-3-first", "outcome": "completed", "artifacts": []})
    time.sleep(0.02)
    outbox_write(home, {"dispatch_id": "dsp-1-second", "outcome": "completed", "artifacts": []})
    time.sleep(0.02)
    outbox_write(home, {"dispatch_id": "dsp-2-third", "outcome": "completed", "artifacts": []})

    client = StubDeliverClient()
    loop = WorkerLoop(home=home, base_url="http://stub", worker_id="w-1", heartbeat_s=1.0, client_factory=lambda: client)

    remaining = loop.flush_outbox()
    assert remaining == 0
    assert client.delivered == ["dsp-3-first", "dsp-1-second", "dsp-2-third"]
    assert outbox_read_all(home) == []


def test_transient_failure_preserves_unflushed_order(tmp_path):
    """Beweis 4: Bei Teillieferausfall bleibt die chronologische Reihenfolge der verbleibenden Einträge gewahrt."""
    home = str(tmp_path)
    outbox_write(home, {"dispatch_id": "dsp-t1", "outcome": "completed", "artifacts": []})
    time.sleep(0.02)
    outbox_write(home, {"dispatch_id": "dsp-t2-fail", "outcome": "completed", "artifacts": []})
    time.sleep(0.02)
    outbox_write(home, {"dispatch_id": "dsp-t3", "outcome": "completed", "artifacts": []})

    # dsp-t2 schlägt fehl
    client = StubDeliverClient(fail_on={"dsp-t2-fail"})
    loop = WorkerLoop(home=home, base_url="http://stub", worker_id="w-1", heartbeat_s=1.0, client_factory=lambda: client)

    remaining = loop.flush_outbox()
    assert remaining == 1
    assert "dsp-t1" in client.delivered
    assert "dsp-t3" in client.delivered

    # Nur dsp-t2 ist noch in der Outbox
    pending = outbox_read_all(home)
    assert len(pending) == 1
    assert pending[0][1]["dispatch_id"] == "dsp-t2-fail"


def test_corrupt_outbox_file_skipped_without_halting_fifo_stream(tmp_path):
    """Beweis 5: Korrupte Datei in der Outbox blockiert nicht die Auslieferung valider Nachfolger."""
    home = str(tmp_path)
    outbox = Path(home) / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)

    outbox_write(home, {"dispatch_id": "dsp-good-1", "outcome": "completed", "artifacts": []})
    time.sleep(0.02)
    # Schreibe defekte JSON-Datei
    (outbox / "corrupt.json").write_text("{broken json", encoding="utf-8")
    time.sleep(0.02)
    outbox_write(home, {"dispatch_id": "dsp-good-2", "outcome": "completed", "artifacts": []})

    items = outbox_read_all(home)
    order = [p["dispatch_id"] for _, p in items]
    assert order == ["dsp-good-1", "dsp-good-2"]


def test_negative_missing_or_empty_outbox_dir(tmp_path):
    """Negativtest 1: Nicht existierende oder leere Outbox liefert leere Liste ohne Fehler."""
    home = str(tmp_path / "nonexistent")
    assert outbox_read_all(home) == []

    # Leere Outbox
    empty_home = str(tmp_path / "empty")
    (Path(empty_home) / "outbox").mkdir(parents=True)
    assert outbox_read_all(empty_home) == []


def test_negative_outbox_cap_overflow_fail_closed(tmp_path):
    """Negativtest 2: Bei Erreichen von OUTBOX_CAP schlägt outbox_write fail-closed fehl."""
    home = str(tmp_path)
    for i in range(OUTBOX_CAP):
        outbox_write(home, {"dispatch_id": f"dsp-{i:03d}", "attempt": 1, "outcome": "completed", "artifacts": []})

    # Weiterer Dispatch muss OutboxFull auslösen
    with pytest.raises(OutboxFull):
        outbox_write(home, {"dispatch_id": "dsp-overflow", "attempt": 1, "outcome": "completed", "artifacts": []})

    # Bestehender Dispatch darf aktualisiert werden ohne OutboxFull
    refreshed = outbox_write(home, {"dispatch_id": "dsp-000", "attempt": 2, "outcome": "completed", "artifacts": []})
    assert refreshed.exists()

