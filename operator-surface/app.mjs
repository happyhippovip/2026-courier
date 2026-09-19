import { addCandidateToBoard, addThought, cannonPreview, contextPreview, createGoal, createGoalCandidate, createProject, createSurfaceResult, deriveBoard, deriveHumanInbox, fireCannon, firstRunStatus, ingestGitHubSnapshot, loadState, morningView, myDay, proposeProjectMatch, recentEntities, resultSectionText, safeActualConcurrency, saveState, setGovernor, toggleFavorite, transitionWorkItem } from "./core.mjs";

let state = loadState(localStorage);
let selectedGoal = state.goals.at(-1)?.goal_id || null;
let selectedPreview = state.previews.at(-1)?.preview_id || null;
let selectedResult = state.results.at(-1)?.result_id || null;
let selectedResultTab = "answer";
let selectedThought = null;

const byId = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));

function status(message, kind = "info") {
  byId("status").textContent = message;
  byId("status").dataset.kind = kind;
}

function persist(next) {
  state = saveState(localStorage, next);
  render();
}

function render() {
  byId("model-calls").textContent = String(state.modelCalls);
  byId("power-mode").value = state.settings.power;
  byId("max-tasks").value = String(state.settings.maxTasks);
  byId("goals").innerHTML = state.goals.length ? state.goals.map((goal) => `
    <button class="list-item ${goal.goal_id === selectedGoal ? "selected" : ""}" data-goal="${goal.goal_id}">
      <strong>${escapeHtml(goal.title)}</strong><small>${escapeHtml(goal.status)} · ${escapeHtml(goal.goal_id)}</small>
    </button>`).join("") : '<p class="empty">No goals yet.</p>';
  byId("projects").innerHTML = state.projects.map((project) => `<article class="thought"><strong>${escapeHtml(project.name)}</strong><p>${escapeHtml(project.description)}</p><small>${escapeHtml(project.status)} · ${escapeHtml(project.project_id)}</small></article>`).join("") || '<p class="empty">No project drafts.</p>';
  byId("thoughts").innerHTML = state.thoughts.filter((thought) => thought.goal_id === selectedGoal).map((thought) => `
    <article class="thought"><p>${escapeHtml(thought.content)}</p><small>${escapeHtml(thought.provider)} · ${escapeHtml(thought.contributor)} · ${escapeHtml(thought.dedup_key)}</small><button data-thought="${thought.contribution_id}">Project / Goal Preview</button></article>`).join("") || '<p class="empty">No thoughts for this goal.</p>';
  const preview = state.previews.find((item) => item.preview_id === selectedPreview && item.goal_id === selectedGoal)
    || [...state.previews].reverse().find((item) => item.goal_id === selectedGoal);
  selectedPreview = preview?.preview_id || null;
  byId("work").innerHTML = preview ? preview.candidates.map((item) => `
    <article class="work-item"><span class="tag ${item.classification.toLowerCase()}">${item.classification}</span><p>${escapeHtml(item.text)}</p><small>${item.execution_status} · ${item.fingerprint}</small><button data-board-candidate="${item.candidate_id}">Add to Task Board</button></article>`).join("") || '<p class="empty">Preview contains no candidates.</p>' : '<p class="empty">Run Cannon Preview to derive work. Nothing executes during preview.</p>';
  const board = deriveBoard(state);
  byId("task-board").innerHTML = Object.entries(board).map(([column, items]) => `<section class="board-column"><strong>${column} <small>${items.length}</small></strong>${items.map((item) => `<article><p>${escapeHtml(item.objective)}</p><small>${escapeHtml(item.work_id)}</small></article>`).join("") || '<p class="empty">—</p>'}</section>`).join("");
  const capacity = safeActualConcurrency(state, { independentReady: board.READY.length, qualifiedWorkers: 0, scopeSafe: board.READY.length, resources: state.settings.maxTasks, provider: 0 });
  byId("governor-readout").textContent = `${state.settings.power} ceiling ${capacity.ceiling} · safe actual ${capacity.actual} · limited by ${capacity.limiting_factors.join(", ")}`;
  const human = deriveHumanInbox(state);
  byId("human-inbox").innerHTML = human.map((item) => `<article class="thought"><p>${escapeHtml(item.question)}</p><small>Default: ${item.automatic_default}</small><button data-approve-work="${item.work_id}">Approve to READY</button></article>`).join("") || '<p class="empty">No genuine decisions.</p>';
  const day = myDay(state);
  byId("my-day").innerHTML = Object.entries({ ...day, favorites: state.favorites.length, recent: Math.min(state.goals.length, 5) }).map(([key, value]) => `<span><b>${value}</b><small>${key}</small></span>`).join("");
  byId("recent").innerHTML = recentEntities(state).map((item) => `<article class="thought"><strong>${escapeHtml(item.title)}</strong><small>${item.type} · ${escapeHtml(item.id)}${state.favorites.includes(item.id) ? " · FAVORITE" : ""}</small></article>`).join("") || '<p class="empty">No recent projects or goals.</p>';
  byId("github-today").innerHTML = state.githubSnapshots.slice(-3).reverse().map((item) => `<article class="thought"><strong>${escapeHtml(item.repository)}</strong><p>${escapeHtml(item.branch || "unknown branch")} · ${escapeHtml(item.head_sha)}</p><small>${item.checks?.length || 0} checks · ${item.pull_requests?.length || 0} PRs · ${escapeHtml(item.source)}</small></article>`).join("") || '<p class="empty">No operator-supplied snapshot. No network call is made.</p>';
  const firstRun = firstRunStatus(state);
  byId("first-run").innerHTML = firstRun.steps.map((step) => `<article class="thought"><strong>${step.done ? "✓" : "○"} ${escapeHtml(step.id)}</strong>${step.reason ? `<small>${escapeHtml(step.reason)}</small>` : ""}</article>`).join("");
  byId("result-list").innerHTML = state.results.map((item) => `<button class="list-item ${item.result_id === selectedResult ? "selected" : ""}" data-result="${item.result_id}"><strong>${escapeHtml(item.status)}</strong><small>${escapeHtml(item.result_id)} · ${escapeHtml(item.task_id || "NO_TASK")}</small></button>`).join("") || '<p class="empty">No execution results. Fire is fail-closed until a real adapter exists.</p>';
  const result = state.results.find((item) => item.result_id === selectedResult) || state.results.at(-1);
  selectedResult = result?.result_id || null;
  document.querySelectorAll("[data-result-tab]").forEach((button) => button.classList.toggle("selected", button.dataset.resultTab === selectedResultTab));
  byId("result-content").textContent = result ? (resultSectionText(result, selectedResultTab) || "UNPROVEN / no durable content") : "No result selected.";
  byId("copy-section").disabled = !result;
  byId("copy-all").disabled = !result;
  byId("preview-button").disabled = !selectedGoal;
  byId("fire-button").disabled = !selectedPreview;
  document.querySelectorAll("[data-goal]").forEach((button) => button.addEventListener("click", () => { selectedGoal = button.dataset.goal; selectedPreview = null; render(); }));
  document.querySelectorAll("[data-result]").forEach((button) => button.addEventListener("click", () => { selectedResult = button.dataset.result; render(); }));
  document.querySelectorAll("[data-thought]").forEach((button) => button.addEventListener("click", () => {
    selectedThought = button.dataset.thought;
    const match = proposeProjectMatch(state, selectedThought);
    const projectId = match.candidates[0]?.project_id || null;
    const candidate = createGoalCandidate(state, selectedThought, projectId);
    byId("candidate-output").textContent = JSON.stringify({ project_match: match, goal_candidate: candidate }, null, 2);
  }));
  document.querySelectorAll("[data-board-candidate]").forEach((button) => button.addEventListener("click", () => {
    try { const outcome = addCandidateToBoard(state, selectedPreview, button.dataset.boardCandidate); persist(outcome.state); status(outcome.duplicate ? "Existing work item reused." : "Work item added without execution.", outcome.duplicate ? "warn" : "ok"); }
    catch (error) { status(error.message, "error"); }
  }));
  document.querySelectorAll("[data-approve-work]").forEach((button) => button.addEventListener("click", () => {
    try { persist(transitionWorkItem(state, button.dataset.approveWork, "READY")); status("Human decision recorded locally; no execution started.", "ok"); }
    catch (error) { status(error.message, "error"); }
  }));
}

