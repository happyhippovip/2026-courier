/**
 * AI Agent Command Center Engine (MVP 092)
 * Coordinates 17 Canonical Roles, Workflow Visualizer, Demo Mission, and Event Stream.
 */

// 1. ALL 17 CANONICAL AGENT ROLES (from Project Memory / TECHNICAL_CONTEXT.md)
const AGENT_ROSTER = [
  {
    id: "chief-commander",
    name: "Chief Commander",
    role: "Strategic Orchestrator",
    category: "orchestration",
    avatar: "👑",
    status: "ACTIVE",
    statusClass: "status-active",
    provenance: "REAL PIPELINE",
    capabilities: [
      "Directs high-level project goals & policy boundaries",
      "Emits structured Chief COMMANDs via Courier v2.0",
      "Autonomous 088 Decision evaluation & final gatekeeper"
    ]
  },
  {
    id: "courier",
    name: "Courier Bridge",
    role: "Event Transport & Protocol",
    category: "orchestration",
    avatar: "📦",
    status: "ACTIVE",
    statusClass: "status-active",
    provenance: "REAL PIPELINE",
    capabilities: [
      "GitHub-based event relay across repositories",
      "Deduplication & SHA-256 payload verification",
      "Unified run_chief_relay_cycle executor (089/090)"
    ]
  },
  {
    id: "dispatcher",
    name: "Task Dispatcher",
    role: "Contract Hardening & Packaging",
    category: "orchestration",
    avatar: "🎯",
    status: "ACTIVE",
    statusClass: "status-active",
    provenance: "REAL PIPELINE",
    capabilities: [
      "Translates Chief COMMAND into Worker Job Contract",
      "Enforces ZERO_COST_ONLY & STOP_ON_HUMAN_GATE_ONLY",
      "Strict schema validation (antigravity_worker_job)"
    ]
  },
  {
    id: "antigravity-worker",
    name: "Antigravity Worker",
    role: "Autonomous Code & System Builder",
    category: "orchestration",
    avatar: "🤖",
    status: "ACTIVE",
    statusClass: "status-active",
    provenance: "REAL PIPELINE",
    capabilities: [
      "Interactive pair programming & task execution",
      "Emits structured Antigravity RESULT envelopes",
      "Sandboxed local file access & verification tests"
    ]
  },
  {
    id: "memory-steward",
    name: "Memory Steward (Vergesslichkeits-Bot)",
    role: "Knowledge Base Guard",
    category: "governance",
    avatar: "💾",
    status: "ACTIVE",
    statusClass: "status-active",
    provenance: "REAL PIPELINE",
    capabilities: [
      "Manages 2026-project-memory canonical records",
      "086 Proposal Gate & 087 Controlled Write Handler",
      "Guarantees truth status & deletes denied by default"
    ]
  },
  {
    id: "supervisor",
    name: "Supervisor",
    role: "Progress & Telemetry Monitor",
    category: "orchestration",
    avatar: "👁️",
    status: "AVAILABLE",
    statusClass: "status-available",
    provenance: "PLANNED ROLE",
    capabilities: [
      "Tracks multi-step task trajectories and SLA timeouts",
      "Detects worker stalls and flags stuck loops",
      "Generates consolidated status summaries"
    ]
  },
  {
    id: "switchboard",
    name: "Switchboard Router",
    role: "Message Gateway",
    category: "orchestration",
    avatar: "🎛️",
    status: "AVAILABLE",
    statusClass: "status-available",
    provenance: "PLANNED ROLE",
    capabilities: [
      "Multiplexes inter-agent message queues",
      "Routes incoming webhook payloads to target roles",
      "Maintains correlation_id thread continuity"
    ]
  },
  {
    id: "sysadmin",
    name: "System Administrator",
    role: "Tooling & Environment Guard",
    category: "governance",
    avatar: "🔧",
    status: "AVAILABLE",
    statusClass: "status-available",
    provenance: "PLANNED ROLE",
    capabilities: [
      "Audits local environment & Python virtualenv integrity",
      "Verifies git authentication & submodule sync",
      "Ensures dependency compatibility"
    ]
  },
  {
    id: "cost-officer",
    name: "Cost & Energy Controller",
    role: "Budget & Quota Steward",
    category: "governance",
    avatar: "⚡",
    status: "ACTIVE",
    statusClass: "status-active",
    provenance: "REAL PIPELINE",
    capabilities: [
      "Enforces 0.00 EUR strict zero-cost policy",
      "Blocks paid model tier upgrades and external APIs",
      "Monitors token consumption across runs"
    ]
  },
  {
    id: "review-release",
    name: "Review & Release Auditor",
    role: "Human Gate Guardian",
    category: "governance",
    avatar: "🛡️",
    status: "ACTIVE",
    statusClass: "status-active",
    provenance: "REAL PIPELINE",
    capabilities: [
      "Enforces STOP_ON_HUMAN_GATE_ONLY rules",
      "Blocks unauthorized uploads, payments & OAuth actions",
      "Conducts pre-publish content & quality audits"
    ]
  },
  {
    id: "creative-director",
    name: "Creative Director",
    role: "Narrative & Hook Engineer",
    category: "production",
    avatar: "🎨",
    status: "AVAILABLE",
    statusClass: "status-available",
    provenance: "DEMO CONCEPT",
    capabilities: [
      "Designs 9:16 vertical short-form story concepts",
      "Engineers viral 3-second hook structures",
      "Specifies FruitKI character animation cues"
    ]
  },
  {
    id: "production-engine",
    name: "3D Production Engine (Godot)",
    role: "Short-Form Video Renderer",
    category: "production",
    avatar: "🎬",
    status: "AVAILABLE",
    statusClass: "status-available",
    provenance: "LOCAL ASSET VERIFIED",
    capabilities: [
      "Godot 360x640 vertical 3D rendering pipeline",
      "Kiwi & Strawberry character animation scripts",
      "Generates H.264 / AAC video files locally"
    ]
  },
  {
    id: "youtube-specialist",
    name: "YouTube Specialist",
    role: "Platform Publisher & SEO",
    category: "production",
    avatar: "▶️",
    status: "HUMAN GATE",
    statusClass: "status-gate",
    provenance: "HUMAN GATE PROTECTED",
    capabilities: [
      "Prepares YouTube Shorts metadata, titles and tags",
      "Desktop OAuth pilot scripts exist locally",
      "Requires explicit human approval before any upload"
    ]
  },
  {
    id: "tiktok-specialist",
    name: "TikTok Specialist",
    role: "Vertical Format & Trends",
    category: "production",
    avatar: "🎵",
    status: "HUMAN GATE",
    statusClass: "status-gate",
    provenance: "HUMAN GATE PROTECTED",
    capabilities: [
      "PKCE loopback and draft inbox upload scripts",
      "Optimizes 9:16 aspect ratio & hashtag grouping",
      "Production Review gate: requires human approval"
    ]
  },
  {
    id: "research-analyst",
    name: "Research & Trend Analyst",
    role: "Audience & Market Intelligence",
    category: "production",
    avatar: "📊",
    status: "AVAILABLE",
    statusClass: "status-available",
    provenance: "DEMO CONCEPT",
    capabilities: [
      "Analyzes vertical video retention curves",
      "Monitors trending sound formats & formats",
      "Provides data-backed premise recommendations"
    ]
  },
  {
    id: "survival-guard",
    name: "Survival & Capital Guard",
    role: "Capital Protection Guardian",
    category: "governance",
    avatar: "🏰",
    status: "ACTIVE",
    statusClass: "status-active",
    provenance: "REAL POLICY",
    capabilities: [
      "Enforces D-002: Crypto and speculation strictly blocked",
      "Enforces D-003: Protected reserves untouched",
      "Enforces D-004: Zero unauthorized financial risk"
    ]
  },
  {
    id: "revenue-steward",
    name: "Revenue & Commercial Steward",
    role: "Service Pricing & Monetization",
    category: "governance",
    avatar: "💰",
    status: "AVAILABLE",
    statusClass: "status-available",
    provenance: "DEMO CONCEPT",
    capabilities: [
      "Verifies real received money vs vanity metrics",
      "Scopes 9:16 short production service packages",
      "Ensures sustainable, profitable project growth"
    ]
  }
];

