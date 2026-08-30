/**
 * 2026 Courier // Autonomous Chief Operations Cockpit Controller
 */
import {
  executionBadgeLabel,
  resolveChiefWaitState,
  resolveCorrelationTruth,
  resolveDecisionTruth,
  resolveExecutionTruth,
  resolveStewardTruth,
  resolveThreadContext,
} from './execution_truth.js';

class OperationsStudio {
  constructor() {
    this.pollInterval = 500;
    this.isPolling = false;
    this.currentWorkflow = null;
    this.currentCorrelation = null;
    this.initElements();
    this.bindEvents();
    this.startPolling();
  }

  initElements() {
    // Controls & Inbox
    this.btn16x9 = document.getElementById('btn-aspect-16-9');
    this.btn9x16 = document.getElementById('btn-aspect-9-16');
    this.btnRecord = document.getElementById('btn-recording-mode');
    this.ideaInput = document.getElementById('human-idea-input');
    this.btnDispatchIdea = document.getElementById('btn-dispatch-idea');
    this.presetBtns = document.querySelectorAll('.preset-btn');

    // Human Gate Banner
    this.gateBanner = document.getElementById('human-gate-banner');
    this.gateDesc = document.getElementById('gate-desc');
    this.btnGateApprove = document.getElementById('btn-gate-approve');
    this.btnGateReject = document.getElementById('btn-gate-reject');

    // Thought Curator Elements
    this.badgeCuratorState = document.getElementById('badge-curator-state');
    this.curatorClass = document.getElementById('curator-class');
    this.curatorTaskLabel = document.getElementById('curator-task-label');
    this.curatorProgressNum = document.getElementById('curator-progress-num');
    this.curatorProgressBar = document.getElementById('curator-progress-bar');
    this.curatorFeedLog = document.getElementById('curator-feed-log');
    this.curatorMemoryLinks = document.getElementById('curator-memory-links');
    this.curatorAffectedAgents = document.getElementById('curator-affected-agents');
    this.curatorContextDelta = document.getElementById('curator-context-delta');

    // Update Steward Elements
    this.badgeStewardState = document.getElementById('badge-steward-state');
    this.stewardContextVersion = document.getElementById('steward-context-version');
    this.stewardPrevVersion = document.getElementById('steward-prev-version');
    this.stewardSnapshotHash = document.getElementById('steward-snapshot-hash');
    this.stewardLastRefresh = document.getElementById('steward-last-refresh');
    this.stewardRepos = document.getElementById('steward-repos');
    this.repoCourier = document.getElementById('repo-courier');
    this.repoMemory = document.getElementById('repo-memory');
    this.repoGodot = document.getElementById('repo-godot');
    this.stewardChangedItems = document.getElementById('steward-changed-items');
    this.stewardTaskLabel = document.getElementById('steward-task-label');
    this.stewardProgressNum = document.getElementById('steward-progress-num');
    this.stewardProgressBar = document.getElementById('steward-progress-bar');
    this.stewardFeedLog = document.getElementById('steward-feed-log');

    // Flow Steps
    this.step1 = document.getElementById('step-1');
    this.step2 = document.getElementById('step-2');
    this.step3 = document.getElementById('step-3');
    this.step4 = document.getElementById('step-4');
    this.step5 = document.getElementById('step-5');

    // Chief Elements
    this.badgeChiefState = document.getElementById('badge-chief-state');
    this.chiefWorkflow = document.getElementById('chief-workflow');
    this.chiefWaitState = document.getElementById('chief-wait-state');
    this.chiefLastDecision = document.getElementById('chief-last-decision');
    this.chiefContextVersion = document.getElementById('chief-context-version');
    this.chiefTaskLabel = document.getElementById('chief-task-label');
    this.chiefProgressNum = document.getElementById('chief-progress-num');
    this.chiefProgressBar = document.getElementById('chief-progress-bar');
    this.chiefFeedLog = document.getElementById('chief-feed-log');

    // Courier Bus Elements
    this.badgeBusState = document.getElementById('badge-bus-state');
    this.countDispatch = document.getElementById('count-dispatch');
    this.countProcessed = document.getElementById('count-processed');
    this.countDecisions = document.getElementById('count-decisions');
    this.busLockStatus = document.getElementById('bus-lock-status');
    this.threadCorrelation = document.getElementById('thread-correlation');
    this.threadActors = document.getElementById('thread-actors');

    // Antigravity Elements
    this.badgeAgMode = document.getElementById('badge-ag-mode');
    this.agState = document.getElementById('ag-state');
    this.agTaskLabel = document.getElementById('ag-task-label');
    this.agProgressNum = document.getElementById('ag-progress-num');
    this.agProgressBar = document.getElementById('ag-progress-bar');
    this.agFeedLog = document.getElementById('ag-feed-log');

    // Codex Elements
    this.badgeCodexMode = document.getElementById('badge-codex-mode');
    this.codexState = document.getElementById('codex-state');
    this.codexTaskLabel = document.getElementById('codex-task-label');
    this.codexProgressNum = document.getElementById('codex-progress-num');
    this.codexProgressBar = document.getElementById('codex-progress-bar');
    this.codexFeedLog = document.getElementById('codex-feed-log');

    // Footer
    this.footerStewardStatus = document.getElementById('footer-steward-status');
    this.lastPollTime = document.getElementById('last-poll-time');
    this.serverStatus = document.getElementById('server-status');
  }

