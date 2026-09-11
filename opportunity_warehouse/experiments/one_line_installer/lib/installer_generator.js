function generateBashInstaller(options = {}) {
  const packageName = options.packageName || 'agent-context-trimmer';
  const version = options.version || '1.0.0';
  const installDir = options.installDir || '$HOME/.agent-context-trimmer';

  return `#!/usr/bin/env bash
# Deterministic One-Line Installer for ${packageName} v${version}
set -euo pipefail

echo "==> Installing ${packageName} v${version}..."

TARGET_DIR="${installDir}"
mkdir -p "$TARGET_DIR"

if ! command -v node >/dev/null 2>&1; then
  echo "Error: Node.js is required but not found in PATH." >&2
  exit 1
fi

NODE_VER=$(node -v)
echo "==> Verified Node.js runtime: $NODE_VER"

echo "==> Unpacking to $TARGET_DIR..."
# Unpack logic assumes release archive in current directory or piped stream
if [ -f "${packageName}-${version}.zip" ]; then
  unzip -q -o "${packageName}-${version}.zip" -d "$TARGET_DIR"
fi

BIN_PATH="$TARGET_DIR/bin/trimmer.js"
chmod +x "$BIN_PATH" 2>/dev/null || true

echo "==> Installation successful! Run with: node $BIN_PATH --help"
`;
}

function generatePowerShellInstaller(options = {}) {
  const packageName = options.packageName || 'agent-context-trimmer';
  const version = options.version || '1.0.0';

  return `# Deterministic PowerShell Installer for ${packageName} v${version}
\$ErrorActionPreference = 'Stop'

Write-Host "==> Installing ${packageName} v${version}..." -ForegroundColor Cyan

\$TargetDir = Join-Path \$env:USERPROFILE ".${packageName}"
if (!(Test-Path -Path \$TargetDir)) {
  New-Item -ItemType Directory -Path \$TargetDir -Force | Out-Null
}

\$NodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (!\$NodeCmd) {
  Write-Error "Node.js runtime was not found in PATH. Please install Node.js 18+."
  exit 1
}

\$ZipPath = ".${packageName}-${version}.zip"
if (Test-Path -Path \$ZipPath) {
  Expand-Archive -Path \$ZipPath -DestinationPath \$TargetDir -Force
  Write-Host "==> Unpacked archive to \$TargetDir" -ForegroundColor Green
}

\$BinPath = Join-Path \$TargetDir "bin\\trimmer.js"
Write-Host "==> Installation complete! Test with: node \$BinPath --version" -ForegroundColor Cyan
`;
}

module.exports = {
  generateBashInstaller,
  generatePowerShellInstaller
};
