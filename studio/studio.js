/**
 * 2026 Courier // Living Agent HQ Operations Cockpit Controller
 * 100% Deterministic Local State Binding — 0 Model Calls for UI
 */

import {
  resolveLivingRoomAgents,
  resolveBodyguardsTruth,
  resolveLiveHQMetrics,
  resolveSnitchTruth,
  resolvePermissionGuardTruth,
  resolveStewardTruth,
  resolveTeacherTruth,
  resolveDirectorTruth,
  resolveAcademyEconomics,
  resolveCorrelationTruth,
  resolveDecisionTruth,
  resolveGateDecisionTruth,
} from "./execution_truth.js";

class LivingHQController {
  constructor() {
    this.pollInterval = 500;
    this.isPolling = false;
    this.currentView = "overview";
    this.previousAgentsState = {};
    
    this.initElements();
    this.bindEvents();
    this.startClock();
    this.startPolling();
  }

  initElements() {
    // Stage & Views
    this.stage = document.getElementById("living-hq-stage");
    this.agentsLayer = document.getElementById("living-agents-layer");
    this.camButtons = document.querySelectorAll(".cam-btn");

    // Header & Controls
    this.serverStatus = document.getElementById("server-status");
    this.courierCommit = document.getElementById("courier-commit");
    this.contextPillVer = document.getElementById("context-pill-ver");
    this.btn16x9 = document.getElementById("btn-aspect-16-9");
    this.btn9x16 = document.getElementById("btn-aspect-9-16");
    this.btnRecord = document.getElementById("btn-recording-mode");
    this.btnToggleDetails = document.getElementById("btn-toggle-details");
    this.btnCloseDrawer = document.getElementById("btn-close-drawer");
    this.drawer = document.getElementById("control-panel-drawer");
    this.liveClock = document.getElementById("hq-live-clock");

    // Big TV Wall Elements
    this.tvActiveCount = document.getElementById("tv-active-count");
    this.tvCapacityPct = document.getElementById("tv-capacity-pct");
    this.tvWorkstationsTotal = document.getElementById("tv-workstations-total");
    this.tvWsActive = document.getElementById("tv-ws-active");
    this.tvWsIdle = document.getElementById("tv-ws-idle");
    this.tvOverviewContext = document.getElementById("tv-overview-context");
    this.tvOverviewWorkflow = document.getElementById("tv-overview-workflow");
    this.tvOverviewCorrelation = document.getElementById("tv-overview-correlation");
    this.tvOverviewSchool = document.getElementById("tv-overview-school");

    // Panel 1: SNITCH 3.0 Permission Guard
    this.snitchPermStatus = document.getElementById("snitch-perm-status");
    this.snitchPermCommand = document.getElementById("snitch-perm-command");
    this.snitchPermRuleRec = document.getElementById("snitch-perm-rule-rec");
    this.snitchPermUpdated = document.getElementById("snitch-perm-updated");
    this.snitchMiniEvents = document.getElementById("snitch-mini-events");

    // Panel 2: Live Workflow
    this.liveWfId = document.getElementById("live-wf-id");
    this.liveWfCorrelation = document.getElementById("live-wf-correlation");
    this.liveWfTimeline = document.getElementById("live-wf-timeline");
    this.liveWfStatus = document.getElementById("live-wf-status");
    this.liveWfPct = document.getElementById("live-wf-pct");
    this.liveWfBar = document.getElementById("live-wf-bar");

    // Panel 3: Agent Activity Feed
    this.activityFeedList = document.getElementById("activity-feed-list");

    // Panel 4: Context & Repositories
    this.panelCtxVer = document.getElementById("panel-ctx-ver");
    this.panelCtxPrev = document.getElementById("panel-ctx-prev");
    this.panelCtxHash = document.getElementById("panel-ctx-hash");
    this.panelCtxRefresh = document.getElementById("panel-ctx-refresh");
    this.panelRepoCourier = document.getElementById("panel-repo-courier");
    this.panelRepoMemory = document.getElementById("panel-repo-memory");
    this.panelCtxSyncBar = document.getElementById("panel-ctx-sync-bar");
    this.panelCtxStatusLabel = document.getElementById("panel-ctx-status-label");

    // Footer Elements
    this.footerSchoolTime = document.getElementById("footer-school-time");
    this.footerGateStatus = document.getElementById("footer-gate-status");
    this.footerIncidentsCount = document.getElementById("footer-incidents-count");

    // Drawer / Inbox Elements
    this.humanIdeaInput = document.getElementById("human-idea-input");
    this.btnDispatchIdea = document.getElementById("btn-dispatch-idea");
    this.presetButtons = document.querySelectorAll(".preset-btn");
    this.gateBanner = document.getElementById("human-gate-banner");
    this.gateDesc = document.getElementById("gate-desc");
    this.btnGateApprove = document.getElementById("btn-gate-approve");
    this.btnGateReject = document.getElementById("btn-gate-reject");
    this.treasuryEur = document.getElementById("treasury-eur");
    this.treasuryUsd = document.getElementById("treasury-usd");
    this.treasuryVerified = document.getElementById("treasury-verified");
    this.treasuryGoal = document.getElementById("treasury-goal");
  }

