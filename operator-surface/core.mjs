const VERSION = 1;

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export function fingerprint(value) {
  const text = canonical(value);
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `fp1-${(hash >>> 0).toString(16).padStart(8, "0")}`;
}

export function emptyState() {
  return {
    version: VERSION, projects: [], goals: [], packages: [], thoughts: [], previews: [], results: [],
    workItems: [], registeredPackages: [], favorites: [], activity: [], githubSnapshots: [], settings: { power: "AUTO", maxTasks: 10 }, modelCalls: 0
  };
}

export const POWER_LEVELS = Object.freeze({ AUTO: 20, ECO: 1, QUICK: 2, TURBO: 3, BOOST: 5, HYPER: 10, ULTRA: 15, CANNON: 20 });
export const MAX_TASK_OPTIONS = Object.freeze([10, 20, 50, 100]);
export const BOARD_STATES = Object.freeze(["READY", "RUNNING", "WAITING", "DONE", "BLOCKED", "BRAUCHT_MICH"]);

export function setGovernor(state, { power, maxTasks }) {
  if (!(power in POWER_LEVELS)) throw new Error("Unknown power mode");
  if (!MAX_TASK_OPTIONS.includes(Number(maxTasks))) throw new Error("Invalid max tasks");
  return { ...state, settings: { power, maxTasks: Number(maxTasks) } };
}

export function registerWorkPackage(state, workPackage) {
  const required = ["package_id", "version", "title", "description", "inputs", "goal", "acceptance", "tasks", "dependencies", "required_capabilities", "read_scopes", "write_scopes", "parallel_safe_tasks", "writer_scope", "verification", "human_gates", "cost_policy", "result_layout", "failure_policy"];
  for (const key of required) if (!(key in (workPackage || {}))) throw new Error(`Missing Work Package field: ${key}`);
  if (!/^[a-z0-9][a-z0-9._-]{2,79}$/.test(workPackage.package_id) || !/^\d+\.\d+\.\d+$/.test(workPackage.version)) throw new Error("Invalid Work Package identity");
  if (!Array.isArray(workPackage.tasks) || workPackage.tasks.length < 1 || workPackage.tasks.length > 100) throw new Error("Work Package tasks must contain 1 to 100 items");
  if (!workPackage.writer_scope) throw new Error("Work Package requires one writer scope");
  const identity = `${workPackage.package_id}@${workPackage.version}`;
  const existing = state.registeredPackages.find((item) => item.identity === identity);
  if (existing) return { state, entry: existing, duplicate: true };
  const entry = { identity, package: JSON.parse(JSON.stringify(workPackage)), status: "REGISTERED_NOT_EXECUTED" };
  return { state: { ...state, registeredPackages: [...state.registeredPackages, entry] }, entry, duplicate: false };
}

export function safeActualConcurrency(state, capacity) {
  const ceiling = POWER_LEVELS[state.settings?.power || "AUTO"];
  const values = [ceiling, capacity.independentReady, capacity.qualifiedWorkers, capacity.scopeSafe, capacity.resources, capacity.provider]
    .map(Number).map((value) => Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0);
  const actual = Math.min(...values);
  const labels = ["user_ceiling", "independent_ready", "qualified_workers", "scope_safe", "resources", "provider"];
  return { actual, ceiling, limiting_factors: labels.filter((_, index) => values[index] === actual) };
}

const RESULT_SECTIONS = ["answer", "code", "files", "diff", "tests", "evidence", "next_action"];

export function createSurfaceResult(state, input, now = new Date().toISOString()) {
  const result = {
    result_id: nextId("result", state), status: String(input?.status || "UNPROVEN"), created_at: now,
    task_id: input?.task_id || null, answer: String(input?.answer || input?.reason || ""),
    code: String(input?.code || ""), files: Array.isArray(input?.files) ? input.files.map(String) : [],
    diff: String(input?.diff || ""), tests: Array.isArray(input?.tests) ? input.tests.map(String) : [],
    evidence: Array.isArray(input?.evidence) ? input.evidence.map(String) : [],
    next_action: String(input?.next_action || "No verified next action."),
    provenance: input?.provenance || { source: "operator-surface", execution: "NOT_EXECUTED" }
  };
  return { state: { ...state, results: [...state.results, result] }, result };
}