byId("project-form").addEventListener("submit", (event) => {
  event.preventDefault();
  try { const outcome = createProject(state, { name: byId("project-name").value, description: byId("project-description").value }); persist(outcome.state); event.target.reset(); status(`Project draft created: ${outcome.project.project_id}`, "ok"); }
  catch (error) { status(error.message, "error"); }
});

byId("github-form").addEventListener("submit", (event) => {
  event.preventDefault();
  try { const outcome = ingestGitHubSnapshot(state, JSON.parse(byId("github-snapshot").value)); persist(outcome.state); status(outcome.duplicate ? "Snapshot already exists; reused." : "Read-only GitHub snapshot stored.", outcome.duplicate ? "warn" : "ok"); }
  catch (error) { status(error.message, "error"); }
});

function updateGovernor() {
  try { persist(setGovernor(state, { power: byId("power-mode").value, maxTasks: Number(byId("max-tasks").value) })); status("Governor ceiling updated; no workers were launched.", "ok"); }
  catch (error) { status(error.message, "error"); }
}
byId("power-mode").addEventListener("change", updateGovernor);
byId("max-tasks").addEventListener("change", updateGovernor);

byId("goal-form").addEventListener("submit", (event) => {
  event.preventDefault();
  try {
    const outcome = createGoal(state, { title: byId("goal-title").value, objective: byId("goal-objective").value });
    selectedGoal = outcome.goal.goal_id;
    persist(outcome.state);
    event.target.reset();
    status(`Goal and durable ThoughtPackage created: ${outcome.thoughtPackage.package_id}`, "ok");
  } catch (error) { status(error.message, "error"); }
});