  bindEvents() {
    // Camera View Switching
    this.camButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        this.camButtons.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const view = btn.getAttribute("data-view");
        this.setCameraView(view);
      });
    });

    // Aspect Ratio Toggles
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

    // Recording Mode
    this.btnRecord?.addEventListener("click", () => {
      document.body.classList.toggle("mode-recording");
      this.btnRecord.classList.toggle("active");
    });

    // Toggle Details Drawer
    this.btnToggleDetails?.addEventListener("click", () => {
      this.drawer?.classList.toggle("hidden");
    });

    this.btnCloseDrawer?.addEventListener("click", () => {
      this.drawer?.classList.add("hidden");
    });

    document.getElementById("link-view-audit")?.addEventListener("click", (e) => {
      e.preventDefault();
      this.drawer?.classList.remove("hidden");
    });

    document.getElementById("link-view-feed")?.addEventListener("click", (e) => {
      e.preventDefault();
      this.drawer?.classList.remove("hidden");
    });

    // Preset Pills
    this.presetButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const idea = btn.getAttribute("data-idea");
        if (this.humanIdeaInput && idea) {
          this.humanIdeaInput.value = idea;
        }
      });
    });

    // Dispatch Directive
    this.btnDispatchIdea?.addEventListener("click", () => this.dispatchHumanIdea());

    // Human Gate Actions
    this.btnGateApprove?.addEventListener("click", () => this.sendGateDecision(true));
    this.btnGateReject?.addEventListener("click", () => this.sendGateDecision(false));
  }

  setCameraView(view) {
    this.currentView = view;
    if (!this.stage) return;
    this.stage.className = "living-hq-stage view-" + view;
  }

  startClock() {
    const updateTime = () => {
      const now = new Date();
      const utcString = now.toUTCString().split(" ")[4];
      if (this.liveClock) {
        this.liveClock.textContent = `HQ TIME: ${utcString} UTC`;
      }
    };
    updateTime();
    setInterval(updateTime, 1000);
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
          if (this.serverStatus) {
            this.serverStatus.textContent = "LIVE BUS CONNECTED";
          }
        }
      } catch (err) {
        if (this.serverStatus) {
          this.serverStatus.textContent = "RECONNECTING LOCAL BUS...";
        }
      } finally {
        setTimeout(poll, this.pollInterval);
      }
    };

    poll();
  }

  updateLivingHQ(stateData) {
    // 1. Resolve and Render Living Agents Layer
    const agents = resolveLivingRoomAgents(stateData);
    this.renderLivingAgents(agents);

    // 2. Resolve Master TV Wall & Overview Metrics
    const metrics = resolveLiveHQMetrics(stateData);
    if (this.tvActiveCount) this.tvActiveCount.textContent = metrics.active_agents;
    if (this.tvCapacityPct) this.tvCapacityPct.textContent = `${Math.round((metrics.active_agents / 40) * 100)}% Capacity`;
    if (this.tvWorkstationsTotal) this.tvWorkstationsTotal.textContent = metrics.total_desks;
    if (this.tvWsActive) this.tvWsActive.textContent = metrics.active_agents;
    if (this.tvWsIdle) this.tvWsIdle.textContent = metrics.idle_agents;

    const bus = stateData?.bus || {};
    const wf = metrics.current_workflow || "IDLE_MONITORING";
    const corr = metrics.correlation_id || "corr-demo-c94b85b8";
    const ctxVer = metrics.context_version ? `v${metrics.context_version}` : "v64";

    if (this.tvOverviewWorkflow) this.tvOverviewWorkflow.textContent = wf;
    if (this.tvOverviewCorrelation) this.tvOverviewCorrelation.textContent = corr;
    if (this.tvOverviewContext) this.tvOverviewContext.textContent = ctxVer;
    if (this.contextPillVer) this.contextPillVer.textContent = `CONTEXT: ${ctxVer}`;

    const teacher = resolveTeacherTruth(stateData);
    const nextSchool = teacher.next_school_time || "06:00 UTC";
    if (this.tvOverviewSchool) this.tvOverviewSchool.textContent = nextSchool;
    if (this.footerSchoolTime) this.footerSchoolTime.textContent = nextSchool;

    // Flow State Indicator
    const isFlowActive = Boolean(wf && wf !== "IDLE_MONITORING");
    this.stage?.classList.toggle("is-flow-active", isFlowActive);

    // 3. Panel 1: SNITCH 3.0 Permission Guard
    const pg = resolvePermissionGuardTruth(stateData);
    if (this.snitchPermStatus) {
      this.snitchPermStatus.textContent = pg.status;
      this.snitchPermStatus.className = `badge font-mono badge-perm-${pg.status.toLowerCase().replace(/_/g, "-").replace(/\s+/g, "-")}`;
    }
    if (this.snitchPermCommand) this.snitchPermCommand.textContent = pg.last_checked_command;
    if (this.snitchPermRuleRec) this.snitchPermRuleRec.textContent = pg.rule_match || pg.recommendation;

    // 4. Panel 2: Live Workflow
    if (this.liveWfId) this.liveWfId.textContent = wf;
    if (this.liveWfCorrelation) this.liveWfCorrelation.textContent = corr;
    
    // Progress resolution
    let activeProgress = 0;
    const activeAgent = agents.find(a => a.is_active);
    if (activeAgent) {
      activeProgress = Math.round(activeAgent.progress * 100);
    } else if (wf !== "IDLE_MONITORING") {
      activeProgress = 100;
    }
    if (this.liveWfPct) this.liveWfPct.textContent = `${activeProgress}%`;
    if (this.liveWfBar) this.liveWfBar.style.width = `${activeProgress}%`;
    if (this.liveWfStatus) this.liveWfStatus.textContent = `STATUS: ${activeProgress === 100 ? "COMPLETED" : (activeProgress > 0 ? "IN_PROGRESS" : "IDLE")}`;

    // 5. Panel 4: Context & Repositories
    const steward = resolveStewardTruth(stateData);
    if (this.panelCtxVer) this.panelCtxVer.textContent = `v${steward.context_version || 64}`;
    if (this.panelCtxPrev) this.panelCtxPrev.textContent = `v${steward.previous_version || 63}`;
    if (this.panelCtxHash) this.panelCtxHash.textContent = (steward.snapshot_hash || "8f0874f495cf").slice(0, 12) + "...";
    if (this.panelCtxRefresh) this.panelCtxRefresh.textContent = steward.last_refresh ? steward.last_refresh.split("T")[1]?.slice(0, 8) || "17:37:43" : "17:37:43";

    const headShort = stateData?.context_snapshot?.courier_head ? stateData.context_snapshot.courier_head.slice(0, 8) : "e7edad01";
    const memShort = stateData?.context_snapshot?.memory_head ? stateData.context_snapshot.memory_head.slice(0, 8) : "62c658b0";
    if (this.courierCommit) this.courierCommit.textContent = `HEAD: ${headShort}`;
    if (this.panelRepoCourier) this.panelRepoCourier.textContent = headShort;
    if (this.panelRepoMemory) this.panelRepoMemory.textContent = memShort;
    if (this.panelCtxStatusLabel) this.panelCtxStatusLabel.textContent = `Status: Context v${steward.context_version || 64} (${(steward.snapshot_hash || "8f0874f4").slice(0, 8)}) 100%`;

    // 6. Treasury & Human Gate
    const treasury = resolveAcademyEconomics(stateData);
    if (this.treasuryEur) this.treasuryEur.textContent = treasury.eur_balance;
    if (this.treasuryUsd) this.treasuryUsd.textContent = treasury.usd_balance;
    if (this.treasuryVerified) this.treasuryVerified.textContent = treasury.revenue_evidence;

    const gate = resolveGateDecisionTruth(stateData);
    if (this.gateBanner) {
      if (gate.is_active) {
        this.gateBanner.classList.remove("hidden");
        if (this.gateDesc) this.gateDesc.textContent = gate.reason;
        if (this.footerGateStatus) this.footerGateStatus.textContent = "REQUIRED";
      } else {
        this.gateBanner.classList.add("hidden");
        if (this.footerGateStatus) this.footerGateStatus.textContent = "ACTIVE";
      }
    }
  }

  renderLivingAgents(agents) {
    if (!this.agentsLayer) return;

    agents.forEach(agent => {
      let node = document.getElementById(`agent-node-${agent.id}`);
      if (!node) {
        node = document.createElement("div");
        node.id = `agent-node-${agent.id}`;
        node.className = "agent-character-node";
        node.innerHTML = `
          <div class="agent-speech-bubble" style="display: none;"></div>
          <div class="agent-nameplate">
            <span class="nameplate-main">${agent.name}</span>
            <span class="nameplate-sub">${agent.title}</span>
          </div>
          <div class="agent-sprite">
            <div class="sprite-robot"></div>
          </div>
        `;
        this.agentsLayer.appendChild(node);
      }

      // Smooth coordinate update
      node.style.left = `${agent.x}%`;
      node.style.top = `${agent.y}%`;

      // Status styling
      node.classList.toggle("active", agent.is_active);
      node.classList.toggle("blocked", agent.is_blocked);

      // Nameplate update
      const sub = node.querySelector(".nameplate-sub");
      if (sub) {
        sub.textContent = agent.is_active ? `TASK: ${agent.task?.slice(0, 16) || "BUSY"}` : agent.title;
      }

      // Speech bubble update
      const bubble = node.querySelector(".agent-speech-bubble");
      if (bubble) {
        if (agent.speech && (agent.is_active || agent.is_blocked || agent.id === "agent-chief-commander" || agent.id === "agent-snitch")) {
          bubble.textContent = agent.speech;
          bubble.style.display = "block";
        } else {
          bubble.style.display = "none";
        }
      }
    });
  }

  async dispatchHumanIdea() {
    const text = this.humanIdeaInput?.value?.trim();
    if (!text) return;

    try {
      const resp = await fetch("/api/idea", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idea: text, type: "IDEA" }),
      });
      if (resp.ok) {
        if (this.humanIdeaInput) this.humanIdeaInput.value = "";
        this.drawer?.classList.add("hidden");
      }
    } catch (e) {
      console.error("Error dispatching idea:", e);
    }
  }

  async sendGateDecision(approved) {
    try {
      await fetch("/api/gate/decision", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved, decision: approved ? "APPROVE" : "REJECT" }),
      });
    } catch (e) {
      console.error("Error sending gate decision:", e);
    }
  }
}

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  window.livingHQ = new LivingHQController();
});
