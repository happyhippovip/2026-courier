import assert from "node:assert/strict";
import { addCandidateToBoard, addThought, cannonPreview, contextPreview, createGoal, createGoalCandidate, createProject, createSurfaceResult, deriveBoard, deriveHumanInbox, emptyState, fireCannon, firstRunStatus, ingestGitHubSnapshot, loadState, morningView, myDay, proposeProjectMatch, recentEntities, registerWorkPackage, resultSectionText, safeActualConcurrency, saveState, setGovernor, toggleFavorite, transitionWorkItem } from "./core.mjs";

class MemoryStorage {
  constructor() { this.values = new Map(); }
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, value); }
}

const clock = "2026-09-18T12:00:00.000Z";
let state = emptyState();
const packageFixture = {
  package_id: "bug-end-to-end", version: "1.0.0", title: "Bug", description: "Fix one bug", inputs: ["repo"], goal: "Fix",
  acceptance: ["test passes"], tasks: [{ task_id: "repro", objective: "Reproduce", depends_on: [], write_scope: "tests/" }],
  dependencies: [], required_capabilities: ["test"], read_scopes: ["repo"], write_scopes: ["tests/"], parallel_safe_tasks: [],
  writer_scope: "assigned-writer", verification: ["test"], human_gates: ["MERGE"], cost_policy: "LOCAL_FIRST",
  result_layout: ["DIFF", "TESTS"], failure_policy: "FAIL_CLOSED"
};
let registered = registerWorkPackage(state, packageFixture);
state = registered.state;
assert.equal(registered.entry.status, "REGISTERED_NOT_EXECUTED");
assert.equal(registerWorkPackage(state, packageFixture).duplicate, true);
assert.throws(() => registerWorkPackage(state, { package_id: "bad" }), /Missing Work Package field/);
const projectCreated = createProject(state, { name: "Courier Website", description: "Inspect state and build the Courier website", now: clock });
state = projectCreated.state;
assert.equal(projectCreated.project.execution_authorized, false);
assert.throws(() => createProject(state, { name: "  courier website  " }), /already exists/);
const created = createGoal(state, { title: "Surface acceptance", objective: "Inspect state. Publish later only with approval.", now: clock });
state = created.state;
assert.equal(state.goals.length, 1);
assert.equal(state.packages.length, 1);
assert.equal(state.packages[0].goal_id, state.goals[0].goal_id);

const first = addThought(state, { goalId: created.goal.goal_id, content: "Inspect state. Publish later only with approval.", provider: "provider-neutral", contributor: "tester", now: clock });
state = first.state;
assert.equal(first.duplicate, false);
assert.equal(first.thought.execution_authorized, false);
assert.equal(first.thought.provenance.provider, "provider-neutral");
const match = proposeProjectMatch(state, first.thought.contribution_id);
assert.equal(match.recommendation, "REVIEW_EXISTING_PROJECT");
assert.equal(match.candidates[0].project_id, projectCreated.project.project_id);
assert.equal(match.applied, false);
assert.equal(match.execution_count, 0);
const goalCandidate = createGoalCandidate(state, first.thought.contribution_id, projectCreated.project.project_id);
assert.equal(goalCandidate.status, "DRAFT_NOT_CREATED");
assert.equal(goalCandidate.execution_count, 0);
assert.ok(goalCandidate.constraints.includes("NO_AUTO_SPEND"));
const duplicate = addThought(state, { goalId: created.goal.goal_id, content: "  inspect   state. publish later only with approval. ", provider: "other", contributor: "alias", now: clock });
assert.equal(duplicate.duplicate, true);
assert.equal(duplicate.state.thoughts.length, 1);

const previewed = cannonPreview(state, created.goal.goal_id, clock);
state = previewed.state;
assert.equal(previewed.preview.execution_count, 0);
assert.equal(state.modelCalls, 0);
assert.deepEqual(previewed.preview.candidates.map((item) => item.classification), ["LOCAL_CANDIDATE", "HUMAN_GATE"]);
assert.ok(previewed.preview.candidates.every((item) => item.execution_status === "NOT_EXECUTED"));
assert.equal(previewed.preview.agent_count, 0);

const many = addThought(state, { goalId: created.goal.goal_id, content: Array.from({ length: 12 }, (_, index) => `Inspect bounded item ${index}`).join(". "), now: clock });
const bounded = cannonPreview(many.state, created.goal.goal_id, clock, { maxCandidates: 10 });
assert.equal(bounded.preview.candidates.length, 10);
assert.equal(bounded.preview.overflow_count, 4);
assert.equal(bounded.preview.truncated, true);
assert.equal(bounded.preview.execution_count, 0);
assert.equal(bounded.preview.agent_count, 0);
assert.throws(() => cannonPreview(state, created.goal.goal_id, clock, { maxCandidates: 11 }), /maxCandidates/);

