from pathlib import Path


def test_sleep_mode_uses_persistent_idle():
    source = Path("scripts/run_autonomous_supervisor.py").read_text(encoding="utf-8")

    assert "persistent_idle: bool = True" in source
    assert "idle_backoff_seconds: float = 30.0" in source
    assert "if not persistent_idle:" in source
    assert "[IDLE BACKOFF]" in source
    assert '"idle_backoff_cycles": idle_backoff_cycles' in source
    assert "persistent_idle=False" in source
    assert "persistent_idle=True" in source


def test_persistent_idle_does_not_use_idle_stop_path():
    source = Path("scripts/run_autonomous_supervisor.py").read_text(encoding="utf-8")

    idle_block_start = source.index("if not next_opp:")
    idle_block_end = source.index("empty_queue_checks = 0", idle_block_start)
    idle_block = source[idle_block_start:idle_block_end]

    assert 'stop_reason = "IDLE_MONITORING_NO_WORK"' in idle_block
    assert "if not persistent_idle:" in idle_block
    assert "time.sleep(sleep_for)" in source
