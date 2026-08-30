// ============================================================================
// 2026 Courier Studio // Living Agent HQ 60FPS Walking Simulation Engine
// Waypoint Navigation Graph, Real State Binding, MMORPG Nameplates & Courier Relay
// ============================================================================

import {
  resolveLivingRoomAgents,
  resolveLiveHQMetrics,
  resolvePermissionGuardTruth,
  resolveTeacherTruth,
  resolveAcademyEconomics,
  resolveActiveGateTruth,
  findWalkingPath,
  HQ_WAYPOINTS,
} from "./execution_truth.js";

const AVATAR_ICONS = {
  "agent-chief-commander": "👑",
  "smart-resource-router": "🧭",
  "agent-human-gate-monitor": "🛡️",
  "agent-thought-curator": "💡",
  "agent-update-steward": "📜",
  "agent-antigravity-bridge": "🚀",
  "agent-courier-relay": "⚡",
  "agent-academy-teacher": "🎓",
  "agent-academy-director": "🏛️",
  "agent-codex-bridge": "💻",
  "agent-snitch": "👁️",
  "agent-asset-validator": "🎨",
  "agent-video-synth": "🎬",
  "agent-channel-dispatcher": "📡",
  "agent-memory-mesh": "🧠",
  "agent-test-guardian": "🧪",
  "agent-loop-supervisor": "🔄",
};

export class LivingHQController {
  constructor() {
    this.pollInterval = 1000;
    this.isPolling = false;
    this.currentView = "overview";

    // Simulation State per Agent: id -> { currentX, currentY, targetX, targetY, pathQueue: [], isWalking: false, facing: 1 }
    this.agentSims = new Map();
    this.agentNodes = new Map();
    this.lastAgents = [];

    // Ambient walking patrol timer
    this.lastPatrolTime = Date.now();

    this.initElements();
    this.resetUnverifiedTelemetry();
    this.bindEvents();
    this.startClock();
    this.startAnimationLoop();
    this.startPolling();
  }

  initElements() {
    this.stage = document.getElementById("living-hq-stage");
    this.agentsLayer = document.getElementById("living-agents-layer");
    this.courierPacket = document.getElementById("courier-packet");
    this.courierPacketLabel = document.getElementById("courier-packet-label");

    // Header Controls
    this.serverStatus = document.getElementById("server-status");
    this.liveClock = document.getElementById("hq-live-clock");
    this.contextPillVer = document.getElementById("context-pill-ver");
    this.courierCommitTag = document.getElementById("courier-commit");
    this.camButtons = document.querySelectorAll(".cam-btn");
    this.btn16x9 = document.getElementById("btn-aspect-16-9");
    this.btn9x16 = document.getElementById("btn-aspect-9-16");
    this.btnRecord = document.getElementById("btn-recording-mode");
    this.btnToggleDetails = document.getElementById("btn-toggle-details");
    this.btnCloseDrawer = document.getElementById("btn-close-drawer");
    this.drawer = document.getElementById("control-panel-drawer");

    // TV Wall Overlays
    this.tvActiveCount = document.getElementById("tv-active-count");
    this.tvCapacityPct = document.getElementById("tv-capacity-pct");
    this.tvLiveWf = document.getElementById("tv-live-wf");
    this.tvLiveCorr = document.getElementById("tv-live-corr");
    this.tvLiveCtx = document.getElementById("tv-live-ctx");
    this.tvLiveSchool = document.getElementById("tv-live-school");
    this.tvLiveTreasury = document.getElementById("tv-live-treasury");

    // Drawer Elements
    this.humanIdeaInput = document.getElementById("human-idea-input");
    this.btnDispatchIdea = document.getElementById("btn-dispatch-idea");
    this.presetButtons = document.querySelectorAll(".preset-btn");
    this.gateBanner = document.getElementById("human-gate-banner");
    this.gateDesc = document.getElementById("gate-desc");
    this.btnGateApprove = document.getElementById("btn-gate-approve");
    this.btnGateReject = document.getElementById("btn-gate-reject");

    // Telemetry Elements
    this.snitchPermStatus = document.getElementById("snitch-perm-status");
    this.snitchPermCommand = document.getElementById("snitch-perm-command");
    this.snitchPermRuleRec = document.getElementById("snitch-perm-rule-rec");
    this.liveWfId = document.getElementById("live-wf-id");
    this.liveWfStatus = document.getElementById("live-wf-status");
    this.liveWfBar = document.getElementById("live-wf-bar");
    this.treasuryEur = document.getElementById("treasury-eur");
    this.treasuryUsd = document.getElementById("treasury-usd");
    this.treasuryVerified = document.getElementById("treasury-verified");
    this.treasuryGoal = document.getElementById("treasury-goal");
    this.panelCtxVer = document.getElementById("panel-ctx-ver");
    this.panelCtxPrev = document.getElementById("panel-ctx-prev");
    this.panelCtxHash = document.getElementById("panel-ctx-hash");
    this.panelRepoCourier = document.getElementById("panel-repo-courier");
    this.panelRepoMemory = document.getElementById("panel-repo-memory");
  }

