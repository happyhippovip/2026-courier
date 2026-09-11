/**
 * shell_hook_generator.js - Pre-Prompt Bash/Zsh Shell Hook & Wrapper Generator
 * Generates transparent shell aliases and wrapper functions to auto-prune context before invoking LLM CLIs.
 */
class ShellHookGenerator {
  constructor(options = {}) {
    this.binaryPath = options.binaryPath || 'npx @symphony/agent-context-trimmer';
    this.targetTools = options.targetTools || ['claude', 'aider', 'cursor'];
  }

  generateBashZshHooks() {
    let script = '#!/usr/bin/env bash\n';
    script += '# Symphony Agent Context Trimmer - Automatic Shell Hook\n';
    script += '# Add this snippet to your ~/.bashrc or ~/.zshrc\n\n';
    script += 'trim_context() {\n';
    script += '  local target="$1"\n';
    script += '  if [ -f "$target" ]; then\n';
    script += '    ' + this.binaryPath + ' --file "$target" --inplace\n';
    script += '  fi\n';
    script += '}\n\n';

    this.targetTools.forEach(tool => {
      script += tool + '() {\n';
      script += '  # Auto-trim staged prompts before launching ' + tool + '\n';
      script += '  if [ -f "PROMPT.md" ]; then trim_context "PROMPT.md"; fi\n';
      script += '  if [ -f ".cursorrules" ]; then trim_context ".cursorrules"; fi\n';
      script += '  command ' + tool + ' "$@"\n';
      script += '}\n\n';
    });

    script += '# End Symphony Hook\n';
    return script;
  }

  generateFishHooks() {
    let script = '# Fish Shell Functions for Symphony Context Trimmer\n';
    script += 'function trim_context\n';
    script += '  set -l target $argv[1]\n';
    script += '  if test -f "$target"\n';
    script += '    ' + this.binaryPath + ' --file "$target" --inplace\n';
    script += '  end\n';
    script += 'end\n\n';

    this.targetTools.forEach(tool => {
      script += 'function ' + tool + ' --wraps ' + tool + '\n';
      script += '  if test -f "PROMPT.md"; trim_context "PROMPT.md"; end\n';
      script += '  command ' + tool + ' $argv\n';
      script += 'end\n\n';
    });

    return script;
  }

  generateInstallSnippet(shellType = 'bash') {
    const isFish = shellType === 'fish';
    const configFile = isFish ? '~/.config/fish/config.fish' : '~/.zshrc (or ~/.bashrc)';
    const content = isFish ? this.generateFishHooks() : this.generateBashZshHooks();

    return {
      shellType,
      targetConfigFile: configFile,
      content,
      instructions: 'Append the content to ' + configFile + ' and reload your shell.'
    };
  }
}

module.exports = { ShellHookGenerator };
