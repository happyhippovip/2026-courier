import { resolveLivingRoomAgents } from '../studio/execution_truth.js';

const emptyLiving = resolveLivingRoomAgents({});
for (const ag of emptyLiving) {
  if (!ag.is_bodyguard) {
    if (ag.state !== 'IDLE' && ag.state !== 'UNKNOWN') {
      console.log(ag.id, ag.state);
    }
  }
}
