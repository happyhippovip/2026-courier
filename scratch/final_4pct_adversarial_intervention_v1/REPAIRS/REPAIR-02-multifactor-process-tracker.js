module.exports = function hardenedProcessClassifier(lease, osState) {
    if (!osState.exists) return 'NOT_MATCH';
    if (osState.metadataInaccessible || osState.accessDenied || osState.startTime === null) return 'UNKNOWN';
    if (lease.startTime && osState.startTime !== lease.startTime) return 'NOT_MATCH';
    if (lease.cmd && osState.cmd && osState.cmd !== lease.cmd) return 'NOT_MATCH';
    if (lease.ppid && osState.ppid && osState.ppid !== lease.ppid) return 'NOT_MATCH';
    if (lease.token && osState.cmdToken && osState.cmdToken !== lease.token) return 'NOT_MATCH';
    if (lease.startTime && osState.startTime === lease.startTime) return 'MATCH_CONFIRMED';
    return 'UNKNOWN';
  };