// 2. DEMO MISSION 6-STAGE DEFINITIONS
const MISSION_STAGES = [
  {
    step: 1,
    title: "Stage 1: Idea Generation & Character Hook",
    badge: "UI SIMULATED",
    desc: "Creative Director and Research Analyst selected high-retention character hook based on canonical FruitKI local production baseline.",
    agent: "Creative Director & Research Analyst",
    asset: "strawberry-school-short-002-concept.json",
    format: "9:16 Vertical Video (360×640 H.264 / AAC)",
    gate: "SAFE (Local zero-cost ideation)",
    character: "🍓",
    overlayText: "\"Strawberry School Mystery\"",
    badgeText: "STAGE 1: IDEA SELECTED",
    flowStep: 1,
    logMsg: "Chief emitted directive for Strawberry School short-form production concept."
  },
  {
    step: 2,
    title: "Stage 2: Script & Timing Breakdown",
    badge: "UI SIMULATED",
    desc: "Generated precise 7.125-second vertical script with 3-second visual hook, dialogue cues and comedic payoff.",
    agent: "Creative Director",
    asset: "strawberry-school-002.script.md",
    format: "7.125s duration · 3 scene beats",
    gate: "SAFE (Local narrative formulation)",
    character: "📝",
    overlayText: "\"Beat 1: The Disappearing Eraser\"",
    badgeText: "STAGE 2: SCRIPT READY",
    flowStep: 2,
    logMsg: "Script validated: 7.125s runtime matches verified local Strawberry audio track."
  },
  {
    step: 3,
    title: "Stage 3: 3D Scene & Asset Assembly",
    badge: "UI SIMULATED",
    desc: "Godot short studio loaded 3D strawberry mesh, classroom environment, camera framing (360×640 vertical) and lighting rigs.",
    agent: "3D Production Engine (Godot)",
    asset: "05-3D-Shorts-Produktion/godot-short-studio",
    format: "Godot 3D Scene · 360×640 viewport",
    gate: "SAFE (Local Godot production environment)",
    character: "🏫",
    overlayText: "\"Godot 3D Classroom Viewport\"",
    badgeText: "STAGE 3: 3D ASSETS STAGED",
    flowStep: 3,
    logMsg: "Dispatcher verified worker job contract for Godot asset pipeline."
  },
  {
    step: 4,
    title: "Stage 4: Video Rendering & Audio Multiplexing",
    badge: "UI SIMULATED / LOCAL ASSET",
    desc: "Rendered final H.264/AAC vertical video asset. Validated matching local baseline: strawberry-school-short-002-final.mp4 (7.125 s).",
    agent: "3D Production Engine & Antigravity Worker",
    asset: "strawberry-school-short-002-final.mp4 (7.125s)",
    format: "360×640 H.264 / AAC · 1.8 MB",
    gate: "SAFE (Zero-cost local render completed)",
    character: "🎬",
    overlayText: "\"Render Complete: 7.125s MP4\"",
    badgeText: "STAGE 4: VIDEO RENDERED",
    flowStep: 4,
    logMsg: "Worker published RESULT: strawberry-school-short-002-final.mp4 verified locally."
  },
  {
    step: 5,
    title: "Stage 5: Quality Audit & 088 Policy Review",
    badge: "REAL POLICY ENGINE",
    desc: "Autonomous Chief Policy (088) evaluated proposal. Pure technical facts approved with AUTO_APPROVE. All publication gates locked.",
    agent: "Review & Release Auditor (088 Policy)",
    asset: "events/chief-decisions/TASK-092-decision.json",
    format: "087 Approval Record Generated",
    gate: "HUMAN GATE ACTIVE (Public upload held)",
    character: "🛡️",
    overlayText: "\"QC Passed · Human Gate Locked\"",
    badgeText: "STAGE 5: POLICY AUDIT PASS",
    flowStep: 5,
    logMsg: "088 Policy: AUTO_APPROVE for technical asset; Public social upload locked for human approval."
  },
  {
    step: 6,
    title: "Stage 6: Ready for Human Release Approval",
    badge: "HUMAN GATE BOUNDARY",
    desc: "Asset package ready for distribution. Public YouTube and TikTok upload require explicit human approval in accordance with D-004 & D-008.",
    agent: "Chief Commander (Human Review Gate)",
    asset: "YouTube/TikTok Distribution Package",
    format: "Pre-upload package staged",
    gate: "⛔ LOCKED: Explicit human consent required",
    character: "🔒",
    overlayText: "\"Awaiting Human Upload Approval\"",
    badgeText: "STAGE 6: HUMAN GATE LOCKED",
    flowStep: 6,
    logMsg: "Mission safely paused at Human Gate. No automatic public upload executed."
  }
];

