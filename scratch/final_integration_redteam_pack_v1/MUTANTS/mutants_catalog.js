// Mutants Catalog — Adversarial Integration Invariant Mutations
// Mission: WINDOWS_FINAL_INTEGRATION_REDTEAM_PACK_V1

const CRITICAL_MUTANTS = [
  {
    id: 'MUTANT_A01_01',
    target: 'A01',
    name: 'Remove A01 Central Fence',
    description: 'Central dispatcher omits check for EXECUTION_UNCERTAIN; dispatches unconditionally.',
    config: { enableFence: false }
  },
  {
    id: 'MUTANT_A01_02',
    target: 'A01',
    name: 'Allow Fallback Around A01 Fence',
    description: 'Dispatcher enforces fence for initial dispatch, but permits router fallback/retry to bypass fence.',
    config: { allowFallbackAroundFence: true }
  },
  {
    id: 'MUTANT_L01_01',
    target: 'L01',
    name: 'Remove Resource Parent-Child Check',
    description: 'Lock manager checks only exact string equality, allowing tree:src/ and tree:src/core/ to overlap.',
    config: { disableParentChildCheck: true }
  },
  {
    id: 'MUTANT_L01_02',
    target: 'L01',
    name: 'Remove Semantic Resource Lock',
    description: 'Lock manager strips db: and port: prefixes, failing to detect collisions on non-fs resources.',
    config: { disableSemanticLock: true }
  },
  {
    id: 'MUTANT_L01_03',
    target: 'L01',
    name: 'Assume Case-Sensitive Universally',
    description: 'Fails to fold paths to lowercase on Windows NTFS/APFS, allowing src/Core/ and src/core/ to collide.',
    config: { universalCaseSensitive: true }
  },
  {
    id: 'MUTANT_G01_01',
    target: 'G01',
    name: 'Allow Deferred €0 Commitment',
    description: 'Safety gate only checks amount > 0; allows €0 today with auto-renew €50/mo to execute without gate.',
    config: { allowDeferredZeroEuro: true }
  },
  {
    id: 'MUTANT_G01_02',
    target: 'G01',
    name: 'Trust NLP Alone Without Tool Capability Barrier',
    description: 'Omitted low-level tool interceptor; benign-sounding prompt invoking stripe_charge executes directly.',
    config: { trustNlpAlone: true }
  },
  {
    id: 'MUTANT_G01_03',
    target: 'G01',
    name: 'Allow Approval Nonce Reuse (Replay Attack)',
    description: 'Omits consumed nonce tracking, allowing an approved token to be replayed for subsequent charges.',
    config: { allowNonceReuse: true }
  },
  {
    id: 'MUTANT_G01_04',
    target: 'G01',
    name: 'Remove Task Version Binding',
    description: 'Allows an approval token granted for task v1 to authorize a modified task v2.',
    config: { ignoreTaskVersion: true }
  },
  {
    id: 'MUTANT_B01_01',
    target: 'B01',
    name: 'PID-Only Process Matching',
    description: 'Reconciler assumes process is alive and authentic if PID exists in OS process table.',
    config: { pidOnlyMatch: true }
  },
  {
    id: 'MUTANT_B01_02',
    target: 'B01',
    name: 'UNKNOWN Treated as MATCH',
    description: 'When process start-time query fails or is missing, reconciler defaults to MATCH.',
    config: { unknownToMatch: true }
  },
  {
    id: 'MUTANT_B01_03',
    target: 'B01',
    name: 'UNKNOWN Process Treated as KILLABLE',
    description: 'When process start-time query fails, reconciler permits sending SIGKILL signal.',
    config: { unknownToKill: true }
  },
  {
    id: 'MUTANT_M01_01',
    target: 'MIGRATION',
    name: 'Legacy Missing Field Defaults to SAFE',
    description: 'Migration converts missing uncertainty or missing approval to SAFE/APPROVED.',
    config: { defaultMissingToSafe: true }
  }
];

module.exports = { CRITICAL_MUTANTS };
