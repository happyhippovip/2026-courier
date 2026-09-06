import { resolveLivingRoomAgents } from '../studio/execution_truth.js';
const emptyLiving = resolveLivingRoomAgents({});
console.log(emptyLiving.find(a => a.id === 'agent-chief-commander').state);
