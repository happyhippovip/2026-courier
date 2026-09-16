// Schema Registry for Versioned Events and Entities
const SCHEMA_VERSIONS = {
  EVENT_FRAME_V2: '2.0.0',
  TASK_PASSPORT_V2: '2.0.0',
  RESULT_ENVELOPE_V2: '2.0.0',
  CHECKPOINT_V2: '2.0.0'
};

const CANONICAL_EVENT_TYPES = Object.freeze([
  'MISSION_INITIALIZED',
  'GOAL_CREATED',
  'GOAL_UPDATED',
  'GOAL_SATISFIED',
  'TASK_PROPOSED',
  'TASK_NEGOTIATED',
  'TASK_STAMPED',
  'TASK_DISPATCHED',
  'TASK_HEARTBEAT',
  'TASK_COMPLETED',
  'TASK_VERIFIED',
  'TASK_FENCED',
  'TASK_CLOSED',
  'LEASE_ACQUIRED',
  'LEASE_RELEASED',
  'PROCESS_REGISTERED',
  'PROCESS_TERMINATED',
  'FOLLOW_UP_CAPTURED',
  'FRONTIER_REPLENISHED',
  'CHECKPOINT_SAVED'
]);

class SchemaRegistry {
  static validateEvent(event) {
    if (!event || typeof event !== 'object') return { valid: false, error: 'Event must be an object' };
    if (!event.type || !CANONICAL_EVENT_TYPES.includes(event.type)) {
      return { valid: false, error: 'Unknown event type: ' + event.type };
    }
    if (!event.timestamp) event.timestamp = new Date().toISOString();
    return { valid: true, event };
  }
}

module.exports = {
  SchemaRegistry,
  SCHEMA_VERSIONS,
  CANONICAL_EVENT_TYPES
};
