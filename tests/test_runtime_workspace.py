"""Tests for courier_runtime.workspace."""

from courier_runtime.workspace import Step, Workspace


def test_step_dataclass():
    step = Step(name="build", argv=["echo", "hi"], output="out.txt")
    assert step.name == "build"
    assert step.argv == ["echo", "hi"]
    assert step.output == "out.txt"
    assert step.effect_class == "idempotent"