// STATE MANAGEMENT
let currentMissionStep = 1;
let autoMissionInterval = null;
let currentFilter = "all";

// INITIALIZATION
document.addEventListener("DOMContentLoaded", () => {
  renderAgentRoster();
  setupFilterButtons();
  setupMissionControls();
  setupInitialLogs();
  updateMissionUI();
});

// RENDER AGENT ROSTER
function renderAgentRoster() {
  const container = document.getElementById("agent-cards-container");
  container.innerHTML = "";

  const filteredAgents = AGENT_ROSTER.filter(agent => {
    if (currentFilter === "all") return true;
    return agent.category === currentFilter;
  });

  filteredAgents.forEach(agent => {
    const card = document.createElement("div");
    card.className = "agent-card";
    card.id = `card-${agent.id}`;

    const capsList = agent.capabilities.map(c => `<li>${c}</li>`).join("");

    card.innerHTML = `
      <div class="card-top">
        <div class="agent-avatar">${agent.avatar}</div>
        <div class="agent-header-info">
          <div class="agent-name">${agent.name}</div>
          <div class="agent-role-title">${agent.role}</div>
        </div>
      </div>

      <div class="agent-status-row">
        <span class="agent-status-tag ${agent.statusClass}">${agent.status}</span>
        <span class="provenance-tag">${agent.provenance}</span>
      </div>

      <ul class="agent-caps">
        ${capsList}
      </ul>

      <button class="card-action-btn ${agent.status === 'ACTIVE' ? 'active-state' : ''}" 
              onclick="toggleAgentActivation('${agent.id}')">
        ${agent.status === 'ACTIVE' ? '✓ ACTIVE' : '⚡ ACTIVATE'}
      </button>
    `;

    container.appendChild(card);
  });

  // Update HUD Active Count
  const activeCount = AGENT_ROSTER.filter(a => a.status === "ACTIVE").length;
  document.getElementById("active-agents-count").textContent = activeCount;
}