export function resultSectionText(result, section) {
  if (!RESULT_SECTIONS.includes(section)) throw new Error("Unknown result section");
  const value = result?.[section];
  return Array.isArray(value) ? value.join("\n") : String(value || "");
}

export function loadState(storage, key = "courier-symphony-surface-v1") {
  const raw = storage.getItem(key);
  if (!raw) return emptyState();
  try {
    const parsed = JSON.parse(raw);
    if (parsed.version !== VERSION) return emptyState();
    return { ...emptyState(), ...parsed, modelCalls: 0 };
  } catch {
    return emptyState();
  }
}

export function saveState(storage, state, key = "courier-symphony-surface-v1") {
  storage.setItem(key, JSON.stringify(state));
  return state;
}

function nextId(prefix, state) {
  const total = ["projects", "goals", "packages", "thoughts", "previews", "results", "workItems", "githubSnapshots"]
    .reduce((sum, key) => sum + (state[key]?.length || 0), 0) + 1;
  return `${prefix}-${String(total).padStart(4, "0")}-${Date.now().toString(36)}`;
}

export function createGoal(state, { title, objective, actor = "local-operator", now = new Date().toISOString() }) {
  const cleanTitle = String(title || "").trim();
  const cleanObjective = String(objective || "").trim();
  if (!cleanTitle || !cleanObjective) throw new Error("Goal title and objective are required");
  const goal = {
    goal_id: nextId("goal", state), title: cleanTitle, objective: cleanObjective,
    status: "DRAFT", created_at: now, provenance: { actor, source: "operator-surface", observed_at: now }
  };
  const thoughtPackage = {
    package_id: nextId("package", { ...state, goals: [...state.goals, goal] }), goal_id: goal.goal_id,
    status: "DURABLE_DRAFT", created_at: now, thought_ids: [], provenance: goal.provenance
  };
  return { state: { ...state, goals: [...state.goals, goal], packages: [...state.packages, thoughtPackage] }, goal, thoughtPackage };
}

export function addThought(state, { goalId, content, provider = "human", contributor = "local-operator", now = new Date().toISOString() }) {
  const goal = state.goals.find((item) => item.goal_id === goalId);
  if (!goal) throw new Error("Unknown goal");
  const normalized = String(content || "").trim().replace(/\s+/g, " ");
  if (!normalized) throw new Error("Thought content is required");
  const dedupKey = fingerprint({ goal_id: goalId, content: normalized.toLowerCase() });
  const duplicate = state.thoughts.find((item) => item.dedup_key === dedupKey);
  if (duplicate) return { state, thought: duplicate, duplicate: true };
  const contribution = {
    contribution_id: nextId("thought", state), goal_id: goalId, content: normalized,
    provider, contributor, observed_at: now, dedup_key: dedupKey,
    provenance: { provider, contributor, source: "operator-input", observed_at: now },
    execution_authorized: false
  };
  const packages = state.packages.map((item) => item.goal_id === goalId
    ? { ...item, thought_ids: [...item.thought_ids, contribution.contribution_id], updated_at: now }
    : item);
  return { state: { ...state, thoughts: [...state.thoughts, contribution], packages }, thought: contribution, duplicate: false };
}