byId("thought-form").addEventListener("submit", (event) => {
  event.preventDefault();
  try {
    const outcome = addThought(state, { goalId: selectedGoal, content: byId("thought-content").value, provider: byId("thought-provider").value || "human" });
    if (!outcome.duplicate) persist(outcome.state);
    event.target.reset();
    status(outcome.duplicate ? `Duplicate detected: ${outcome.thought.dedup_key}` : `Thought stored with provenance: ${outcome.thought.contribution_id}`, outcome.duplicate ? "warn" : "ok");
  } catch (error) { status(error.message, "error"); }
});

byId("preview-button").addEventListener("click", () => {
  try {
    const outcome = cannonPreview(state, selectedGoal);
    selectedPreview = outcome.preview.preview_id;
    persist(outcome.state);
    status(`Preview created ${outcome.preview.candidates.length} deduplicated candidates; executions: 0`, "ok");
  } catch (error) { status(error.message, "error"); }
});

byId("fire-button").addEventListener("click", () => {
  try {
    const outcome = fireCannon(state, selectedPreview);
    const stored = createSurfaceResult(outcome.state, { status: outcome.result.status, answer: outcome.result.reason, evidence: outcome.result.evidence, next_action: outcome.result.next_action, provenance: { source: "cannon-fire-boundary", execution: "NOT_EXECUTED" } });
    selectedResult = stored.result.result_id;
    persist(stored.state);
    status(outcome.result.reason, "warn");
  } catch (error) { status(error.message, "error"); }
});

document.querySelectorAll("[data-result-tab]").forEach((button) => button.addEventListener("click", () => { selectedResultTab = button.dataset.resultTab; render(); }));

async function copyText(text, label) {
  try { await navigator.clipboard.writeText(text); status(`${label} copied from durable result.`, "ok"); }
  catch { status("Clipboard permission unavailable; nothing was changed.", "error"); }
}

byId("copy-section").addEventListener("click", () => {
  const result = state.results.find((item) => item.result_id === selectedResult);
  if (result) copyText(resultSectionText(result, selectedResultTab), selectedResultTab);
});

byId("copy-all").addEventListener("click", () => {
  const result = state.results.find((item) => item.result_id === selectedResult);
  if (result) copyText(JSON.stringify(result, null, 2), "Result");
});

byId("expert-toggle").addEventListener("change", (event) => {
  document.body.classList.toggle("expert", event.target.checked);
  status("Expert View changed display only; model calls remain 0.", "ok");
});

byId("favorite-goal").addEventListener("click", () => {
  if (!selectedGoal) return status("Select a goal first.", "warn");
  try { persist(toggleFavorite(state, selectedGoal)); status("Favorite state updated locally.", "ok"); }
  catch (error) { status(error.message, "error"); }
});

byId("context-preview").addEventListener("click", () => {
  if (!selectedGoal) return status("Select a goal first.", "warn");
  try { byId("context-output").textContent = JSON.stringify(contextPreview(state, selectedGoal), null, 2); status("Context preview created with zero execution.", "ok"); }
  catch (error) { status(error.message, "error"); }
});

byId("morning-view").addEventListener("click", () => {
  byId("context-output").textContent = JSON.stringify(morningView(state), null, 2);
  status("Morning View generated locally with zero model calls.", "ok");
});

render();
