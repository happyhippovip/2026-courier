"""Tests for CP-23 / CQ-23 / GB-LAZYEXP-01: Lazy Expansion Engine & Rule-Bound Waves

Verifies:
1. Vague idea starts nothing: Unspecified or criteria-free requests are strictly rejected.
2. Wave ceilings are enforced: Depth > 3 and task count > 8 are blocked.
3. Repeated expansion event produces zero duplicates (expansion-idempotency).
4. Required successors remain completely discoverable across wave lineage.
5. Required evidence generated: ['recipe', 'wave-state', 'expansion-idempotency'].
"""

import pytest

from courier_core.lazy_expansion_engine import (
    ExpansionRecipe,
    InvalidParentTaskError,
    LazyExpansionEngine,
    VagueIdeaRejectedError,
    WaveCeilingExceededError,
)


def test_vague_idea_is_rejected_starts_nothing():
    engine = LazyExpansionEngine()
    engine.register_parent_task("parent-1", "Build Pipeline")

    # Case A: Empty acceptance criteria
    recipe_empty_criteria = ExpansionRecipe(
        recipe_id="rec-empty",
        name="Speculative Idea",
        description="A vague idea without verifiable criteria",
        acceptance_criteria=[],
        child_task_templates=[{"task_name": "Do something", "acceptance_criteria": ["Valid criterion 12345"]}],
    )
    with pytest.raises(VagueIdeaRejectedError, match="zero acceptance criteria"):
        engine.expand_wave("parent-1", recipe_empty_criteria, wave_number=1)

    # Case B: Trivial criteria (less than 10 characters)
    recipe_trivial_criteria = ExpansionRecipe(
        recipe_id="rec-trivial",
        name="Trivial Idea",
        description="Critieria is just 'works'",
        acceptance_criteria=["ok", "works"],
        child_task_templates=[{"task_name": "Do something", "acceptance_criteria": ["Valid criterion 12345"]}],
    )
    with pytest.raises(VagueIdeaRejectedError, match="too trivial/unspecified"):
        engine.expand_wave("parent-1", recipe_trivial_criteria, wave_number=1)

    # Case C: Empty child templates
    recipe_no_templates = ExpansionRecipe(
        recipe_id="rec-no-tmpl",
        name="Empty Templates",
        description="Has criteria but no actionable child task templates",
        acceptance_criteria=["Must produce a verified report artifact."],
        child_task_templates=[],
    )
    with pytest.raises(VagueIdeaRejectedError, match="zero child task templates"):
        engine.expand_wave("parent-1", recipe_no_templates, wave_number=1)

    # Asserts nothing was materialized
    assert len(engine.materialized_waves) == 0


def test_wave_ceiling_limits_enforced():
    engine = LazyExpansionEngine()
    engine.register_parent_task("parent-root", "Root Task")

    # Valid template helper
    def make_template(i):
        return {
            "task_name": f"Subtask {i}",
            "acceptance_criteria": [f"Must pass component verification test suite #{i}"],
            "required_capabilities": ["python"],
        }

    # Case A: Wave depth ceiling (> 3)
    recipe_valid = ExpansionRecipe(
        recipe_id="rec-valid",
        name="Valid Wave",
        description="Concrete wave recipe",
        acceptance_criteria=["Must build all modules and verify hashes."],
        child_task_templates=[make_template(1)],
    )

    with pytest.raises(WaveCeilingExceededError, match="Wave depth ceiling exceeded: wave 4"):
        engine.expand_wave("parent-root", recipe_valid, wave_number=4)

    # Case B: Tasks per wave ceiling (> 8)
    recipe_too_many_tasks = ExpansionRecipe(
        recipe_id="rec-too-many",
        name="Overloaded Wave",
        description="Creates 9 tasks in a single wave",
        acceptance_criteria=["Must scale safely without unbounded proliferation."],
        child_task_templates=[make_template(i) for i in range(9)],
    )

    with pytest.raises(WaveCeilingExceededError, match="produces 9 tasks \\(maximum allowed per wave is 8\\)"):
        engine.expand_wave("parent-root", recipe_too_many_tasks, wave_number=1)