export function createProject(state, { name, description = "", workspace = null, actor = "local-operator", now = new Date().toISOString() }) {
  const cleanName = String(name || "").trim();
  if (!cleanName) throw new Error("Project name is required");
  const key = cleanName.toLowerCase().replace(/\s+/g, " ");
  if (state.projects.some((item) => item.match_key === key)) throw new Error("Project already exists");
  const project = {
    project_id: nextId("project", state), name: cleanName, description: String(description || "").trim(),
    workspace, match_key: key, status: "DRAFT", created_at: now,
    provenance: { actor, source: "operator-surface", observed_at: now }, execution_authorized: false
  };
  return { state: { ...state, projects: [...state.projects, project] }, project };
}

function words(value) {
  return new Set(String(value || "").toLowerCase().match(/[a-z0-9äöüß]{3,}/g) || []);
}

export function proposeProjectMatch(state, thoughtId) {
  const thought = state.thoughts.find((item) => item.contribution_id === thoughtId);
  if (!thought) throw new Error("Unknown thought");
  const source = words(thought.content);
  const candidates = state.projects.map((project) => {
    const target = words(`${project.name} ${project.description}`);
    const overlap = [...source].filter((word) => target.has(word)).length;
    return { project_id: project.project_id, score: overlap, decision: overlap > 0 ? "CANDIDATE" : "NO_MATCH" };
  }).filter((item) => item.score > 0).sort((a, b) => b.score - a.score || a.project_id.localeCompare(b.project_id));
  return {
    thought_id: thoughtId, candidates: candidates.slice(0, 3),
    recommendation: candidates.length ? "REVIEW_EXISTING_PROJECT" : "NO_PROJECT_YET",
    applied: false, execution_count: 0
  };
}

export function createGoalCandidate(state, thoughtId, projectId = null) {
  const thought = state.thoughts.find((item) => item.contribution_id === thoughtId);
  if (!thought) throw new Error("Unknown thought");
  if (projectId && !state.projects.some((item) => item.project_id === projectId)) throw new Error("Unknown project");
  return {
    candidate_id: `goal-candidate-${thought.dedup_key.slice(4)}`, thought_id: thoughtId, project_id: projectId,
    intent: thought.content, goal: `Resolve: ${thought.content}`, constraints: ["NO_AUTO_SPEND", "NO_UNATTENDED_EXTERNAL_EFFECTS"],
    acceptance: ["Outcome is independently reviewable"], required_capabilities: [], human_gates: [],
    status: "DRAFT_NOT_CREATED", execution_count: 0
  };
}

export function addCandidateToBoard(state, previewId, candidateId, now = new Date().toISOString()) {
  const preview = state.previews.find((item) => item.preview_id === previewId);
  const candidate = preview?.candidates.find((item) => item.candidate_id === candidateId);
  if (!candidate) throw new Error("Unknown preview candidate");
  const existing = state.workItems.find((item) => item.fingerprint === candidate.fingerprint);
  if (existing) return { state, item: existing, duplicate: true };
  if (state.workItems.length >= state.settings.maxTasks) throw new Error("Maximum planned tasks reached");
  const needsHuman = candidate.classification === "HUMAN_GATE";
  const item = {
    work_id: nextId("work", state), goal_id: preview.goal_id, source_candidate_id: candidateId,
    objective: candidate.text, fingerprint: candidate.fingerprint, status: needsHuman ? "BRAUCHT_MICH" : "READY",
    created_at: now, execution_authorized: false, result_id: null
  };
  return { state: { ...state, workItems: [...state.workItems, item] }, item, duplicate: false };
}

export function transitionWorkItem(state, workId, nextStatus, resultId = null) {
  if (!BOARD_STATES.includes(nextStatus)) throw new Error("Invalid board state");
  const current = state.workItems.find((item) => item.work_id === workId);
  if (!current) throw new Error("Unknown work item");
  const allowed = {
    READY: ["RUNNING", "WAITING", "BLOCKED", "BRAUCHT_MICH"], RUNNING: ["DONE", "WAITING", "BLOCKED", "BRAUCHT_MICH"],
    WAITING: ["READY", "BLOCKED", "BRAUCHT_MICH"], BLOCKED: ["READY", "BRAUCHT_MICH"], BRAUCHT_MICH: ["READY", "BLOCKED"], DONE: []
  };
  if (!allowed[current.status].includes(nextStatus)) throw new Error("Invalid board transition");
  if (nextStatus === "DONE" && !state.results.some((item) => item.result_id === resultId)) throw new Error("DONE requires durable result");
  const workItems = state.workItems.map((item) => item.work_id === workId ? { ...item, status: nextStatus, result_id: resultId || item.result_id } : item);
  return { ...state, workItems };
}