state = setGovernor(state, { power: "TURBO", maxTasks: 10 });
assert.deepEqual(safeActualConcurrency(state, { independentReady: 8, qualifiedWorkers: 2, scopeSafe: 5, resources: 4, provider: 3 }), { actual: 2, ceiling: 3, limiting_factors: ["qualified_workers"] });
assert.equal(safeActualConcurrency(state, { independentReady: 0, qualifiedWorkers: 2, scopeSafe: 5, resources: 4, provider: 3 }).actual, 0);
assert.throws(() => setGovernor(state, { power: "MAX", maxTasks: 10 }), /Unknown power/);

const localCandidate = previewed.preview.candidates.find((item) => item.classification === "LOCAL_CANDIDATE");
const humanCandidate = previewed.preview.candidates.find((item) => item.classification === "HUMAN_GATE");
let boardAdd = addCandidateToBoard(state, previewed.preview.preview_id, localCandidate.candidate_id, clock);
state = boardAdd.state;
assert.equal(boardAdd.item.status, "READY");
assert.equal(boardAdd.item.execution_authorized, false);
assert.equal(addCandidateToBoard(state, previewed.preview.preview_id, localCandidate.candidate_id, clock).duplicate, true);
boardAdd = addCandidateToBoard(state, previewed.preview.preview_id, humanCandidate.candidate_id, clock);
state = boardAdd.state;
assert.equal(boardAdd.item.status, "BRAUCHT_MICH");
assert.equal(deriveHumanInbox(state).length, 1);
assert.equal(deriveBoard(state).READY.length, 1);
assert.equal(myDay(state).needs_me, 1);
assert.equal(contextPreview(state, created.goal.goal_id).execution_authorized, false);
state = toggleFavorite(state, created.goal.goal_id);
assert.deepEqual(state.favorites, [created.goal.goal_id]);
state = transitionWorkItem(state, deriveBoard(state).READY[0].work_id, "RUNNING");
assert.equal(deriveBoard(state).RUNNING.length, 1);
assert.throws(() => transitionWorkItem(state, deriveBoard(state).RUNNING[0].work_id, "DONE"), /durable result/);

const fired = fireCannon(state, previewed.preview.preview_id);
assert.equal(fired.result.status, "UNPROVEN");
assert.equal(fired.result.executed, false);
assert.equal(fired.state.modelCalls, 0);
const stored = createSurfaceResult(fired.state, { status: fired.result.status, answer: fired.result.reason, tests: ["NOT_RUN"], evidence: fired.result.evidence, next_action: fired.result.next_action }, clock);
state = stored.state;
assert.equal(resultSectionText(stored.result, "answer"), fired.result.reason);
assert.equal(resultSectionText(stored.result, "tests"), "NOT_RUN");
assert.equal(resultSectionText(stored.result, "evidence"), "PREVIEW_ONLY\nMODEL_CALLS=0");
assert.throws(() => resultSectionText(stored.result, "unknown"), /Unknown result section/);
state = transitionWorkItem(state, deriveBoard(state).RUNNING[0].work_id, "DONE", stored.result.result_id);
assert.equal(deriveBoard(state).DONE.length, 1);
assert.equal(morningView(state).completed.length, 1);
assert.equal(morningView(state).model_calls, 0);
assert.equal(recentEntities(state)[0].type, "GOAL");
const github = ingestGitHubSnapshot(state, { repository: "example/repo", head_sha: "a".repeat(40), branch: "main", checks: [{ name: "test", status: "PASS" }], pull_requests: [], issues: [], commits: [] }, clock);
state = github.state;
assert.equal(github.duplicate, false);
assert.equal(ingestGitHubSnapshot(state, { repository: "example/repo", head_sha: "a".repeat(40), branch: "main", checks: [{ name: "test", status: "PASS" }], pull_requests: [], issues: [], commits: [] }, clock).duplicate, true);
assert.throws(() => ingestGitHubSnapshot(state, { repository: "example/repo", head_sha: "short" }), /full SHA/);
assert.equal(firstRunStatus(state).local_setup_complete, true);
assert.equal(firstRunStatus(state).customer_execution_ready, false);

const storage = new MemoryStorage();
saveState(storage, state);
const restarted = loadState(storage);
assert.equal(restarted.goals[0].goal_id, created.goal.goal_id);
assert.equal(restarted.projects[0].project_id, projectCreated.project.project_id);
assert.equal(restarted.thoughts[0].dedup_key, first.thought.dedup_key);
assert.equal(restarted.previews[0].execution_count, 0);
assert.equal(restarted.modelCalls, 0);
assert.equal(restarted.results[0].result_id, stored.result.result_id);
assert.equal(restarted.githubSnapshots[0].head_sha, "a".repeat(40));
assert.equal(restarted.registeredPackages[0].identity, "bug-end-to-end@1.0.0");
console.log("operator-surface acceptance: PASS");