// TOGGLE AGENT ACTIVATION (UI Simulation)
window.toggleAgentActivation = function(agentId) {
  const agent = AGENT_ROSTER.find(a => a.id === agentId);
  if (!agent) return;

  if (agent.status === "ACTIVE") {
    agent.status = "AVAILABLE";
    agent.statusClass = "status-available";
    addLog("INFO", `Agent [${agent.name}] set to standby / AVAILABLE.`);
  } else {
    agent.status = "ACTIVE";
    agent.statusClass = "status-active";
    addLog("SUCCESS", `Agent [${agent.name}] activated in command roster (UI Mode).`);
  }

  renderAgentRoster();
};

// FILTER TABS SETUP
function setupFilterButtons() {
  const buttons = document.querySelectorAll("#roster-filters .filter-btn");
  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      buttons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = btn.dataset.filter;
      renderAgentRoster();
    });
  });
}

// MISSION CONTROLS SETUP
function setupMissionControls() {
  document.getElementById("btn-step-mission").addEventListener("click", () => {
    if (currentMissionStep < MISSION_STAGES.length) {
      currentMissionStep++;
    } else {
      currentMissionStep = 1;
    }
    updateMissionUI();
  });

  document.getElementById("btn-reset-mission").addEventListener("click", () => {
    stopAutoMission();
    currentMissionStep = 1;
    updateMissionUI();
    addLog("INFO", "Demo mission reset to Stage 1.");
  });

  document.getElementById("btn-auto-mission").addEventListener("click", () => {
    if (autoMissionInterval) {
      stopAutoMission();
    } else {
      startAutoMission();
    }
  });

  // Direct Click on Step Icons
  document.querySelectorAll(".mission-step").forEach(stepEl => {
    stepEl.addEventListener("click", () => {
      stopAutoMission();
      currentMissionStep = parseInt(stepEl.dataset.step, 10);
      updateMissionUI();
    });
  });

  // Clear Logs
  document.getElementById("btn-clear-logs").addEventListener("click", () => {
    document.getElementById("log-stream-container").innerHTML = "";
    addLog("INFO", "Log stream cleared.");
  });
}

