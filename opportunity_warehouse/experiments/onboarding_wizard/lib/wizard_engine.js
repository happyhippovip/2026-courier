function generateProjectConfig(projectMeta = {}) {
  const projectType = (projectMeta.projectType || 'NODE_TYPESCRIPT').toUpperCase();
  const detectedFiles = projectMeta.detectedFiles || ['.cursorrules'];

  let compressionProfile = 'BALANCED';
  let stripComments = false;
  let prunePreamble = true;

  if (projectType === 'AI_AGENT_HEAVY') {
    compressionProfile = 'AGGRESSIVE';
    stripComments = true;
  } else if (projectType === 'DOCUMENTATION_MONOREPO') {
    compressionProfile = 'SAFE_PRESERVE';
    prunePreamble = false;
  }

  return {
    version: '1.0.0',
    project_type: projectType,
    profile: compressionProfile,
    settings: {
      prune_conversational_preamble: prunePreamble,
      deduplicate_identical_rules: true,
      extract_code_blocks_to_refs: true,
      strip_redundant_comments: stripComments,
      enforce_delimiter_balance: true
    },
    targets: detectedFiles,
    backup_directory: './.trimmer_backups',
    configured_at: new Date().toISOString()
  };
}

module.exports = { generateProjectConfig };
