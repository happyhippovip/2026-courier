/**
 * 2026 Courier // Autonomous Chief Operations Cockpit Controller
 */
import {
  executionBadgeLabel,
  resolveAcademyEconomics,
  resolveAcademySummary,
  resolveChiefWaitState,
  resolveCorrelationTruth,
  resolveDecisionTruth,
  resolveGateDecisionTruth,
  resolveSpeechBubble,
  resolveDeskMatrix,
  resolveDirectorTruth,
  resolveExecutionTruth,
  resolveLiveHQMetrics,
  resolveStewardTruth,
  resolveTeacherTruth,
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

    // Master Operations TV Wall Elements
    this.tvActiveAgents = document.getElementById('tv-active-agents');
    this.tvIdleAgents = document.getElementById('tv-idle-agents');
    this.tvBlockedAgents = document.getElementById('tv-blocked-agents');
    this.tvAvailableDesks = document.getElementById('tv-available-desks');
    this.tvFutureDesks = document.getElementById('tv-future-desks');
    this.tvSystemHealth = document.getElementById('tv-system-health');
    this.tvWorkflow = document.getElementById('tv-workflow');
    this.tvCorrelation = document.getElementById('tv-correlation');
    this.tvChiefWait = document.getElementById('tv-chief-wait');
    this.tvContextVer = document.getElementById('tv-context-ver');
    this.tvAcademyTime = document.getElementById('tv-academy-time');
    this.busFlowViz = document.querySelector('.bus-flow-viz');
    this.snitchState = document.getElementById('snitch-state');
    this.snitchTask = document.getElementById('snitch-task');
    this.snitchAlert = document.getElementById('snitch-alert');
    this.treasuryEur = document.getElementById('treasury-eur');
    this.treasuryUsd = document.getElementById('treasury-usd');
    this.treasuryVerified = document.getElementById('treasury-verified');
    this.treasuryGoal = document.getElementById('treasury-goal');
    this.treasuryGoalBar = document.getElementById('treasury-goal-bar');

    // Academy Evidence Explorer Elements
    this.explorerLessonsList = document.getElementById('explorer-lessons-list');
    this.explorerOppsList = document.getElementById('explorer-opps-list');
    this.explorerEvalsList = document.getElementById('explorer-evals-list');

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

    // AI Academy: Agentenlehrer Elements
    this.badgeTeacherState = document.getElementById('badge-teacher-state');
    this.teacherTopic = document.getElementById('teacher-topic');
    this.teacherScheduleStatus = document.getElementById('teacher-schedule-status');
    this.teacherNextTime = document.getElementById('teacher-next-time');
    this.teacherLessonsOpps = document.getElementById('teacher-lessons-opps');
    this.teacherLastTime = document.getElementById('teacher-last-time');
    this.teacherNextAction = document.getElementById('teacher-next-action');
    this.teacherAcademyWindow = document.getElementById('teacher-academy-window');
    this.teacherEligibleAgents = document.getElementById('teacher-eligible-agents');
    this.teacherLatestLesson = document.getElementById('teacher-latest-lesson');
    this.teacherAffectedAgents = document.getElementById('teacher-affected-agents');
    this.teacherPendingLessons = document.getElementById('teacher-pending-lessons');
    this.teacherOpportunityCandidates = document.getElementById('teacher-opportunity-candidates');
    this.teacherTaskLabel = document.getElementById('teacher-task-label');
    this.teacherProgressNum = document.getElementById('teacher-progress-num');
    this.teacherProgressBar = document.getElementById('teacher-progress-bar');
    this.teacherFeedLog = document.getElementById('teacher-feed-log');

    // AI Academy: Schuldirektor Elements
    this.badgeDirectorState = document.getElementById('badge-director-state');
    this.directorReviewedApproved = document.getElementById('director-reviewed-approved');
    this.directorEvalsRatio = document.getElementById('director-evals-ratio');
    this.directorRuleViolations = document.getElementById('director-rule-violations');
    this.directorTestsRequired = document.getElementById('director-tests-required');
    this.directorNextAction = document.getElementById('director-next-action');
    this.econMinSaved = document.getElementById('econ-min-saved');
    this.econCostSaved = document.getElementById('econ-cost-saved');
    this.econRevenueTruth = document.getElementById('econ-revenue-truth');
    this.econAdoptedCount = document.getElementById('econ-adopted-count');
    this.directorTaskLabel = document.getElementById('director-task-label');
    this.directorProgressNum = document.getElementById('director-progress-num');
    this.directorProgressBar = document.getElementById('director-progress-bar');
    this.directorFeedLog = document.getElementById('director-feed-log');

    // Footer
    this.footerStewardStatus = document.getElementById('footer-steward-status');
    this.footerAcademyStatus = document.getElementById('footer-academy-status');
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

    // Human-gate actions must use the exact active-gate provenance, never the
    // global/latest workflow or decision shown elsewhere on the dashboard.
    const activeGate = bus.active_human_gate;
    const gateProvenanceComplete = Boolean(
      activeGate?.provenance_complete
      && activeGate.workflow_id
      && activeGate.correlation_id
    );
    this.currentWorkflow = gateProvenanceComplete ? activeGate.workflow_id : null;
    this.currentCorrelation = gateProvenanceComplete ? activeGate.correlation_id : null;
    const hasVerifiedGateContext = Boolean(this.currentWorkflow && this.currentCorrelation);
    this.btnGateApprove.disabled = !hasVerifiedGateContext;
    this.btnGateReject.disabled = !hasVerifiedGateContext;

    // 1. Update Bus Counts
    this.countDispatch.textContent = counts.dispatch || 0;
    this.countProcessed.textContent = counts.processed || 0;
    this.countDecisions.textContent = counts.decisions || 0;
    this.busLockStatus.textContent = bus.is_locked ? `LOCKED (${bus.active_lock})` : 'UNLOCKED';
    if (this.busFlowViz) {
      this.busFlowViz.classList.toggle('is-flow-active', Boolean(this.currentWorkflow && bus.is_locked));
    }

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
    this.chiefLastDecision.textContent = bus.human_gate
      ? resolveGateDecisionTruth(bus)
      : resolveDecisionTruth(bus);
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

    // 6. SNITCH watchdog: display only its persisted machine evidence.
    const snitch = agents['agent-snitch'] || {};
    if (this.snitchState) this.snitchState.textContent = snitch.state || 'UNKNOWN';
    if (this.snitchTask) this.snitchTask.textContent = snitch.task || 'No monitored task recorded';
    if (this.snitchAlert) this.snitchAlert.textContent = data.runtime_alert?.classification || 'NO_ALERT';
    const snitchCard = document.getElementById('station-snitch');
    if (snitchCard) {
      snitchCard.classList.toggle(
        'active-working',
        snitch.state === 'MONITORING' || snitch.state === 'SLOW_BUT_PROGRESSING',
      );
    }

    this.renderSpeechBubbles({
      'agent-chief-commander': chief,
      'agent-courier-relay': agents['agent-courier-relay'] || {},
      'agent-antigravity-bridge': ag,
      'agent-codex-bridge': codex,
      'agent-thought-curator': curator,
      'agent-update-steward': agents['agent-update-steward'] || {},
      'agent-academy-teacher': agents['agent-academy-teacher'] || {},
      'agent-academy-director': agents['agent-academy-director'] || {},
      'agent-snitch': snitch,
    }, bus);

    const treasury = data.treasury || {};
    if (this.treasuryEur) this.treasuryEur.textContent = treasury.eur ?? 'UNKNOWN';
    if (this.treasuryUsd) this.treasuryUsd.textContent = treasury.usd ?? 'UNKNOWN';
    if (this.treasuryVerified) this.treasuryVerified.textContent = treasury.last_verified_at || 'NOT_VERIFIED';
    if (this.treasuryGoal) {
      this.treasuryGoal.textContent = `$${treasury.goal_current_usd ?? 'UNKNOWN'} / $${Number(treasury.goal_target_usd || 1_000_000_000).toLocaleString()}`;
    }
    if (this.treasuryGoalBar) {
      const percent = Math.min(100, ((Number(treasury.goal_current_usd) || 0) / (Number(treasury.goal_target_usd) || 1)) * 100);
      this.treasuryGoalBar.style.width = `${percent}%`;
    }

    // 7. Update AI Academy: Agentenlehrer Station
    const teacher = resolveTeacherTruth(data);
    if (this.badgeTeacherState) {
      this.badgeTeacherState.textContent = teacher.state;
    }
    if (this.teacherTopic) {
      this.teacherTopic.textContent = teacher.current_topic || 'UNKNOWN';
    }
    if (this.teacherScheduleStatus) {
      this.teacherScheduleStatus.textContent = teacher.schedule_status;
      this.teacherScheduleStatus.className = teacher.schedule_status === 'RESEARCH RUNNING'
        ? 'metric-value font-mono text-accent'
        : 'metric-value font-mono';
    }
    if (this.teacherNextTime) {
      this.teacherNextTime.textContent = teacher.next_school_time || 'UNKNOWN';
    }
    if (this.teacherLessonsOpps) {
      this.teacherLessonsOpps.textContent = `${this.formatEvidenceValue(teacher.lessons_today)} / ${this.formatEvidenceValue(teacher.opportunities_found)}`;
    }
    if (this.teacherLastTime) {
      this.teacherLastTime.textContent = teacher.last_school_time || 'UNKNOWN';
    }
    if (this.teacherNextAction) {
      this.teacherNextAction.textContent = teacher.next_action || 'UNKNOWN';
    }
    if (this.teacherAcademyWindow) {
      const enabled = teacher.academy_enabled === null ? 'UNKNOWN' : (teacher.academy_enabled ? 'ENABLED' : 'DISABLED');
      this.teacherAcademyWindow.textContent = `${enabled} / ${teacher.school_window_minutes === null ? 'UNKNOWN' : `${teacher.school_window_minutes} min`}`;
    }
    if (this.teacherEligibleAgents) {
      this.teacherEligibleAgents.textContent = teacher.eligible_agents === null
        ? 'UNKNOWN'
        : (teacher.eligible_agents.length ? teacher.eligible_agents.join(', ') : 'NONE');
    }
    if (this.teacherLatestLesson) {
      this.teacherLatestLesson.textContent = teacher.latest_lesson
        ? `📚 LESSON: ${teacher.latest_lesson} | ${teacher.latest_lesson_status || 'STATUS UNKNOWN'}`
        : '📚 UNKNOWN';
    }
    if (this.teacherAffectedAgents) {
      this.renderEvidencePills(this.teacherAffectedAgents, teacher.affected_agents, 'NONE');
    }
    if (this.teacherPendingLessons) {
      this.renderEvidencePills(this.teacherPendingLessons, teacher.pending_lessons, 'QUEUE EMPTY');
    }
    if (this.teacherOpportunityCandidates) {
      this.renderEvidencePills(this.teacherOpportunityCandidates, teacher.opportunity_candidates, 'NONE');
    }
    if (this.teacherTaskLabel) {
      this.teacherTaskLabel.textContent = `Status: ${teacher.state}`;
    }
    const teacherProgress = Number.isFinite(teacher.progress) ? Math.round(teacher.progress * 100) : null;
    if (this.teacherProgressNum) {
      this.teacherProgressNum.textContent = teacherProgress === null ? 'UNKNOWN' : `${teacherProgress}%`;
    }
    if (this.teacherProgressBar) {
      this.teacherProgressBar.style.width = `${teacherProgress || 0}%`;
    }
    if (teacher.next_action) {
      this.appendLog(this.teacherFeedLog, `[LEHRER] ${teacher.next_action}`);
    }

    const teacherCard = document.getElementById('station-teacher');
    if (teacherCard) {
      if (teacher.state === 'RESEARCHING' || teacher.state === 'PROPOSING' || teacher.state === 'PENDING_REVIEW') {
        teacherCard.classList.add('active-working');
      } else {
        teacherCard.classList.remove('active-working');
      }
    }

    // 8. Update AI Academy: Schuldirektor Station & Economics
    const director = resolveDirectorTruth(data);
    const econ = resolveAcademyEconomics(data);

    if (this.badgeDirectorState) {
      this.badgeDirectorState.textContent = director.state;
    }
    if (this.directorReviewedApproved) {
      this.directorReviewedApproved.textContent = `${this.formatEvidenceValue(director.lessons_reviewed)} / ${this.formatEvidenceValue(director.lessons_approved)}`;
    }
    if (this.directorEvalsRatio) {
      this.directorEvalsRatio.textContent = `${this.formatEvidenceValue(director.evals_passed)} / ${this.formatEvidenceValue(director.evals_failed)}`;
    }
    if (this.directorRuleViolations) {
      this.directorRuleViolations.textContent = this.formatEvidenceValue(director.rule_violations);
      this.directorRuleViolations.className = director.rule_violations !== null && director.rule_violations > 0
        ? 'metric-value font-mono text-alert'
        : 'metric-value font-mono';
    }
    if (this.directorTestsRequired) {
      this.directorTestsRequired.textContent = this.formatEvidenceValue(director.tests_required);
    }
    if (this.directorNextAction) {
      this.directorNextAction.textContent = director.next_action || 'UNKNOWN';
    }

    // Update Economic Metrics
    if (this.econMinSaved) {
      this.econMinSaved.textContent = `⏱️ Saved: ${econ.measured_minutes_saved === null ? 'UNKNOWN' : `${econ.measured_minutes_saved} min`}`;
    }
    if (this.econCostSaved) {
      this.econCostSaved.textContent = `💶 Saved: ${econ.measured_cost_saved_eur === null ? 'UNKNOWN' : `${econ.measured_cost_saved_eur.toFixed(2)} EUR`}`;
    }
    if (this.econRevenueTruth) {
      this.econRevenueTruth.textContent = `💰 Revenue: ${econ.revenue_evidence}`;
    }
    if (this.econAdoptedCount) {
      this.econAdoptedCount.textContent = `📜 Adopted: ${this.formatEvidenceValue(econ.lessons_adopted)}`;
    }

    if (this.directorTaskLabel) {
      this.directorTaskLabel.textContent = `Status: ${director.state}`;
    }
    const directorProgress = Number.isFinite(director.progress) ? Math.round(director.progress * 100) : null;
    if (this.directorProgressNum) {
      this.directorProgressNum.textContent = directorProgress === null ? 'UNKNOWN' : `${directorProgress}%`;
    }
    if (this.directorProgressBar) {
      this.directorProgressBar.style.width = `${directorProgress || 0}%`;
    }
    if (director.next_action) {
      this.appendLog(this.directorFeedLog, `[DIREKTOR] ${director.next_action}`);
    }

    const directorCard = document.getElementById('station-director');
    if (directorCard) {
      if (director.state === 'CHECKING ATTENDANCE' || director.state === 'REVIEWING LESSON' || director.state === 'EVALUATING') {
        directorCard.classList.add('active-working');
      } else {
        directorCard.classList.remove('active-working');
      }
    }

    // Update Footer Status
    if (this.footerAcademyStatus) {
      this.footerAcademyStatus.textContent = teacher.state !== 'UNKNOWN'
        ? 'ACTIVE (TEACHER + DIRECTOR)'
        : 'STANDBY';
    }

    // 9. Update Master Operations TV Wall
    const hqMetrics = resolveLiveHQMetrics(data);
    if (this.tvActiveAgents) this.tvActiveAgents.textContent = hqMetrics.active_agents;
    if (this.tvIdleAgents) this.tvIdleAgents.textContent = hqMetrics.idle_agents;
    if (this.tvBlockedAgents) this.tvBlockedAgents.textContent = hqMetrics.blocked_agents;
    if (this.tvAvailableDesks) this.tvAvailableDesks.textContent = hqMetrics.available_workstations;
    if (this.tvFutureDesks) this.tvFutureDesks.textContent = hqMetrics.future_workstations;
    if (this.tvWorkflow) this.tvWorkflow.textContent = hqMetrics.current_workflow || 'UNKNOWN';
    if (this.tvCorrelation) this.tvCorrelation.textContent = hqMetrics.correlation_id || 'UNKNOWN';
    if (this.tvChiefWait) this.tvChiefWait.textContent = hqMetrics.chief_wait_state;
    if (this.tvContextVer) this.tvContextVer.textContent = hqMetrics.context_version === null ? 'UNKNOWN' : `v${hqMetrics.context_version}`;
    if (this.tvAcademyTime) this.tvAcademyTime.textContent = teacher.next_school_time || 'UNKNOWN';
    if (this.tvSystemHealth) {
      this.tvSystemHealth.textContent = hqMetrics.system_health;
      this.tvSystemHealth.className = hqMetrics.system_health === 'ATTENTION_REQUIRED'
        ? 'tv-health-badge alert'
        : 'tv-health-badge';
    }

    // 10. Update Academy Evidence Explorer
    const academySummary = resolveAcademySummary(data);
    if (this.explorerLessonsList) {
      if (academySummary.recent_lessons && academySummary.recent_lessons.length > 0) {
        this.explorerLessonsList.innerHTML = academySummary.recent_lessons
          .map(l => `<div class="log-entry">📌 [${l.status}] <b>${l.title}</b> (${l.topic || 'General'}) - Risk: ${l.risk || 'LOW'}</div>`)
          .join('');
      } else {
        this.explorerLessonsList.textContent = academySummary.recent_lessons === null
          ? 'Academy evidence unavailable.'
          : 'No recent lessons discovered yet.';
      }
    }

    if (this.explorerOppsList) {
      if (academySummary.recent_opportunities && academySummary.recent_opportunities.length > 0) {
        this.explorerOppsList.innerHTML = academySummary.recent_opportunities
          .map(o => `<div class="log-entry text-accent">💡 [${o.status}] <b>${o.title}</b> (Rev: ${o.revenue_evidence || 'NOT_VERIFIED'})</div>`)
          .join('');
      } else {
        this.explorerOppsList.textContent = academySummary.recent_opportunities === null
          ? 'Academy evidence unavailable.'
          : 'No opportunity candidates pending.';
      }
    }

    if (this.explorerEvalsList) {
      if (academySummary.recent_evaluations && academySummary.recent_evaluations.length > 0) {
        this.explorerEvalsList.innerHTML = academySummary.recent_evaluations
          .map(e => `<div class="log-entry">⚖️ [${e.verdict}] Eval: ${e.lesson_id} - Time saved: ${e.metrics?.runtime_seconds_saved || 0}s</div>`)
          .join('');
      } else {
        this.explorerEvalsList.textContent = academySummary.recent_evaluations === null
          ? 'Academy evidence unavailable.'
          : 'No evaluation runs recorded.';
      }
    }

    // 11. Human Gate Alert Banner
    if (curatorState === 'CONFLICT' || curatorState === 'BLOCKED' || chief.state === 'BLOCKED_HUMAN_GATE' || chief.state === 'BLOCKED_POLICY_CONFLICT' || codex.state === 'BLOCKED_HUMAN_GATE' || ag.state === 'BLOCKED_HUMAN_GATE' || bus.human_gate) {
      this.gateBanner.classList.remove('hidden');
      this.gateDesc.textContent = hasVerifiedGateContext
        ? `Workflow task paused: ${curator.last_action || codex.task || ag.task || chief.task || 'Explicit human approval required'}`
        : 'Workflow task paused: WAITING_FOR_HUMAN — verified workflow/correlation provenance is unavailable.';
    } else {
      this.gateBanner.classList.add('hidden');
    }
  }

  formatEvidenceValue(value) {
    return value === null || value === undefined ? 'UNKNOWN' : String(value);
  }

  renderSpeechBubbles(agentStates, bus) {
    const stationByAgent = {
      'agent-chief-commander': 'station-chief',
      'agent-courier-relay': 'station-courier',
      'agent-antigravity-bridge': 'station-antigravity',
      'agent-codex-bridge': 'station-codex',
      'agent-thought-curator': 'station-curator',
      'agent-update-steward': 'station-steward',
      'agent-academy-teacher': 'station-teacher',
      'agent-academy-director': 'station-director',
      'agent-snitch': 'station-snitch',
    };
    for (const [agentId, state] of Object.entries(agentStates)) {
      const station = document.getElementById(stationByAgent[agentId]);
      if (!station) continue;
      let bubble = station.querySelector('.agent-speech-bubble');
      if (!bubble) {
        bubble = document.createElement('p');
        bubble.className = 'agent-speech-bubble';
        station.querySelector('.card-header')?.after(bubble);
      }
      bubble.textContent = resolveSpeechBubble(agentId, state, bus);
    }
  }

  renderEvidencePills(container, values, emptyLabel) {
    container.replaceChildren();
    const labels = values === null ? ['UNKNOWN'] : (values.length ? values : [emptyLabel]);
    labels.forEach((label) => {
      const pill = document.createElement('span');
      pill.className = 'affected-pill font-mono';
      pill.textContent = label;
      container.appendChild(pill);
    });
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