function startAutoMission() {
  const btn = document.getElementById("btn-auto-mission");
  btn.textContent = "⏸ Pause Auto Demo";
  btn.classList.add("btn-secondary");
  btn.classList.remove("btn-accent");

  addLog("POLICY", "▶ Auto-Demo sequence initiated across 6 pipeline stages.");

  autoMissionInterval = setInterval(() => {
    if (currentMissionStep < MISSION_STAGES.length) {
      currentMissionStep++;
      updateMissionUI();
    } else {
      stopAutoMission();
      addLog("GATE", "Demo mission reached final stage: safely stopped at Human Gate.");
    }
  }, 2200);
}

function stopAutoMission() {
  if (autoMissionInterval) {
    clearInterval(autoMissionInterval);
    autoMissionInterval = null;
  }
  const btn = document.getElementById("btn-auto-mission");
  btn.textContent = "▶ Run Auto Demo";
  btn.classList.remove("btn-secondary");
  btn.classList.add("btn-accent");
}

// UPDATE MISSION UI
function updateMissionUI() {
  const stageData = MISSION_STAGES[currentMissionStep - 1];

  // Update Stepper Visuals
  for (let i = 1; i <= 6; i++) {
    const stepEl = document.getElementById(`mstep-${i}`);
    const lineEl = document.getElementById(`mline-${i}`);

    stepEl.classList.remove("current", "completed");
    if (lineEl) lineEl.classList.remove("completed");

    if (i < currentMissionStep) {
      stepEl.classList.add("completed");
      if (lineEl) lineEl.classList.add("completed");
    } else if (i === currentMissionStep) {
      stepEl.classList.add("current");
    }
  }

  // Update Details
  document.getElementById("stage-title").textContent = stageData.title;
  document.getElementById("stage-desc").textContent = stageData.desc;
  document.getElementById("stage-agent").textContent = stageData.agent;
  document.getElementById("stage-asset").textContent = stageData.asset;
  document.getElementById("stage-gate").textContent = stageData.gate;

  // Update Preview Mockup
  document.getElementById("video-stage-badge").textContent = stageData.badgeText;
  document.getElementById("sim-text").textContent = stageData.overlayText;
  document.querySelector(".sim-character").textContent = stageData.character;

  // Update Workflow Diagram Node Highlight
  highlightWorkflowNode(stageData.flowStep);

  // Emit Log
  addLog("INFO", `[Mission Stage ${stageData.step}] ${stageData.logMsg}`);
}

// WORKFLOW NODE HIGHLIGHT
function highlightWorkflowNode(stepNumber) {
  const nodes = [
    "node-chief",
    "node-courier-in",
    "node-dispatcher",
    "node-worker",
    "node-review",
    "node-memory"
  ];

  nodes.forEach((nId, idx) => {
    const el = document.getElementById(nId);
    if (el) {
      if (idx + 1 === stepNumber) {
        el.classList.add("active-node");
      } else {
        el.classList.remove("active-node");
      }
    }
  });
}

// LOG STREAM SYSTEM
function addLog(level, message) {
  const logContainer = document.getElementById("log-stream-container");
  const timeStr = new Date().toISOString().substring(11, 19);

  const entry = document.createElement("div");
  entry.className = "log-entry";
  entry.innerHTML = `
    <span class="log-time">[${timeStr}Z]</span>
    <span class="log-level ${level}">${level.padEnd(7)}</span>
    <span class="log-msg">${message}</span>
  `;

  logContainer.prepend(entry);

  // Keep max 50 entries
  while (logContainer.children.length > 50) {
    logContainer.removeChild(logContainer.lastChild);
  }
}

// INITIAL SEED LOGS (From real Courier baseline)
function setupInitialLogs() {
  addLog("SUCCESS", "AI Agent Command Center MVP 092 initialized.");
  addLog("POLICY", "Deterministic 088 Autonomous Policy Engine: ACTIVE.");
  addLog("INFO", "Canonical Project Memory loaded from happyhippovip/2026-project-memory (HEAD: 89cece2).");
  addLog("GATE", "Human Gates status: Public Upload, OAuth, and Payments LOCKED by default.");
  addLog("SUCCESS", "Courier Relay Protocol v2.0 verified with zero human-gate stalls.");
}