  bindEvents() {
    this.btn16x9.addEventListener('click', () => {
      document.body.classList.remove('view-9-16');
      this.btn16x9.classList.add('active');
      this.btn9x16.classList.remove('active');
    });

    this.btn9x16.addEventListener('click', () => {
      document.body.classList.add('view-9-16');
      this.btn9x16.classList.add('active');
      this.btn16x9.classList.remove('active');
    });

    this.btnRecord.addEventListener('click', () => {
      document.body.classList.toggle('recording-mode');
    });

    this.presetBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const idea = btn.getAttribute('data-idea');
        this.ideaInput.value = idea;
      });
    });

    this.btnDispatchIdea.addEventListener('click', () => this.submitHumanIdea());
    this.ideaInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.submitHumanIdea();
    });

    this.btnGateApprove.addEventListener('click', () => this.sendHumanGateDecision('APPROVE'));
    this.btnGateReject.addEventListener('click', () => this.sendHumanGateDecision('REJECT'));
  }

  async sendHumanGateDecision(action) {
    if (!this.currentWorkflow || !this.currentCorrelation) {
      this.appendLog(this.chiefFeedLog, '[HUMAN GATE] WAITING_FOR_HUMAN: no verified workflow and correlation are available.');
      return;
    }

    try {
      this.btnGateApprove.disabled = true;
      this.btnGateReject.disabled = true;
      const res = await fetch('/api/human-gate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: action,
          workflow_id: this.currentWorkflow,
          correlation_id: this.currentCorrelation,
          reason: `Human operator executed ${action} action in Studio Cockpit`,
        }),
      });
      const data = await res.json();
      this.appendLog(this.chiefFeedLog, `[HUMAN GATE] Decision persisted: ${action} (${data.approval_id || 'OK'})`);
      this.gateBanner.classList.add('hidden');
    } catch (err) {
      console.error('Failed to submit human gate action:', err);
    } finally {
      this.btnGateApprove.disabled = false;
      this.btnGateReject.disabled = false;
    }
  }

  async submitHumanIdea() {
    const idea = this.ideaInput.value.trim();
    if (!idea) return;

    try {
      this.btnDispatchIdea.disabled = true;
      this.btnDispatchIdea.innerHTML = '<span class="dispatch-icon">⏳</span> CURATING...';
      
      this.appendLog(this.curatorFeedLog, `[INGEST] Human idea: "${idea}"`);
      this.appendLog(this.chiefFeedLog, `[HUMAN IDEA] Forwarded for processing: "${idea}"`);

      const res = await fetch('/api/submit-idea', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idea: idea, type: 'IDEA' }),
      });

      const data = await res.json();
      console.log('Idea processed by Curator & Chief:', data);
      this.ideaInput.value = '';
    } catch (err) {
      console.error('Failed to submit idea:', err);
    } finally {
      setTimeout(() => {
        this.btnDispatchIdea.disabled = false;
        this.btnDispatchIdea.innerHTML = '<span class="dispatch-icon">⚡</span> DISPATCH TO CURATOR & CHIEF';
      }, 1500);
    }
  }

  startPolling() {
    this.isPolling = true;
    this.poll();
  }

  async poll() {
    try {
      const response = await fetch('/api/state');
      if (response.ok) {
        const state = await response.json();
        this.updateUI(state);
        this.serverStatus.textContent = 'LIVE BUS CONNECTED';
        this.serverStatus.style.color = 'var(--text-primary)';
      } else {
        this.serverStatus.textContent = 'BUS DISCONNECTED';
        this.serverStatus.style.color = 'var(--accent-red)';
      }
    } catch (err) {
      this.serverStatus.textContent = 'STANDALONE OFFLINE';
      this.serverStatus.style.color = 'var(--text-muted)';
    }

    const now = new Date();
    this.lastPollTime.textContent = now.toTimeString().split(' ')[0];

    if (this.isPolling) {
      setTimeout(() => this.poll(), this.pollInterval);
    }
  }

  updateFlowSteps(state) {
    [this.step1, this.step2, this.step3, this.step4, this.step5].forEach(s => s.classList.remove('active'));

    if (state === 'NEW IDEA') {
      this.step1.classList.add('active');
    } else if (state === 'READING MEMORY') {
      this.step2.classList.add('active');
    } else if (state === 'COMPARING' || state === 'DUPLICATE FOUND' || state === 'RELATED' || state === 'RELATED FOUND' || state === 'CONFLICT') {
      this.step3.classList.add('active');
    } else if (state === 'CONTEXT UPDATED') {
      this.step4.classList.add('active');
    } else if (state === 'SENT TO CHIEF' || state === 'PROMOTED') {
      this.step5.classList.add('active');
    }
  }

  updateUI(data) {
    if (!data) return;

    const { agents = {}, counts = {}, bus = {} } = data;

    // Preserve only identifiers received from Courier state.  The UI never
    // synthesizes a workflow/correlation identity for a human-gate decision.
    this.currentWorkflow = typeof bus.active_workflow === 'string'
      && bus.active_workflow
      && bus.active_workflow !== 'IDLE_MONITORING'
      ? bus.active_workflow
      : null;
    this.currentCorrelation = resolveCorrelationTruth(bus);
    const hasVerifiedGateContext = Boolean(this.currentWorkflow && this.currentCorrelation);
    this.btnGateApprove.disabled = !hasVerifiedGateContext;
    this.btnGateReject.disabled = !hasVerifiedGateContext;

    // 1. Update Bus Counts
    this.countDispatch.textContent = counts.dispatch || 0;
    this.countProcessed.textContent = counts.processed || 0;
    this.countDecisions.textContent = counts.decisions || 0;
    this.busLockStatus.textContent = bus.is_locked ? `LOCKED (${bus.active_lock})` : 'UNLOCKED';

    // 2. Update Thought Curator Station
    const curator = agents['agent-thought-curator'] || {};
    const curatorState = curator.state || 'IDLE';
    this.badgeCuratorState.textContent = curatorState;
    this.curatorTaskLabel.textContent = curator.task ? `Task: ${curator.task}` : 'Status: Standby';
    this.curatorClass.textContent = curator.result ? curator.result.split('|')[0].replace('Classification:', '').trim() : (curator.last_action ? curator.last_action.split('->')[0].replace('Classified as', '').trim() : '-');
    const curatorProgress = Math.round((curator.progress || 0) * 100);
    this.curatorProgressNum.textContent = `${curatorProgress}%`;
    this.curatorProgressBar.style.width = `${curatorProgress}%`;

    this.updateFlowSteps(curatorState);

    if (curator.workflow) {
      this.curatorContextDelta.textContent = `📦 DELTA [${curator.workflow}]: ${curator.result || curator.last_action || 'Context compiled'}`;
    }

    if (curator.last_action) {
      this.appendLog(this.curatorFeedLog, `[CURATOR] ${curator.last_action}`);
    }

    const curatorCard = document.getElementById('station-curator');
    if (curatorState === 'COMPARING' || curatorState === 'NEW IDEA' || curatorState === 'READING MEMORY') {
      curatorCard.classList.add('active-working');
    } else {
      curatorCard.classList.remove('active-working');
    }

    // 3. Update Context Sync / Update Steward Station
    const steward = resolveStewardTruth(data);
    this.badgeStewardState.textContent = steward.state;
    this.stewardContextVersion.textContent = steward.context_version !== null ? `v${steward.context_version}` : '-';
    this.stewardPrevVersion.textContent = steward.previous_version !== null ? `v${steward.previous_version}` : '-';
    this.stewardSnapshotHash.textContent = steward.snapshot_hash ? `${steward.snapshot_hash.slice(0, 12)}...` : '-';
    this.stewardLastRefresh.textContent = steward.last_refresh
      ? (steward.last_refresh.includes('T') ? steward.last_refresh.split('T')[1].split('.')[0] : steward.last_refresh)
      : '--:--:--';

    // Update Repositories Chips
    if (steward.repositories) {
      this.repoCourier.textContent = `Courier: ${steward.repositories.courier_head ? steward.repositories.courier_head.slice(0, 8) : '-'}`;
      this.repoMemory.textContent = `Memory: ${steward.repositories.memory_head ? steward.repositories.memory_head.slice(0, 8) : '-'}`;
      this.repoGodot.textContent = `Godot: ${steward.repositories.godot_head ? (steward.repositories.godot_head === 'NOT_CONNECTED' ? 'NOT_CONNECTED' : steward.repositories.godot_head.slice(0, 8)) : 'NOT_CONNECTED'}`;
    }

    // Update Changed Items Container
    if (this.stewardChangedItems) {
      if (steward.changed_items && steward.changed_items.length > 0) {
        this.stewardChangedItems.innerHTML = steward.changed_items
          .map(item => `<span class="affected-pill font-mono">${item}</span>`)
          .join(' ');
      } else {
        this.stewardChangedItems.innerHTML = '<span class="affected-pill font-mono">NONE (CURRENT)</span>';
      }
    }

    this.stewardTaskLabel.textContent = `Status: ${steward.task}`;
    const stewardProgress = Math.round((steward.progress || 0) * 100);
    this.stewardProgressNum.textContent = `${stewardProgress}%`;
    this.stewardProgressBar.style.width = `${stewardProgress}%`;

    if (steward.next_action) {
      this.appendLog(this.stewardFeedLog, `[STEWARD] ${steward.next_action}`);
    }

    const stewardCard = document.getElementById('station-steward');
    if (stewardCard) {
      if (steward.state === 'CHECKING' || steward.state === 'SNAPSHOT UPDATED' || steward.state === 'REFRESH REQUIRED') {
        stewardCard.classList.add('active-working');
      } else {
        stewardCard.classList.remove('active-working');
      }
    }

    // 4. Update Chief Station & Thread Context
    const chief = agents['agent-chief-commander'] || {};
    const chiefState = chief.state || (bus.is_locked ? 'COORDINATING' : 'IDLE');
    const threadContext = resolveThreadContext(data);
    const chiefWaitState = resolveChiefWaitState(data);

    this.badgeChiefState.textContent = chiefState;
    this.chiefWorkflow.textContent = chief.workflow || bus.active_workflow || '-';
    this.chiefWaitState.textContent = chiefWaitState;
    this.chiefLastDecision.textContent = resolveDecisionTruth(bus);
    this.chiefContextVersion.textContent = threadContext.context_version ? `v${threadContext.context_version}` : '-';
    this.chiefTaskLabel.textContent = chief.task ? `Task: ${chief.task}` : 'Task: Standby';
    const chiefProgress = Math.round((chief.progress || 0) * 100);
    this.chiefProgressNum.textContent = `${chiefProgress}%`;
    this.chiefProgressBar.style.width = `${chiefProgress}%`;

    if (chief.last_action) {
      this.appendLog(this.chiefFeedLog, `[CHIEF] ${chief.last_action}`);
    }

    const chiefCard = document.getElementById('station-chief');
    if (chiefState === 'RUNNING' || chiefState === 'COORDINATING') {
      chiefCard.classList.add('active-working');
    } else {
      chiefCard.classList.remove('active-working');
    }

    // Update Bus Hub Thread Context Indicators
    if (this.threadCorrelation) {
      this.threadCorrelation.textContent = threadContext.correlation_id || 'NONE';
    }
    if (this.threadActors) {
      const sender = threadContext.sender_agent_type ? threadContext.sender_agent_type.toUpperCase() : '-';
      this.threadActors.textContent = `${sender} → CHIEF`;
    }

    // Update Footer Status
    if (this.footerStewardStatus) {
      this.footerStewardStatus.textContent = steward.context_version
        ? `ACTIVE (SNAPSHOT V${steward.context_version})`
        : 'STANDBY';
    }

    // 4. Update Antigravity Station (Primary Heavy Worker)
    const ag = agents['agent-antigravity-bridge'] || {};
    const agExecClass = resolveExecutionTruth(ag);
    this.setExecutionBadge(this.badgeAgMode, agExecClass);
    this.agState.textContent = ag.state || 'IDLE';
    this.agTaskLabel.textContent = ag.task ? `Task: ${ag.task}` : 'Task: IDLE';
    const agProgress = Math.round((ag.progress || 0) * 100);
    this.agProgressNum.textContent = `${agProgress}%`;
    this.agProgressBar.style.width = `${agProgress}%`;

    if (ag.last_action) {
      this.appendLog(this.agFeedLog, `[AG] ${ag.last_action}`);
    }

    const agCard = document.getElementById('station-antigravity');
    if (ag.state === 'RUNNING') {
      agCard.classList.add('active-working');
    } else {
      agCard.classList.remove('active-working');
    }

    // 5. Update Codex Station (Scarce Technical Specialist)
    const codex = agents['agent-codex-bridge'] || {};
    const codexExecClass = resolveExecutionTruth(codex);
    this.setExecutionBadge(this.badgeCodexMode, codexExecClass);
    this.codexState.textContent = codex.state || 'IDLE';
    this.codexTaskLabel.textContent = codex.task ? `Task: ${codex.task}` : 'Task: IDLE';
    const cdxProgress = Math.round((codex.progress || 0) * 100);
    this.codexProgressNum.textContent = `${cdxProgress}%`;
    this.codexProgressBar.style.width = `${cdxProgress}%`;

    if (codex.last_action) {
      this.appendLog(this.codexFeedLog, `[CODEX] ${codex.last_action}`);
    }

    const codexCard = document.getElementById('station-codex');
    if (codex.state === 'RUNNING') {
      codexCard.classList.add('active-working');
    } else {
      codexCard.classList.remove('active-working');
    }

    // 6. Human Gate Alert Banner
    if (curatorState === 'CONFLICT' || curatorState === 'BLOCKED' || chief.state === 'BLOCKED_HUMAN_GATE' || chief.state === 'BLOCKED_POLICY_CONFLICT' || codex.state === 'BLOCKED_HUMAN_GATE' || ag.state === 'BLOCKED_HUMAN_GATE' || bus.human_gate) {
      this.gateBanner.classList.remove('hidden');
      this.gateDesc.textContent = `Workflow task paused: ${curator.last_action || codex.task || ag.task || chief.task || 'Explicit human approval required'}`;
    } else {
      this.gateBanner.classList.add('hidden');
    }
  }

  setExecutionBadge(element, executionClass) {
    element.textContent = executionBadgeLabel(executionClass);
    element.classList.remove(
      'execution-real',
      'execution-deterministic',
      'execution-fallback',
      'execution-simulated',
      'execution-registered',
      'execution-human-gate',
      'execution-blocked',
      'execution-unknown',
    );
    const styleClass = {
      REAL_CODEX_CLI: 'execution-real',
      REAL_ANTIGRAVITY: 'execution-real',
      DETERMINISTIC_CODEX: 'execution-deterministic',
      DETERMINISTIC_ANTIGRAVITY: 'execution-deterministic',
      FALLBACK: 'execution-fallback',
      SIMULATED_VISUAL: 'execution-simulated',
      REGISTERED: 'execution-registered',
      WAITING_FOR_HUMAN: 'execution-human-gate',
      BLOCKED: 'execution-blocked',
      UNKNOWN: 'execution-unknown',
    }[executionClass] || 'execution-unknown';
    element.classList.add(styleClass);
  }

  appendLog(feedElement, text) {
    if (!feedElement) return;
    const lastEntry = feedElement.lastElementChild;
    if (lastEntry && lastEntry.textContent === text) return;

    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.textContent = text;
    feedElement.appendChild(entry);
    feedElement.scrollTop = feedElement.scrollHeight;
  }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  window.studio = new OperationsStudio();
});