  /** Replace static markup placeholders before the first local state refresh. */
  resetUnverifiedTelemetry() {
    if (this.courierCommitTag) this.courierCommitTag.textContent = "HEAD: UNAVAILABLE";
    if (this.contextPillVer) this.contextPillVer.textContent = "CONTEXT: UNKNOWN";
    if (this.tvLiveCorr) this.tvLiveCorr.textContent = "NONE";
    if (this.tvLiveCtx) this.tvLiveCtx.textContent = "UNKNOWN";
    if (this.tvLiveSchool) this.tvLiveSchool.textContent = "UNKNOWN";
    if (this.liveWfId) this.liveWfId.textContent = "NONE";
    if (this.treasuryEur) this.treasuryEur.textContent = "UNKNOWN";
    if (this.treasuryUsd) this.treasuryUsd.textContent = "UNAVAILABLE";
    if (this.treasuryVerified) this.treasuryVerified.textContent = "NOT_VERIFIED";
    if (this.treasuryGoal) this.treasuryGoal.textContent = "NOT_VERIFIED";
    if (this.panelCtxVer) this.panelCtxVer.textContent = "UNKNOWN";
    if (this.panelCtxPrev) this.panelCtxPrev.textContent = "UNKNOWN";
    if (this.panelCtxHash) this.panelCtxHash.textContent = "UNAVAILABLE";
    if (this.panelRepoCourier) this.panelRepoCourier.textContent = "UNAVAILABLE";
    if (this.panelRepoMemory) this.panelRepoMemory.textContent = "UNAVAILABLE";
  }