def test_expansion_idempotency_produces_no_duplicates():
    engine = LazyExpansionEngine()
    engine.register_parent_task("parent-idem", "Idempotency Test Parent")

    recipe = ExpansionRecipe(
        recipe_id="rec-idem-01",
        name="Idempotent Architecture Build",
        description="Defines deterministic 3-task wave",
        acceptance_criteria=["All 3 service contracts must be written and tested."],
        child_task_templates=[
            {
                "task_name": "Auth Service Contract",
                "acceptance_criteria": ["JWT token validation and fingerprint tests pass."],
                "required_capabilities": ["python"],
            },
            {
                "task_name": "Routing Service Contract",
                "acceptance_criteria": ["Capability router returns qualified worker."],
                "required_capabilities": ["python"],
            },
            {
                "task_name": "Storage Service Contract",
                "acceptance_criteria": ["Fencing token check rejects stale epoch."],
                "required_capabilities": ["python"],
            },
        ],
    )

    # First Expansion
    tasks_run1 = engine.expand_wave("parent-idem", recipe, wave_number=1, now=1000.0)
    assert len(tasks_run1) == 3
    task_ids_run1 = [t.task_id for t in tasks_run1]

    # Repeated Expansion with identical event/recipe
    tasks_run2 = engine.expand_wave("parent-idem", recipe, wave_number=1, now=1050.0)
    assert len(tasks_run2) == 3
    task_ids_run2 = [t.task_id for t in tasks_run2]

    # Exact same task IDs, zero duplicate tasks created
    assert task_ids_run1 == task_ids_run2
    assert len(engine.materialized_waves) == 1


def test_required_successors_remain_discoverable():
    engine = LazyExpansionEngine()
    engine.register_parent_task("root-01", "Master Root Pipeline")

    recipe_w1 = ExpansionRecipe(
        recipe_id="rec-w1",
        name="Wave 1 Modules",
        description="Initial core decomposition",
        acceptance_criteria=["Core interfaces must be established."],
        child_task_templates=[
            {"task_name": "Core Module A", "acceptance_criteria": ["Unit test coverage >= 90%."]},
            {"task_name": "Core Module B", "acceptance_criteria": ["Unit test coverage >= 90%."]},
        ],
    )

    # Expand Wave 1
    w1_tasks = engine.expand_wave("root-01", recipe_w1, wave_number=1)
    assert len(w1_tasks) == 2
    child_a_id = w1_tasks[0].task_id

    # Expand Wave 2 from Child A
    recipe_w2 = ExpansionRecipe(
        recipe_id="rec-w2",
        name="Wave 2 Sub-components",
        description="Detailed leaf implementation",
        acceptance_criteria=["Leaf sub-components must be verified."],
        child_task_templates=[
            {"task_name": "Subcomponent A1", "acceptance_criteria": ["Subcomponent A1 passes contract tests."]},
        ],
    )
    w2_tasks = engine.expand_wave(child_a_id, recipe_w2, wave_number=2)
    assert len(w2_tasks) == 1

    # Discover all successors for root
    all_descendants = engine.find_all_descendants("root-01")
    assert len(all_descendants) == 3
    descendant_ids = [t.task_id for t in all_descendants]
    assert w1_tasks[0].task_id in descendant_ids
    assert w1_tasks[1].task_id in descendant_ids
    assert w2_tasks[0].task_id in descendant_ids


def test_lazy_expansion_evidence_generation():
    engine = LazyExpansionEngine()
    engine.register_parent_task("parent-evidence", "Evidence Parent Task")

    recipe = ExpansionRecipe(
        recipe_id="rec-evidence-demo",
        name="Evidence Generation Recipe",
        description="Demonstrates full evidence generation",
        acceptance_criteria=["Must produce recipe, wave-state, and expansion-idempotency."],
        child_task_templates=[
            {"task_name": "Subtask Demo", "acceptance_criteria": ["Contract test for subtask passes."]},
        ],
    )

    evidence = engine.generate_lazy_expansion_evidence(recipe, "parent-evidence")

    assert evidence["required_evidence"] == ["recipe", "wave-state", "expansion-idempotency"]
    assert evidence["recipe"]["recipe_id"] == "rec-evidence-demo"
    assert evidence["wave-state"]["tasks_count"] == 1
    assert evidence["expansion-idempotency"]["idempotency_guaranteed"] is True
    assert evidence["expansion-idempotency"]["duplicate_tasks_created"] == 0