export function deriveBoard(state) {
  return Object.fromEntries(BOARD_STATES.map((status) => [status, state.workItems.filter((item) => item.status === status)]));
}

export function deriveHumanInbox(state) {
  return state.workItems.filter((item) => item.status === "BRAUCHT_MICH").map((item) => ({
    decision_id: `decision-${item.work_id}`, work_id: item.work_id, question: `Authorize or revise: ${item.objective}`,
    options: ["APPROVE_TO_READY", "KEEP_BLOCKED"], automatic_default: "KEEP_BLOCKED"
  }));
}

export function toggleFavorite(state, entityId) {
  const exists = [...state.goals, ...state.projects].some((item) => item.goal_id === entityId || item.project_id === entityId);
  if (!exists) throw new Error("Unknown favorite entity");
  const favorites = state.favorites.includes(entityId) ? state.favorites.filter((id) => id !== entityId) : [...state.favorites, entityId];
  return { ...state, favorites };
}

export function contextPreview(state, goalId) {
  const goal = state.goals.find((item) => item.goal_id === goalId);
  if (!goal) throw new Error("Unknown goal");
  return {
    goal: { goal_id: goal.goal_id, title: goal.title, objective: goal.objective, status: goal.status },
    thought_ids: state.thoughts.filter((item) => item.goal_id === goalId).map((item) => item.contribution_id),
    work_ids: state.workItems.filter((item) => item.goal_id === goalId).map((item) => item.work_id),
    result_ids: state.results.filter((item) => state.workItems.some((work) => work.goal_id === goalId && work.result_id === item.result_id)).map((item) => item.result_id),
    execution_authorized: false
  };
}

export function myDay(state) {
  const board = deriveBoard(state);
  return { ready: board.READY.length, running: board.RUNNING.length, needs_me: board.BRAUCHT_MICH.length, done: board.DONE.length, true_idle: state.workItems.length > 0 && board.READY.length === 0 && board.RUNNING.length === 0 && board.WAITING.length === 0 };
}

export function recentEntities(state, limit = 5) {
  return [...state.goals.map((item) => ({ id: item.goal_id, type: "GOAL", title: item.title, at: item.created_at })),
    ...state.projects.map((item) => ({ id: item.project_id, type: "PROJECT", title: item.name, at: item.created_at }))]
    .sort((a, b) => String(b.at).localeCompare(String(a.at))).slice(0, limit);
}

export function morningView(state) {
  const board = deriveBoard(state);
  return {
    completed: board.DONE.map((item) => item.work_id),
    blocked: [...board.BLOCKED, ...board.BRAUCHT_MICH].map((item) => item.work_id),
    ready_next: board.READY.map((item) => item.work_id),
    waiting: board.WAITING.map((item) => item.work_id),
    results: state.results.map((item) => item.result_id),
    generated_locally: true,
    model_calls: 0
  };
}

