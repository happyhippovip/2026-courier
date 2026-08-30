// ============================================================================
// 2026 Courier Studio // Living Agent HQ Operations Controller
// High-Fidelity Character Layer, MMORPG Nameplates, Real State & Courier Relay
// ============================================================================

import {
  resolveLivingRoomAgents,
  resolveLiveHQMetrics,
  resolvePermissionGuardTruth,
  resolveTeacherTruth,
  resolveTreasuryTruth,
  resolveActiveGateTruth,
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
    this.pollInterval = 500;
    this.isPolling = false;
    this.agentNodes = new Map();
    this.currentView = "overview";

    this.initElements();
    this.bindEvents();
    this.startClock();
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
    this.renderLivingAgents(agents);

    // 2. Resolve Master TV Wall Data
    const metrics = resolveLiveHQMetrics(stateData);
    if (this.tvActiveCount) this.tvActiveCount.textContent = metrics.active_agents;
    if (this.tvCapacityPct) this.tvCapacityPct.textContent = `${Math.round((metrics.active_agents / 40) * 100 * 10) / 10}% Capacity`;

    const wf = metrics.current_workflow || "IDLE_MONITORING";
    const corr = metrics.correlation_id || "corr-demo-c94b85b8";
    const ctxVer = metrics.context_version ? `v${metrics.context_version}` : "v64";

    if (this.tvLiveWf) this.tvLiveWf.textContent = wf;
    if (this.tvLiveCorr) this.tvLiveCorr.textContent = corr;
    if (this.tvLiveCtx) this.tvLiveCtx.textContent = ctxVer;
    if (this.contextPillVer) this.contextPillVer.textContent = `CONTEXT: ${ctxVer}`;

    const teacher = resolveTeacherTruth(stateData);
    const nextSchool = teacher.next_school_time || "06:00 UTC";
    if (this.tvLiveSchool) this.tvLiveSchool.textContent = nextSchool;

    // Invariant: Flow indicator
    const isFlowActive = Boolean(wf && wf !== "IDLE_MONITORING");
    this.stage?.classList.toggle("is-flow-active", isFlowActive);

    // 3. Message / Courier Transport Visualization
    this.updateCourierTransport(agents);

    // 4. Update Telemetry Panels & Human Gate
    this.updateTelemetryAndGate(stateData, metrics);
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
        nameplate.innerHTML = `<span class="nameplate-title">${agent.name}</span><span class="nameplate-subtitle">${agent.title}</span>`;

        const avatar = document.createElement("div");
        avatar.className = "agent-avatar-body";
        const iconSymbol = agent.is_bodyguard ? "🛡️" : (AVATAR_ICONS[agent.id] || "🤖");
        avatar.innerHTML = `<span class="avatar-icon">${iconSymbol}</span><span class="avatar-status-ring"></span>`;

        const speech = document.createElement("div");
        speech.className = "agent-speech-bubble";
        speech.style.display = "none";

        node.appendChild(nameplate);
        node.appendChild(avatar);
        node.appendChild(speech);

        this.agentsLayer.appendChild(node);
        this.agentNodes.set(agent.id, node);
      }

      // Smooth Position Update
      node.style.left = `${agent.x}%`;
      node.style.top = `${agent.y}%`;

      // State Classes
      node.className = "living-agent-node";
      if (agent.is_active) node.classList.add("state-working");
      if (agent.is_blocked) node.classList.add("state-blocked");
      if (agent.is_bodyguard) node.classList.add("is-bodyguard");

      // Update Subtitle & Speech
      const subtitle = node.querySelector(".nameplate-subtitle");
      if (subtitle) subtitle.textContent = agent.title;

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
      }
    }
  }

  updateCourierTransport(agents) {
    if (!this.courierPacket) return;

    const courier = agents.find(a => a.id === "agent-courier-relay");
    const activeWorker = agents.find(a => a.is_active && a.id !== "agent-chief-commander" && a.id !== "smart-resource-router");

    if (activeWorker && courier) {
      this.courierPacket.style.display = "flex";
      // Position between worker and courier/chief
      const px = (activeWorker.x + courier.x) / 2;
      const py = (activeWorker.y + courier.y) / 2;
      this.courierPacket.style.left = `${px}%`;
      this.courierPacket.style.top = `${py}%`;
      if (this.courierPacketLabel) {
        this.courierPacketLabel.textContent = activeWorker.progress > 0.8 ? "RESULT_READY" : "TASK_DISPATCH";
      }
    } else {
      this.courierPacket.style.display = "none";
    }
  }

  updateTelemetryAndGate(stateData, metrics) {
    // SNITCH Permission Guard
    const pg = resolvePermissionGuardTruth(stateData);
    if (this.snitchPermStatus) {
      this.snitchPermStatus.textContent = pg.status || "PERMISSIONS HEALTHY";
      this.snitchPermStatus.className = pg.status === "DANGEROUS REQUEST" ? "text-danger" : "badge-perm-healthy";
    }
    if (this.snitchPermCommand) this.snitchPermCommand.textContent = pg.last_command || "curl -s http://127.0.0.1:8088/api/state";
    if (this.snitchPermRuleRec) this.snitchPermRuleRec.textContent = pg.rule_recommendation || "ALREADY_ALLOWED";

    // Workflow
    if (this.liveWfId) this.liveWfId.textContent = metrics.current_workflow || "WF-IDLE";
    if (this.liveWfStatus) this.liveWfStatus.textContent = metrics.active_agents > 0 ? "IN_PROGRESS" : "IDLE";
    if (this.liveWfBar) this.liveWfBar.style.width = `${Math.min(100, metrics.active_agents * 25)}%`;

    // Treasury
    const treasury = resolveTreasuryTruth(stateData);
    if (this.treasuryEur) this.treasuryEur.textContent = treasury.eur || "UNKNOWN";
    if (this.treasuryUsd) this.treasuryUsd.textContent = treasury.usd || "UNKNOWN";
    if (this.treasuryVerified) this.treasuryVerified.textContent = treasury.revenue_evidence || "NOT_VERIFIED";
    if (this.treasuryGoal) this.treasuryGoal.textContent = treasury.goal_label || "$8 / $1,000,000,000";

    // Repositories & Context
    if (this.panelCtxVer) this.panelCtxVer.textContent = metrics.context_version ? `v${metrics.context_version}` : "v64";
    if (this.panelCtxHash) this.panelCtxHash.textContent = metrics.snapshot_hash ? `${metrics.snapshot_hash.slice(0, 16)}...` : "8f0874f495cf...";
    if (this.panelRepoCourier) this.panelRepoCourier.textContent = metrics.repo_courier_head ? metrics.repo_courier_head.slice(0, 8) : "e7edad01";
    if (this.panelRepoMemory) this.panelRepoMemory.textContent = metrics.repo_memory_head ? metrics.repo_memory_head.slice(0, 8) : "62c658b0";

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