  bindEvents() {
    this.camButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        this.camButtons.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const view = btn.getAttribute("data-view");
        this.setCameraView(view);
      });
    });

    this.btn16x9?.addEventListener("click", () => {
      this.btn16x9.classList.add("active");
      this.btn9x16.classList.remove("active");
      document.body.classList.remove("mode-9-16");
    });

    this.btn9x16?.addEventListener("click", () => {
      this.btn9x16.classList.add("active");
      this.btn16x9.classList.remove("active");
      document.body.classList.add("mode-9-16");
    });

    this.btnRecord?.addEventListener("click", () => {
      document.body.classList.toggle("mode-recording");
      this.btnRecord.classList.toggle("active");
    });

    this.btnToggleDetails?.addEventListener("click", () => {
      this.drawer?.classList.toggle("hidden");
    });

    this.btnCloseDrawer?.addEventListener("click", () => {
      this.drawer?.classList.add("hidden");
    });

    this.presetButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const idea = btn.getAttribute("data-idea");
        if (this.humanIdeaInput && idea) {
          this.humanIdeaInput.value = idea;
        }
      });
    });

    this.btnDispatchIdea?.addEventListener("click", () => this.dispatchHumanIdea());
    this.btnGateApprove?.addEventListener("click", () => this.sendGateDecision(true));
    this.btnGateReject?.addEventListener("click", () => this.sendGateDecision(false));
  }

  setCameraView(view) {
    this.currentView = view;
    if (!this.stage) return;

    if (view === "active") {
      const active = this.lastAgents?.find(a => a.is_active && !a.is_bodyguard) || this.lastAgents?.find(a => a.is_active);
      if (active) {
        const panX = 50 - active.x;
        const panY = 50 - active.y;
        this.stage.className = "living-hq-stage";
        this.stage.style.transform = `scale(2.2) translate(${panX}%, ${panY}%)`;
        return;
      }
    }

    this.stage.style.transform = "";
    this.stage.className = "living-hq-stage view-" + view;
  }

  startClock() {
    const update = () => {
      const now = new Date();
      const str = now.toUTCString().split(" ")[4];
      if (this.liveClock) this.liveClock.textContent = `HQ TIME: ${str} UTC`;
    };
    update();
    setInterval(update, 1000);
  }

  // ------------------------------------------------------------------------
  // 60 FPS RequestAnimationFrame Simulation Loop
  // ------------------------------------------------------------------------
  startAnimationLoop() {
    let lastTime = performance.now();

    const loop = (time) => {
      const delta = Math.min((time - lastTime) / 1000, 0.1); // seconds capped at 100ms
      lastTime = time;

      this.updateAgentPositions(delta);
      requestAnimationFrame(loop);
    };

    requestAnimationFrame(loop);
  }

  updateAgentPositions(delta) {
    const WALK_SPEED = 18.0; // % per second

    for (const [id, sim] of this.agentSims.entries()) {
      const node = this.agentNodes.get(id);
      if (!node) continue;

      if (sim.pathQueue && sim.pathQueue.length > 0) {
        const nextWp = sim.pathQueue[0];
        const dx = nextWp.x - sim.currentX;
        const dy = nextWp.y - sim.currentY;
        const dist = Math.hypot(dx, dy);

        if (dist <= 0.6) {
          // Reached waypoint
          sim.currentX = nextWp.x;
          sim.currentY = nextWp.y;
          sim.pathQueue.shift();
        } else {
          // Step towards waypoint
          const moveDist = WALK_SPEED * delta;
          const ratio = Math.min(moveDist / dist, 1.0);
          sim.currentX += dx * ratio;
          sim.currentY += dy * ratio;

          // Update facing direction
          if (Math.abs(dx) > 0.1) {
            sim.facing = dx > 0 ? 1 : -1;
          }
        }

        sim.isWalking = true;
      } else {
        sim.isWalking = false;
      }

      // Apply coordinates and classes to DOM node
      node.style.left = `${sim.currentX.toFixed(2)}%`;
      node.style.top = `${sim.currentY.toFixed(2)}%`;

      node.classList.toggle("is-walking", sim.isWalking);
      node.classList.toggle("facing-left", sim.facing === -1);
      node.classList.toggle("facing-right", sim.facing === 1);
    }
  }

  // ------------------------------------------------------------------------
  // Polling Machine State & Dispatching Waypoint Paths
  // ------------------------------------------------------------------------
  async startPolling() {
    if (this.isPolling) return;
    this.isPolling = true;

    const poll = async () => {
      try {
        const response = await fetch("/api/state", { cache: "no-store" });
        if (response.ok) {
          const stateData = await response.json();
          this.updateLivingHQ(stateData);
          if (this.serverStatus) this.serverStatus.textContent = "LIVE BUS CONNECTED";
        }
      } catch (err) {
        if (this.serverStatus) this.serverStatus.textContent = "RECONNECTING LOCAL BUS...";
      } finally {
        setTimeout(poll, this.pollInterval);
      }
    };

    poll();
  }

  updateLivingHQ(stateData) {
    // 1. Resolve and Render Dynamic Living Agents
    const agents = resolveLivingRoomAgents(stateData);
    this.lastAgents = agents;
    this.syncAgentSimulations(agents);
    this.renderLivingAgents(agents);

    // 2. Resolve Master TV Wall Data
    const metrics = resolveLiveHQMetrics(stateData);
    if (this.tvActiveCount) this.tvActiveCount.textContent = metrics.active_agents;
    if (this.tvCapacityPct) this.tvCapacityPct.textContent = `${Math.round((metrics.active_agents / 40) * 100 * 10) / 10}% Capacity`;

    const wf = metrics.current_workflow || "NONE";
    const corr = metrics.correlation_id || "NONE";
    const ctxVer = metrics.context_version ? `v${metrics.context_version}` : "UNKNOWN";

    if (this.tvLiveWf) this.tvLiveWf.textContent = wf;
    if (this.tvLiveCorr) this.tvLiveCorr.textContent = corr;
    if (this.tvLiveCtx) this.tvLiveCtx.textContent = ctxVer;
    if (this.contextPillVer) this.contextPillVer.textContent = `CONTEXT: ${ctxVer}`;

    const teacher = resolveTeacherTruth(stateData);
    const nextSchool = teacher.next_school_time || "UNKNOWN";
    if (this.tvLiveSchool) this.tvLiveSchool.textContent = nextSchool;

    // Invariant: Flow indicator
    const isFlowActive = Boolean(wf && wf !== "IDLE_MONITORING");
    this.stage?.classList.toggle("is-flow-active", isFlowActive);

    // 3. Message / Courier Transport Visualization
    this.updateCourierTransport(agents);

    // 4. Update Telemetry Panels & Human Gate
    this.updateTelemetryAndGate(stateData, metrics);
  }

  syncAgentSimulations(agents) {
    for (const agent of agents) {
      let sim = this.agentSims.get(agent.id);

      if (!sim) {
        sim = {
          id: agent.id,
          currentX: agent.x,
          currentY: agent.y,
          targetX: agent.x,
          targetY: agent.y,
          homeX: agent.homeX || agent.x,
          homeY: agent.homeY || agent.y,
          pathQueue: [],
          isWalking: false,
          facing: 1,
        };
        this.agentSims.set(agent.id, sim);
      }

      // Check if backend target position changed significantly (> 2.0%)
      const distToTarget = Math.hypot(agent.x - sim.targetX, agent.y - sim.targetY);
      if (distToTarget > 2.0) {
        sim.targetX = agent.x;
        sim.targetY = agent.y;
        // Compute path through walkable navigation graph
        sim.pathQueue = findWalkingPath(sim.currentX, sim.currentY, agent.x, agent.y);
      }
    }
  }

  renderLivingAgents(agents) {
    if (!this.agentsLayer) return;

    const seenIds = new Set();

    agents.forEach(agent => {
      seenIds.add(agent.id);
      let node = this.agentNodes.get(agent.id);

      if (!node) {
        node = document.createElement("div");
        node.className = "living-agent-node";
        node.id = `node-${agent.id}`;
        
        const nameplate = document.createElement("div");
        nameplate.className = "agent-nameplate";
        const title = document.createElement("span");
        title.className = "nameplate-title";
        title.textContent = agent.name || "UNKNOWN";
        const subtitle = document.createElement("span");
        subtitle.className = "nameplate-subtitle";
        subtitle.textContent = agent.title || "UNKNOWN";
        nameplate.append(title, subtitle);

        const avatar = document.createElement("div");
        avatar.className = "agent-avatar-body";
        const iconSymbol = agent.is_bodyguard ? "🛡️" : (AVATAR_ICONS[agent.id] || "🤖");
        const avatarIcon = document.createElement("span");
        avatarIcon.className = "avatar-icon";
        avatarIcon.textContent = iconSymbol;
        const avatarRing = document.createElement("span");
        avatarRing.className = "avatar-status-ring";
        avatar.append(avatarIcon, avatarRing);

        const speech = document.createElement("div");
        speech.className = "agent-speech-bubble";
        speech.style.display = "none";

        node.appendChild(nameplate);
        node.appendChild(avatar);
        node.appendChild(speech);

        this.agentsLayer.appendChild(node);
        this.agentNodes.set(agent.id, node);
      }

      // State Classes
      node.className = "living-agent-node";
      if (agent.is_active) node.classList.add("state-working");
      if (agent.is_blocked) node.classList.add("state-blocked");
      if (agent.is_bodyguard) node.classList.add("is-bodyguard");

      // Update Subtitle & Speech
      const subtitle = node.querySelector(".nameplate-subtitle");
      if (subtitle) subtitle.textContent = agent.title || "UNKNOWN";

      const speechEl = node.querySelector(".agent-speech-bubble");
      if (speechEl) {
        if (agent.speech && agent.speech.trim()) {
          speechEl.textContent = agent.speech;
          speechEl.style.display = "block";
        } else {
          speechEl.style.display = "none";
        }
      }
    });

    // Remove any stale agents
    for (const [id, node] of this.agentNodes.entries()) {
      if (!seenIds.has(id)) {
        node.remove();
        this.agentNodes.delete(id);
        this.agentSims.delete(id);
      }
    }
  }

  updateCourierTransport(agents) {
    if (!this.courierPacket) return;

    const courier = agents.find(a => a.id === "agent-courier-relay");
    const activeWorker = agents.find(a => a.is_active && a.id !== "agent-chief-commander" && a.id !== "smart-resource-router");

    if (activeWorker && courier) {
      this.courierPacket.style.display = "flex";
      const courierSim = this.agentSims.get("agent-courier-relay");
      const workerSim = this.agentSims.get(activeWorker.id);

      const px = ((workerSim ? workerSim.currentX : activeWorker.x) + (courierSim ? courierSim.currentX : courier.x)) / 2;
      const py = ((workerSim ? workerSim.currentY : activeWorker.y) + (courierSim ? courierSim.currentY : courier.y)) / 2;
      
      this.courierPacket.style.left = `${px}%`;
      this.courierPacket.style.top = `${py}%`;

      if (activeWorker.progress >= 0.8) {
        this.courierPacket.className = "courier-transport-packet packet-result";
        if (this.courierPacketLabel) this.courierPacketLabel.textContent = "📨 RESULT";
      } else {
        this.courierPacket.className = "courier-transport-packet packet-task";
        if (this.courierPacketLabel) this.courierPacketLabel.textContent = "📦 TASK";
      }
    } else {
      this.courierPacket.style.display = "none";
    }
  }

  updateTelemetryAndGate(stateData, metrics) {
    // SNITCH Permission Guard
    const pg = resolvePermissionGuardTruth(stateData);
    if (this.snitchPermStatus) {
      this.snitchPermStatus.textContent = pg.status || "UNKNOWN";
      this.snitchPermStatus.className = pg.status === "DANGEROUS REQUEST" ? "text-danger" : "badge-perm-healthy";
    }
    if (this.snitchPermCommand) this.snitchPermCommand.textContent = pg.last_command || "NONE";
    if (this.snitchPermRuleRec) this.snitchPermRuleRec.textContent = pg.rule_recommendation || "UNKNOWN";

    // Workflow
    if (this.liveWfId) this.liveWfId.textContent = metrics.current_workflow || "NONE";
    if (this.liveWfStatus) this.liveWfStatus.textContent = metrics.active_agents > 0 ? "IN_PROGRESS" : "IDLE";
    if (this.liveWfBar) this.liveWfBar.style.width = `${Math.min(100, metrics.active_agents * 25)}%`;

    // Treasury
    const economics = resolveAcademyEconomics(stateData);
    if (this.treasuryEur) this.treasuryEur.textContent = economics.measured_cost_saved_eur === null
      ? "UNKNOWN"
      : `${economics.measured_cost_saved_eur} EUR`;
    if (this.treasuryUsd) this.treasuryUsd.textContent = "UNAVAILABLE";
    if (this.treasuryVerified) this.treasuryVerified.textContent = economics.revenue_evidence || "NOT_VERIFIED";
    if (this.treasuryGoal) this.treasuryGoal.textContent = economics.truth_label || "NOT_VERIFIED";

    // Repositories & Context
    if (this.panelCtxVer) this.panelCtxVer.textContent = metrics.context_version ? `v${metrics.context_version}` : "UNKNOWN";
    const previousContextVersion = stateData?.context_snapshot?.previous_snapshot_version;
    if (this.panelCtxPrev) this.panelCtxPrev.textContent = Number.isFinite(previousContextVersion)
      ? `v${previousContextVersion}`
      : "UNKNOWN";
    if (this.panelCtxHash) this.panelCtxHash.textContent = metrics.snapshot_hash ? `${metrics.snapshot_hash.slice(0, 16)}...` : "UNAVAILABLE";
    if (this.panelRepoCourier) this.panelRepoCourier.textContent = metrics.repo_courier_head ? metrics.repo_courier_head.slice(0, 8) : "UNAVAILABLE";
    if (this.panelRepoMemory) this.panelRepoMemory.textContent = metrics.repo_memory_head ? metrics.repo_memory_head.slice(0, 8) : "UNAVAILABLE";

    // Human Gate Modal
    const gate = resolveActiveGateTruth(stateData);
    if (gate && gate.is_blocked && !gate.decision_made) {
      if (this.gateBanner) this.gateBanner.classList.remove("hidden");
      if (this.gateDesc) this.gateDesc.textContent = gate.description || "A task requires human authorization.";
      this.currentGate = gate;
    } else {
      if (this.gateBanner) this.gateBanner.classList.add("hidden");
      this.currentGate = null;
    }
  }

  async dispatchHumanIdea() {
    if (!this.humanIdeaInput) return;
    const idea = this.humanIdeaInput.value.trim();
    if (!idea) return;

    try {
      this.btnDispatchIdea.disabled = true;
      this.btnDispatchIdea.textContent = "DISPATCHING...";
      const res = await fetch("/api/submit-idea", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idea, mode: "AUTONOMOUS" }),
      });
      if (res.ok) {
        this.humanIdeaInput.value = "";
        this.drawer?.classList.add("hidden");
      }
    } catch (e) {
      console.error("Dispatch idea failed:", e);
    } finally {
      this.btnDispatchIdea.disabled = false;
      this.btnDispatchIdea.innerHTML = `<span class="dispatch-icon">⚡</span> DISPATCH DIRECTIVE`;
    }
  }

  async sendGateDecision(approve) {
    if (!this.currentGate) return;
    try {
      await fetch("/api/human-decision", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          gate_id: this.currentGate.id,
          decision: approve ? "APPROVED" : "REJECTED",
        }),
      });
      if (this.gateBanner) this.gateBanner.classList.add("hidden");
    } catch (e) {
      console.error("Gate decision failed:", e);
    }
  }
}

// Bootstrap on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  window.livingHQ = new LivingHQController();
});