export function ingestGitHubSnapshot(state, snapshot, now = new Date().toISOString()) {
  const allowed = ["repository", "head_sha", "branch", "pull_requests", "checks", "issues", "commits"];
  if (!snapshot || typeof snapshot !== "object" || !snapshot.repository || !snapshot.head_sha) throw new Error("GitHub snapshot requires repository and head_sha");
  if (!/^[0-9a-f]{40}$/.test(snapshot.head_sha)) throw new Error("GitHub snapshot requires full SHA");
  const clean = Object.fromEntries(allowed.filter((key) => key in snapshot).map((key) => [key, snapshot[key]]));
  for (const key of ["pull_requests", "checks", "issues", "commits"]) if (key in clean && !Array.isArray(clean[key])) throw new Error(`${key} must be an array`);
  const fingerprintValue = fingerprint(clean);
  const existing = state.githubSnapshots.find((item) => item.fingerprint === fingerprintValue);
  if (existing) return { state, snapshot: existing, duplicate: true };
  const entry = { snapshot_id: nextId("github", state), ...clean, observed_at: now, fingerprint: fingerprintValue, source: "operator-supplied-read-only" };
  return { state: { ...state, githubSnapshots: [...state.githubSnapshots, entry] }, snapshot: entry, duplicate: false };
}

export function firstRunStatus(state) {
  const hasProject = state.projects.length > 0;
  const hasGoal = state.goals.length > 0;
  const hasThought = state.thoughts.length > 0;
  const hasPreview = state.previews.length > 0;
  return {
    steps: [
      { id: "project", done: hasProject }, { id: "goal", done: hasGoal },
      { id: "thought", done: hasThought }, { id: "preview", done: hasPreview },
      { id: "execution", done: false, reason: "Accepted execution adapter not integrated" }
    ],
    local_setup_complete: hasProject && hasGoal && hasThought && hasPreview,
    customer_execution_ready: false
  };
}

function classify(text) {
  const lowered = text.toLowerCase();
  if (/pay|publish|deploy|contact customer|credential|secret|merge/.test(lowered)) return "HUMAN_GATE";
  if (/inspect|compare|validate|test|summarize|draft|document/.test(lowered)) return "LOCAL_CANDIDATE";
  return "UNPROVEN";
}

export function cannonPreview(state, goalId, now = new Date().toISOString(), options = {}) {
  if (!state.goals.some((item) => item.goal_id === goalId)) throw new Error("Unknown goal");
  const maxCandidates = Number(options.maxCandidates ?? 10);
  if (![10, 20, 50, 100].includes(maxCandidates)) throw new Error("maxCandidates must be 10, 20, 50, or 100");
  const candidates = [];
  const seen = new Set();
  let overflowCount = 0;
  for (const thought of state.thoughts.filter((item) => item.goal_id === goalId)) {
    for (const text of thought.content.split(/\n|[.!?]+/).map((item) => item.trim()).filter(Boolean)) {
      const candidateFingerprint = fingerprint({ goal_id: goalId, text: text.toLowerCase() });
      if (seen.has(candidateFingerprint)) continue;
      seen.add(candidateFingerprint);
      if (candidates.length >= maxCandidates) { overflowCount += 1; continue; }
      candidates.push({
        candidate_id: `candidate-${candidateFingerprint.slice(4)}`, text,
        classification: classify(text), fingerprint: candidateFingerprint,
        source_thought_id: thought.contribution_id, execution_status: "NOT_EXECUTED"
      });
    }
  }
  const preview = {
    preview_id: nextId("preview", state), goal_id: goalId, created_at: now,
    candidates, execution_count: 0, agent_count: 0, max_candidates: maxCandidates,
    overflow_count: overflowCount, truncated: overflowCount > 0, status: "PREVIEW_ONLY"
  };
  return { state: { ...state, previews: [...state.previews, preview] }, preview };
}

export function fireCannon(state, previewId) {
  const preview = state.previews.find((item) => item.preview_id === previewId);
  if (!preview) throw new Error("Unknown preview");
  return {
    state,
    result: {
      status: "UNPROVEN",
      executed: false,
      reason: "No provider-neutral execution adapter is integrated with this isolated surface. Fire fails closed.",
      next_action: "Integrate an accepted execution adapter before retrying Fire.",
      evidence: ["PREVIEW_ONLY", "MODEL_CALLS=0"]
    }
  };
}
