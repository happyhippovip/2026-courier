import json
import os
import sys
from pathlib import Path

# Fix sys.path for test
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from courier_worker.adapter_runner import main

def test_l08_adapter_runner_passes_effect_key(tmp_path, monkeypatch):
    """
    PROVE: The adapter_runner.py script must extract effect_key from the L3 request
    and pass it down to the adapter's run() function.
    """
    workdir = tmp_path / "work"
    report_path = tmp_path / "report.json"
    req_path = tmp_path / "req.json"

    # We mock the synthetic adapter to capture kwargs
    import adapters.synthetic as synthetic
    captured_kwargs = {}
    
    def fake_run(params, workdir, attempt, **kwargs):
        captured_kwargs.update(kwargs)
        return synthetic.RunResult("success", [], "fake")
    
    monkeypatch.setattr(synthetic, "run", fake_run)

    req_path.write_text(json.dumps({
        "adapter": "synthetic",
        "workdir": str(workdir),
        "report": str(report_path),
        "attempt": 1,
        "params": {"write": "out.txt", "content": "hi"},
        "effect_key": "cfx-12345"
    }))

    assert main([str(req_path)]) == 0

    # Red test: this currently fails because adapter_runner drops effect_key
    assert captured_kwargs.get("effect_key") == "cfx-12345"
