import assert from 'assert';
import { resolveLiveAgentMotion } from '../studio/execution_truth.js';

const handoffState = {
  active_handoff: {
    handoff_id: 'handoff-test-001',
    from_agent: 'agent-thought-curator',
    to_agent: 'agent-antigravity-bridge',
    task_id: 'WF-HANDOFF-101',
    correlation_id: 'corr-handoff-101',
    reason: 'Delegate 3D scene compile',
  },
  agents: {
    'agent-thought-curator': { id: 'agent-thought-curator', state: 'HANDOFF' },
    'agent-antigravity-bridge': { id: 'agent-antigravity-bridge', state: 'RUNNING' },
  },
};

const motion = resolveLiveAgentMotion(handoffState);
console.log("STATES:", motion.states);
