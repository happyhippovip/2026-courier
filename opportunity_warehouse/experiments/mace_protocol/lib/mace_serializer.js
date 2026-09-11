/**
 * mace_serializer.js - Multi-Agent Context Exchange Format (MACE) Serializer
 * Compact, deduplicated interchange protocol for multi-agent state handoffs.
 */
const crypto = require('crypto');

class MaceSerializer {
  constructor(options = {}) {
    this.version = options.version || '1.0.0';
  }

  hash(data) {
    return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
  }

  serializeHandoff(senderAgent, recipientAgent, context = {}) {
    const rawMessages = context.messages || [];
    const rawToolOutputs = context.toolOutputs || [];

    // Deduplicate tool outputs by content hash
    const seenToolHashes = new Set();
    const deduplicatedToolOutputs = [];
    let duplicateTokensSaved = 0;

    for (const tool of rawToolOutputs) {
      const content = tool.output || '';
      const h = this.hash(content);
      if (!seenToolHashes.has(h)) {
        seenToolHashes.add(h);
        deduplicatedToolOutputs.push({
          toolName: tool.name,
          callId: tool.callId,
          hash: h.substring(0, 12),
          output: content
        });
      } else {
        duplicateTokensSaved += Math.ceil(content.length / 4);
        deduplicatedToolOutputs.push({
          toolName: tool.name,
          callId: tool.callId,
          hash: h.substring(0, 12),
          output: '[MACE_REF:' + h.substring(0, 12) + ']'
        });
      }
    }

    // Clean message history (strip consecutive blank lines, trailing whitespace)
    const cleanedMessages = rawMessages.map(m => {
      let content = m.content || '';
      content = content.replace(/\r?\n\s*\r?\n/g, '\n').trim();
      return {
        role: m.role || 'user',
        content
      };
    });

    const payload = {
      protocol: 'MACE',
      version: this.version,
      timestamp: new Date().toISOString(),
      header: {
        senderAgent,
        recipientAgent,
        messageCount: cleanedMessages.length,
        toolCount: deduplicatedToolOutputs.length,
        duplicateTokensSaved
      },
      state: {
        messages: cleanedMessages,
        toolOutputs: deduplicatedToolOutputs,
        workspaceFlags: context.workspaceFlags || {}
      }
    };

    const checksum = this.hash(payload.state);
    payload.checksum = checksum;

    return payload;
  }

  deserializeHandoff(macePayload) {
    if (!macePayload || macePayload.protocol !== 'MACE') {
      throw new Error('Invalid MACE payload format');
    }
    const calculatedChecksum = this.hash(macePayload.state);
    if (calculatedChecksum !== macePayload.checksum) {
      throw new Error('MACE checksum mismatch: payload may be corrupted');
    }

    // Reconstruct deduplicated tool outputs
    const hashToContent = new Map();
    macePayload.state.toolOutputs.forEach(t => {
      if (!t.output.startsWith('[MACE_REF:')) {
        hashToContent.set(t.hash, t.output);
      }
    });

    const restoredToolOutputs = macePayload.state.toolOutputs.map(t => {
      if (t.output.startsWith('[MACE_REF:')) {
        const refHash = t.output.replace('[MACE_REF:', '').replace(']', '');
        return {
          ...t,
          output: hashToContent.get(refHash) || t.output,
          restoredFromRef: true
        };
      }
      return t;
    });

    return {
      senderAgent: macePayload.header.senderAgent,
      recipientAgent: macePayload.header.recipientAgent,
      messages: macePayload.state.messages,
      toolOutputs: restoredToolOutputs,
      workspaceFlags: macePayload.state.workspaceFlags,
      verified: true
    };
  }
}

module.exports = { MaceSerializer };
