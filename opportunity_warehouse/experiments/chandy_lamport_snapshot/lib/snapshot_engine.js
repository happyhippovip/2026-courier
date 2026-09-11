/**
 * Multi-Agent Distributed Logical Time Sync & Chandy-Lamport Global Snapshot Engine
 * Implements the Chandy-Lamport algorithm for recording consistent global checkpoints
 * of multi-agent distributed context states and in-flight communication channels without halting execution.
 */

class AgentProcess {
  constructor(processId, initialState = {}) {
    this.processId = processId;
    this.state = { ...initialState };
    this.recordedState = null;
    this.hasRecordedState = false;
    this.incomingChannels = new Map(); // channelId -> { recording: boolean, messages: [] }
    this.outgoingChannels = []; // array of channelId
  }

  mutateState(key, value) {
    this.state[key] = value;
  }
}

class ChandyLamportSnapshotEngine {
  constructor() {
    this.processes = new Map();
    this.channels = new Map(); // channelId -> { from, to, queue: [] }
    this.snapshotInProgress = false;
  }

  registerProcess(processId, initialState = {}) {
    const p = new AgentProcess(processId, initialState);
    this.processes.set(processId, p);
    return p;
  }

  createChannel(fromId, toId) {
    const channelId = fromId + '->' + toId;
    this.channels.set(channelId, { from: fromId, to: toId, queue: [] });

    const pFrom = this.processes.get(fromId);
    const pTo = this.processes.get(toId);

    pFrom.outgoingChannels.push(channelId);
    pTo.incomingChannels.set(channelId, { recording: false, messages: [] });
    return channelId;
  }

  sendMessage(fromId, toId, payload) {
    const channelId = fromId + '->' + toId;
    const ch = this.channels.get(channelId);
    if (!ch) throw new Error('Channel not found: ' + channelId);

    ch.queue.push({
      type: 'DATA',
      payload,
      timestamp: Date.now()
    });
  }

  initiateSnapshot(initiatorId) {
    const p = this.processes.get(initiatorId);
    if (!p) throw new Error('Initiator not found: ' + initiatorId);

    this.snapshotInProgress = true;

    // 1. Initiator records its own state
    p.recordedState = JSON.parse(JSON.stringify(p.state));
    p.hasRecordedState = true;

    // 2. Starts recording on all incoming channels (except markers already seen)
    for (const [chId, rec] of p.incomingChannels.entries()) {
      rec.recording = true;
      rec.messages = [];
    }

    // 3. Sends MARKER along all outgoing channels
    for (const chId of p.outgoingChannels) {
      const ch = this.channels.get(chId);
      ch.queue.push({ type: 'MARKER', initiatorId });
    }
  }

  deliverNextMessage(channelId) {
    const ch = this.channels.get(channelId);
    if (!ch || ch.queue.length === 0) return null;

    const msg = ch.queue.shift();
    const dest = this.processes.get(ch.to);
    const chRec = dest.incomingChannels.get(channelId);

    if (msg.type === 'MARKER') {
      if (!dest.hasRecordedState) {
        // First marker received: record state, mark this channel empty, send markers
        dest.recordedState = JSON.parse(JSON.stringify(dest.state));
        dest.hasRecordedState = true;

        // Channel on which first marker arrived has 0 in-flight messages
        chRec.recording = false;

        // Other incoming channels start recording
        for (const [otherChId, otherRec] of dest.incomingChannels.entries()) {
          if (otherChId !== channelId) {
            otherRec.recording = true;
            otherRec.messages = [];
          }
        }

        // Forward marker along all outgoing channels
        for (const outChId of dest.outgoingChannels) {
          const outCh = this.channels.get(outChId);
          outCh.queue.push({ type: 'MARKER', initiatorId: msg.initiatorId });
        }
      } else {
        // Already recorded state: stop recording on this channel
        chRec.recording = false;
      }
      return { type: 'MARKER_DELIVERED', channelId };
    } else {
      // Normal DATA message
      if (chRec && chRec.recording) {
        // Message arrived after state recorded but before marker: in-flight message!
        chRec.messages.push(msg.payload);
      }
      // Apply message to destination process state
      dest.mutateState('lastReceived', msg.payload);
      return { type: 'DATA_DELIVERED', payload: msg.payload };
    }
  }

  assembleGlobalSnapshot() {
    const globalState = {
      processStates: {},
      channelStates: {}
    };

    for (const [pId, p] of this.processes.entries()) {
      globalState.processStates[pId] = p.recordedState;
      for (const [chId, rec] of p.incomingChannels.entries()) {
        globalState.channelStates[chId] = [...rec.messages];
      }
    }

    return globalState;
  }
}

module.exports = { ChandyLamportSnapshotEngine };
